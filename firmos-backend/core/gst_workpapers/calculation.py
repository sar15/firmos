"""Turn verified registers and 2B/IMS decisions into reviewable GST rows."""
import hashlib
from collections import defaultdict

COMPONENTS = ("taxable_paise", "igst_paise", "cgst_paise", "sgst_paise", "cess_paise")
INELIGIBLE = ("INELIGIBLE", "BLOCKED", "17_5", "17(5)")
REVERSAL = ("REVERSAL", "REVERSED", "RULE_38", "RULE_42", "RULE_43")


def _amounts(row: dict) -> dict[str, int]:
    return {key: int(row.get(key) or 0) for key in COMPONENTS}


def _source(row: dict, table: str, kind: str, treatment: str) -> dict:
    version=str(row.get("source_version") or "1")
    if kind=="PURCHASE_REGISTER":
        decision="|".join(str(row.get(key) or "") for key in ("match_decision","ims_decision","itc_classification","reverse_charge"))
        version+=":"+hashlib.sha256(decision.encode()).hexdigest()[:12]
    return {
        "table_key": table,
        "source_kind": kind,
        "source_id": str(row["id"]),
        "source_version": version,
        "amount_paise": int(row.get("taxable_paise") or 0),
        "treatment": treatment,
        "details": {**_amounts(row), **{key: row.get(key) for key in (
            "customer_gstin", "place_of_supply", "reverse_charge", "itc_classification",
            "match_decision", "ims_decision", "document_type",
        ) if key in row}},
    }


def _itc_table(row: dict) -> tuple[str, str, str | None]:
    classification = str(row.get("itc_classification") or "").upper()
    match, ims = str(row.get("match_decision") or ""), str(row.get("ims_decision") or "")
    if any(label in classification for label in REVERSAL):
        return "4(B) ITC reversed", "REVIEWER_ADJUSTED", None
    if any(label in classification for label in INELIGIBLE) or match == "REJECTED" or ims == "REJECT":
        return "4(D) Ineligible ITC", "IMPORTED" if match else "SYSTEM_CALCULATED", None
    if ims == "PENDING" or match in ("", "PENDING"):
        return "4(D) Ineligible ITC", "IMPORTED" if match else "SYSTEM_CALCULATED", "ITC_DECISION_REQUIRED"
    if row.get("reverse_charge"):
        if "RCM_PAID" in classification:
            return "4(A)(3) RCM ITC", "REVIEWER_ADJUSTED", None
        return "4(D) Ineligible ITC", "SYSTEM_CALCULATED", "RCM_PAYMENT_EVIDENCE_REQUIRED"
    return "4(A)(5) Other ITC", "IMPORTED", None


def build_source_rows(sales: list[dict], purchases: list[dict], return_type: str) -> tuple[list[dict], list[dict]]:
    rows, exceptions = [], []
    for sale in sales:
        table = "GSTR-1 B2B" if sale.get("customer_gstin") else "GSTR-1 B2C"
        rows.append(_source(sale, table if return_type == "GSTR1" else "3.1(a) Outward taxable", "SALES_REGISTER", "SYSTEM_CALCULATED"))
    if return_type == "GSTR1":
        return rows, exceptions
    for purchase in purchases:
        if purchase.get("reverse_charge"):
            rows.append(_source(purchase, "3.1(d) Reverse charge", "PURCHASE_REGISTER", "SYSTEM_CALCULATED"))
        table, treatment, warning = _itc_table(purchase)
        rows.append(_source(purchase, table, "PURCHASE_REGISTER", treatment))
        if warning:
            exceptions.append({"code": warning, "source_id": str(purchase["id"]), "message": "Review the purchase and its 2B/IMS evidence before claiming ITC."})
    return rows, exceptions


def summarize_tables(rows: list[dict], adjustments: list[dict]) -> dict:
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {key: 0 for key in COMPONENTS})
    source_totals: dict[str, int] = defaultdict(int)
    adjustment_totals: dict[str, int] = defaultdict(int)
    for row in rows:
        source_totals[row["table_key"]] += int(row.get("amount_paise") or 0)
        details = row.get("details") or {"taxable_paise": row.get("amount_paise") or 0}
        for key in COMPONENTS:
            totals[row["table_key"]][key] += int(details.get(key) or 0)
    for item in adjustments:
        table = str(item.get("table_key") or "Adjustments")
        component = str(item.get("component") or "taxable_paise")
        if component not in COMPONENTS:
            raise ValueError(f"Unsupported GST component: {component}")
        amount = int(item.get("amount_paise") or 0)
        totals[table][component] += amount
        adjustment_totals[table] += amount
    return {table: {**values, "source_total_paise": source_totals[table],
                    "adjustment_paise": adjustment_totals[table],
                    "total_paise": source_totals[table] + adjustment_totals[table]}
            for table, values in totals.items()}
