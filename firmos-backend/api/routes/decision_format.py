"""Decision presentation and deterministic computation helpers."""
from datetime import date

from models.schemas import Decision


def map_kind(flag: str) -> str:
    value = (flag or "").lower()
    if "tds" in value:
        return "TDS_DEFAULT"
    if "asmt" in value or "notice" in value:
        return "GST_NOTICE"
    if "mismatch" in value or "recon" in value:
        return "RECONCILIATION"
    return "GSTR_APPROVAL"


def map_urgency(value: str) -> str:
    if (value or "").lower() in {"high", "critical", "needs_you_now"}:
        return "NEEDS_YOU_NOW"
    if (value or "").lower() in {"medium", "due_today", "today"}:
        return "DUE_TODAY"
    return "THIS_WEEK"


def as_decision(row, confidence: float | None = None, recommendation: str | None = None) -> Decision:
    stored_recommendation = row.get("recommendation")
    return Decision(
        id=row["id"], clientId=row.get("client_id", "unknown"), kind=map_kind(row.get("flag", "")),
        title=f"Pending Decision: {row['flag'] or row['document_id']}",
        firmOsRecommendation=recommendation or stored_recommendation or "Human review required for workflow continuation.",
        urgency=map_urgency(row["urgency"]), amountAtStake={"paise": row["amount"], "currency": "INR"},
        dueDate=row["created_at"].isoformat() + "Z", confidence=confidence if confidence is not None else (0.8 if stored_recommendation else 0.0),
    )


def enrich_context_with_math(flag: str, amount_paise: int, context_data: dict, evidence: list) -> None:
    if "tds" in flag and amount_paise:
        from engines.tds import calculate_tds

        section = next((item for item in ("194A", "194C", "194H", "194I", "194J_TECH", "194J_PROF", "194Q") if item.lower() in flag), "194J_PROF")
        result = calculate_tds(section=section, gross_amount_paise=amount_paise)
        context_data["tds_computation"] = result
        evidence.append({"source": "engines/tds.py", "data": result})
    if "interest" in flag or "234" in flag:
        from engines.interest import calculate_234b_interest

        result = calculate_234b_interest(
            total_tax_paise=amount_paise,
            advance_tax_paid_paise=0,
            assessment_year_end=date(2027, 3, 31),
            actual_filing_date=date.today(),
        )
        context_data["interest_computation"] = result
        evidence.append({"source": "engines/interest.py", "data": result})
