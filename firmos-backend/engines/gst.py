"""GST computation engine — deterministic, NO AI, 100% tested.

All amounts in PAISE. Rate inputs as percentages (e.g. 18 for 18%).
"""


# GST slab rates (percentages)
GST_SLABS = [0, 5, 12, 18, 28]
from core.money import paise_to_decimal


def calculate_gst(taxable_paise: int, rate_percent: int, is_interstate: bool) -> dict:
    """Compute GST components from taxable amount and rate.
    
    Returns dict with cgst, sgst, igst, total (all in paise).
    Interstate = IGST only. Intra-state = CGST + SGST (50/50).
    """
    if rate_percent not in GST_SLABS:
        raise ValueError(f"Invalid GST rate: {rate_percent}%. Valid: {GST_SLABS}")

    gst_paise = int(taxable_paise * rate_percent / 100)

    if is_interstate:
        return {
            "cgst": 0,
            "sgst": 0,
            "igst": gst_paise,
            "total": taxable_paise + gst_paise,
        }
    else:
        half = gst_paise // 2
        remainder = gst_paise - (half * 2)  # handle odd paise
        return {
            "cgst": half,
            "sgst": half + remainder,
            "igst": 0,
            "total": taxable_paise + gst_paise,
        }


def calculate_net_gst_payable(
    output_gst_paise: int,
    itc_available_paise: int,
    itc_eligible_paise: int,
) -> dict:
    """Compute net GST payable after ITC.
    
    ITC can only be claimed up to eligible amount.
    Net payable = output GST - min(available, eligible) ITC.
    """
    usable_itc = min(itc_available_paise, itc_eligible_paise)
    net_payable = max(0, output_gst_paise - usable_itc)
    itc_used = output_gst_paise - net_payable

    return {
        "output_gst": output_gst_paise,
        "itc_available": itc_available_paise,
        "itc_eligible": itc_eligible_paise,
        "itc_used": itc_used,
        "net_payable": net_payable,
    }


def check_itc_eligibility(
    supplier_filed: bool,
    invoice_amount_paise: int,
    gstr2b_amount_paise: int,
    tolerance_paise: int = 100,
) -> dict:
    """Check if ITC can be claimed for an invoice.
    
    Rules:
    - Supplier must have filed their return
    - Amount must match within tolerance (₹1 default)
    """
    amount_matches = abs(invoice_amount_paise - gstr2b_amount_paise) <= tolerance_paise
    eligible = supplier_filed and amount_matches

    reason = ""
    if not supplier_filed:
        reason = "Supplier has not filed GSTR-1"
    elif not amount_matches:
        reason = f"Amount mismatch: invoice={invoice_amount_paise} vs 2B={gstr2b_amount_paise}"

    return {
        "eligible": eligible,
        "reason": reason,
        "invoice_amount": invoice_amount_paise,
        "gstr2b_amount": gstr2b_amount_paise,
    }


def generate_gstr3b_tables(
    output_taxable_paise: int,
    output_igst_paise: int,
    output_cgst_paise: int,
    output_sgst_paise: int,
    itc_igst_paise: int,
    itc_cgst_paise: int,
    itc_sgst_paise: int,
    rcm_inward_paise: int = 0,
    exempt_inward_paise: int = 0,
    ineligible_itc_paise: int = 0,
) -> dict:
    """Generate exact GST Portal GSTR-3B copy-paste table layout (all cells in paise)."""
    usable_igst = min(output_igst_paise, itc_igst_paise)
    usable_cgst = min(output_cgst_paise, itc_cgst_paise)
    usable_sgst = min(output_sgst_paise, itc_sgst_paise)

    return {
        "table_3_1": {
            "a_outward_taxable_supplies": {
                "txval": output_taxable_paise,
                "iamt": output_igst_paise,
                "camt": output_cgst_paise,
                "samt": output_sgst_paise,
                "csamt": 0,
            },
            "b_outward_taxable_zero_rated": {"txval": 0, "iamt": 0, "csamt": 0},
            "c_other_outward_nil_exempt": {"txval": 0},
            "d_inward_supplies_liable_to_reverse_charge": {
                "txval": rcm_inward_paise,
                "iamt": 0,
                "camt": 0,
                "samt": 0,
                "csamt": 0,
            },
            "e_non_gst_outward_supplies": {"txval": 0},
        },
        "table_3_2": {
            "interstate_supplies_unregistered": [],
            "interstate_supplies_composition": [],
            "interstate_supplies_uin": [],
        },
        "table_4": {
            "A_itc_available": {
                "1_import_goods": {"iamt": 0, "csamt": 0},
                "2_import_services": {"iamt": 0, "csamt": 0},
                "3_inward_supplies_reverse_charge": {"iamt": 0, "camt": 0, "samt": 0, "csamt": 0},
                "4_inward_supplies_isd": {"iamt": 0, "camt": 0, "samt": 0, "csamt": 0},
                "5_all_other_itc": {
                    "iamt": itc_igst_paise,
                    "camt": itc_cgst_paise,
                    "samt": itc_sgst_paise,
                    "csamt": 0,
                },
            },
            "B_itc_reversed": {"rule_38_42_43": {"iamt": 0, "camt": 0, "samt": 0, "csamt": 0}, "others": {"iamt": 0, "camt": 0, "samt": 0, "csamt": 0}},
            "C_net_itc_available": {
                "iamt": itc_igst_paise,
                "camt": itc_cgst_paise,
                "samt": itc_sgst_paise,
                "csamt": 0,
            },
            "D_ineligible_itc": {
                "section_17_5": {"iamt": ineligible_itc_paise, "camt": 0, "samt": 0, "csamt": 0},
                "others": {"iamt": 0, "camt": 0, "samt": 0, "csamt": 0},
            },
        },
        "table_5": {
            "exempt_nil_non_gst_inward": {"inter_state_supplies": exempt_inward_paise, "intra_state_supplies": 0}
        },
        "table_6_1": {
            "payment_of_tax": {
                "igst": {
                    "payable": output_igst_paise,
                    "paid_itc": usable_igst,
                    "paid_cash": max(0, output_igst_paise - usable_igst),
                },
                "cgst": {
                    "payable": output_cgst_paise,
                    "paid_itc": usable_cgst,
                    "paid_cash": max(0, output_cgst_paise - usable_cgst),
                },
                "sgst": {
                    "payable": output_sgst_paise,
                    "paid_itc": usable_sgst,
                    "paid_cash": max(0, output_sgst_paise - usable_sgst),
                },
            }
        },
    }


def export_gstr3b_gstn_json(gstin: str, period: str, tables: dict) -> dict:
    """Format tables into official GSTN GSTR-3B offline utility JSON upload format."""
    def p2r(val_paise: int) -> str:
        return str(paise_to_decimal(val_paise))

    t31 = tables.get("table_3_1", {})
    t4 = tables.get("table_4", {})
    t5 = tables.get("table_5", {})

    osup_det = {
        "txval": p2r(t31.get("a_outward_taxable_supplies", {}).get("txval", 0)),
        "iamt": p2r(t31.get("a_outward_taxable_supplies", {}).get("iamt", 0)),
        "camt": p2r(t31.get("a_outward_taxable_supplies", {}).get("camt", 0)),
        "samt": p2r(t31.get("a_outward_taxable_supplies", {}).get("samt", 0)),
        "csamt": "0.00",
    }

    itc_avl = t4.get("A_itc_available", {}).get("5_all_other_itc", {})

    return {
        "gstin": gstin.upper(),
        "ret_period": period,
        "sup_details": {"osup_det": osup_det},
        "inter_sup": {"unreg_details": []},
        "itc_elg": {
            "itc_avl": [
                {
                    "ty": "ALL_OTHER_ITC",
                    "iamt": p2r(itc_avl.get("iamt", 0)),
                    "camt": p2r(itc_avl.get("camt", 0)),
                    "samt": p2r(itc_avl.get("samt", 0)),
                    "csamt": "0.00",
                }
            ]
        },
        "inward_sup": {
            "isup_details": [
                {"ty": "GST", "inter": p2r(t5.get("exempt_nil_non_gst_inward", {}).get("inter_state_supplies", 0)), "intra": "0.00"}
            ]
        },
    }
