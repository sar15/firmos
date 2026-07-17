"""Tests for all deterministic engines — GST, TDS, interest, tax, reconciliation."""

import pytest
from datetime import date

# ---- GST Engine ----
def test_gst_intrastate_18():
    """18% GST intra-state → 9% CGST + 9% SGST."""
    from engines.gst import calculate_gst
    result = calculate_gst(1000000, 18, is_interstate=False)  # ₹10,000
    assert result["cgst"] == 90000   # ₹900
    assert result["sgst"] == 90000
    assert result["igst"] == 0
    assert result["total"] == 1180000  # ₹11,800


def test_gst_interstate_18():
    """18% GST inter-state → 18% IGST only."""
    from engines.gst import calculate_gst
    result = calculate_gst(1000000, 18, is_interstate=True)
    assert result["cgst"] == 0
    assert result["sgst"] == 0
    assert result["igst"] == 180000
    assert result["total"] == 1180000


def test_gst_zero_rate():
    """0% GST → no tax."""
    from engines.gst import calculate_gst
    result = calculate_gst(1000000, 0, is_interstate=False)
    assert result["total"] == 1000000


def test_gst_invalid_rate():
    """Invalid GST rate raises ValueError."""
    from engines.gst import calculate_gst
    with pytest.raises(ValueError, match="Invalid GST rate"):
        calculate_gst(1000000, 15, is_interstate=False)


def test_gst_net_payable():
    """Net payable = output - min(available, eligible) ITC."""
    from engines.gst import calculate_net_gst_payable
    result = calculate_net_gst_payable(
        output_gst_paise=500000,   # ₹5,000
        itc_available_paise=300000,  # ₹3,000
        itc_eligible_paise=250000,   # ₹2,500 — less than available
    )
    assert result["itc_used"] == 250000
    assert result["net_payable"] == 250000  # 5000 - 2500 = 2500


def test_gst_itc_eligibility_pass():
    from engines.gst import check_itc_eligibility
    result = check_itc_eligibility(supplier_filed=True, invoice_amount_paise=1000000, gstr2b_amount_paise=1000050)
    assert result["eligible"] is True


def test_gst_itc_eligibility_fail_not_filed():
    from engines.gst import check_itc_eligibility
    result = check_itc_eligibility(supplier_filed=False, invoice_amount_paise=1000000, gstr2b_amount_paise=1000000)
    assert result["eligible"] is False
    assert "not filed" in result["reason"]


# ---- TDS Engine ----

def test_tds_194j_professional():
    """10% TDS on professional services."""
    from engines.tds import calculate_tds
    result = calculate_tds("194J_PROF", 5000000)  # ₹50,000
    assert result["tds_amount"] == 500000  # ₹5,000
    assert result["net_amount"] == 4500000


def test_tds_below_threshold():
    """Below threshold → no TDS."""
    from engines.tds import calculate_tds
    result = calculate_tds("194J_PROF", 2000000)  # ₹20,000 (threshold ₹30,000)
    assert result["tds_amount"] == 0
    assert result["rate"] == 0.0


def test_tds_no_pan():
    """No PAN → rate doubles (max 20%)."""
    from engines.tds import calculate_tds
    result = calculate_tds("194J_PROF", 5000000, pan_available=False)
    assert result["rate"] == 20.0  # 10% × 2 = 20%
    assert result["tds_amount"] == 1000000


def test_tds_contractor():
    """1% TDS for individual contractor."""
    from engines.tds import calculate_tds
    result = calculate_tds("194C", 5000000)
    assert result["rate"] == 1.0
    assert result["tds_amount"] == 50000


# ---- Interest Engine ----

def test_234b_shortfall():
    """234B interest on advance tax shortfall."""
    from engines.interest import calculate_234b_interest
    result = calculate_234b_interest(
        total_tax_paise=10000000,        # ₹1,00,000
        advance_tax_paid_paise=5000000,  # ₹50,000 (< 90%)
        assessment_year_end=date(2026, 3, 31),
        actual_filing_date=date(2026, 7, 15),
    )
    assert result["applicable"] is True
    assert result["shortfall"] == 5000000  # ₹50,000
    assert result["months"] >= 3
    assert result["interest"] > 0


def test_234b_no_interest():
    """234B — advance tax >= 90% → no interest."""
    from engines.interest import calculate_234b_interest
    result = calculate_234b_interest(
        total_tax_paise=10000000,
        advance_tax_paid_paise=9500000,  # 95% > 90%
        assessment_year_end=date(2026, 3, 31),
        actual_filing_date=date(2026, 7, 15),
    )
    assert result["applicable"] is False


def test_234c_interest():
    """234C interest on deferred installments."""
    from engines.interest import calculate_234c_interest
    result = calculate_234c_interest(
        total_tax_paise=10000000,  # ₹1,00,000
        installments_paid=[
            {"label": "15 Jun", "amount_paise": 1000000},   # paid ₹10k (need 15k)
            {"label": "15 Sep", "amount_paise": 2000000},   # paid ₹20k
            {"label": "15 Dec", "amount_paise": 3000000},   # paid ₹30k
            {"label": "15 Mar", "amount_paise": 4000000},   # paid ₹40k
        ],
    )
    assert result["applicable"] is True
    assert result["total_interest"] > 0


def test_234b_starts_on_prior_april_and_rounds_interest_base_to_100_rupees():
    from engines.interest import calculate_234b_interest
    result = calculate_234b_interest(
        total_tax_paise=10000100, advance_tax_paid_paise=0,
        assessment_year_end=date(2026, 3, 31), actual_filing_date=date(2026, 4, 1),
    )
    assert result["months"] == 12
    assert result["interest_base"] == 10000000  # ₹100,000; Rule 119A drops ₹1


def test_234c_safe_harbour_is_a_trigger_but_interest_uses_statutory_due_amount():
    from engines.interest import calculate_234c_interest
    no_june_charge = calculate_234c_interest(10000000, [{"label": "15 Jun", "amount_paise": 1200000}])
    assert all(item["installment"] != "15 Jun" for item in no_june_charge["details"])

    charged = calculate_234c_interest(10000000, [{"label": "15 Jun", "amount_paise": 1100000}])
    june = next(item for item in charged["details"] if item["installment"] == "15 Jun")
    assert june["shortfall"] == 400000  # 15% due minus 11% paid, not 12% minus 11%


# ---- Tax Engine ----

def test_income_tax_new_regime_below_7l():
    """New regime: income <= 7L → full rebate under 87A."""
    from engines.tax import calculate_income_tax
    result = calculate_income_tax(700000_00)  # ₹7,00,000
    assert result["total_tax"] == 0  # rebate
    assert result["rebate_87a"] > 0


def test_income_tax_new_regime_10l():
    """New regime: ₹10L income."""
    from engines.tax import calculate_income_tax
    result = calculate_income_tax(1000000_00)  # ₹10,00,000
    assert result["base_tax"] > 0
    assert result["cess"] > 0
    assert result["total_tax"] > 0
    # 0-3L: 0, 3-7L: 20000, 7-10L: 30000 = ₹50,000
    assert result["base_tax"] == 5000000  # ₹50,000 in paise


def test_income_tax_old_regime_10l():
    """Old regime: ₹10L income."""
    from engines.tax import calculate_income_tax
    result = calculate_income_tax(1000000_00, regime="OLD")
    # 0-2.5L: 0, 2.5-5L: 12500, 5-10L: 100000 = ₹1,12,500
    assert result["base_tax"] == 11250000  # ₹1,12,500


def test_surcharge_bands_do_not_fall_through_and_marginal_relief_caps_the_step():
    from engines.tax import calculate_income_tax
    below = calculate_income_tax(4900000_00, regime="OLD")
    at_50l = calculate_income_tax(5000000_00, regime="OLD")
    above = calculate_income_tax(5000000_00 + 1, regime="OLD")
    assert below["surcharge_rate"] == 0
    assert at_50l["surcharge_rate"] == 0
    assert above["surcharge_rate"] == 10
    assert above["marginal_relief"] > 0
    assert above["base_tax"] + above["surcharge"] == at_50l["base_tax"] + 1


def test_new_regime_surcharge_is_zero_through_50_lakh_and_capped_at_25_percent():
    from engines.tax import calculate_income_tax
    assert calculate_income_tax(4900000_00, regime="NEW")["surcharge_rate"] == 0
    assert calculate_income_tax(50000000_00 + 1, regime="NEW")["surcharge_rate"] == 25


# ---- Validator ----

def test_gstin_valid():
    from connectors.document_upload.validator import validate_gstin
    assert validate_gstin("27AABCS1234A1Z5") is True


def test_gstin_invalid():
    from connectors.document_upload.validator import validate_gstin
    assert validate_gstin("INVALID") is False
    assert validate_gstin("") is False


def test_arithmetic_valid():
    from connectors.document_upload.validator import validate_arithmetic
    assert validate_arithmetic(10000, 900, 900, 0, 11800) is True


def test_arithmetic_invalid():
    from connectors.document_upload.validator import validate_arithmetic
    assert validate_arithmetic(10000, 900, 900, 0, 15000) is False


def test_date_valid():
    from connectors.document_upload.validator import validate_date_not_future
    assert validate_date_not_future("01/01/2024") is True


def test_date_future():
    from connectors.document_upload.validator import validate_date_not_future
    assert validate_date_not_future("01/01/2099") is False


# ---- Reconciliation Engine ----

def test_reconcile_exact_match():
    """Exact amount + similar name → AUTO_MATCHED."""
    from engines.reconcile import reconcile
    from models.schemas import ReconLine

    source = [ReconLine(id="s1", date="2024-01-01", description="Purchase", counterparty="Shree Traders", amount=1000000)]
    target = [ReconLine(id="t1", date="2024-01-01", description="B2B", counterparty="Shree Traders & Co", amount=1000000)]

    result = reconcile(source, target)
    assert result.summary.autoMatched == 1
    assert result.matches[0].status == "AUTO_MATCHED"


def test_reconcile_unmatched():
    """No matching target → UNMATCHED."""
    from engines.reconcile import reconcile
    from models.schemas import ReconLine

    source = [ReconLine(id="s1", date="2024-01-01", description="Purchase", counterparty="Alpha Corp", amount=1000000)]
    target = [ReconLine(id="t1", date="2024-01-01", description="B2B", counterparty="Zeta Industries", amount=5000000)]

    result = reconcile(source, target)
    assert result.summary.unmatched >= 1


def test_reconcile_keeps_gstr2b_only_entry_on_the_portal_side():
    from engines.reconcile import reconcile
    from models.schemas import ReconLine

    result = reconcile([], [ReconLine(
        id="portal-1", date="2024-01-01", description="GSTR-2B", counterparty="Supplier", amount=500000,
    )])
    match = result.matches[0]
    assert match.source is None
    assert match.target and match.target.id == "portal-1"
    assert match.flag == "PORTAL_ENTRY_NOT_IN_BOOKS"
