"""Canonical Tally purchase voucher validation and read-back comparison."""
from datetime import date


def validate_purchase(payload: dict) -> dict:
    required = ("tally_company", "company_guid", "party_ledger", "purchase_ledger")
    if any(not str(payload.get(key) or "").strip() for key in required):
        raise ValueError("Tally company, company GUID, party, and purchase ledger are required")
    try:
        parsed = date.fromisoformat(str(payload["date"]))
    except (KeyError, ValueError) as exc:
        raise ValueError("Tally purchase date must be YYYY-MM-DD") from exc
    total = int(payload.get("total_paise", 0))
    if total <= 0:
        raise ValueError("Tally purchase total must be positive integer paise")
    if str(payload["party_ledger"]).strip() == str(payload["purchase_ledger"]).strip():
        raise ValueError("Party and purchase ledgers must be different")
    entries = payload.get("entries") or [
        {"ledger_name": str(payload["party_ledger"]), "amount_paise": total},
        {"ledger_name": str(payload["purchase_ledger"]), "amount_paise": -total},
    ]
    entries = [{
        "ledger_name": str(line.get("ledger_name") or line.get("ledger") or "").strip(),
        "amount_paise": int(line.get("amount_paise", 0)),
    } for line in entries]
    if any(not line["ledger_name"] or not line["amount_paise"] for line in entries):
        raise ValueError("Every Tally entry requires a ledger and non-zero integer paise")
    if sum(line["amount_paise"] for line in entries) != 0:
        raise ValueError("Tally purchase entries must balance to zero paise")
    names = {line["ledger_name"] for line in entries}
    if not {str(payload["party_ledger"]), str(payload["purchase_ledger"])}.issubset(names):
        raise ValueError("Tally purchase entries must include party and purchase ledgers")
    currency = str(payload.get("currency") or "INR").upper()
    if currency != "INR":
        raise ValueError("Tally V1 supports INR purchase vouchers only")
    gst_details = [{
        "ledger_name": str(item.get("ledger_name") or "").strip(),
        "tax_type": str(item.get("tax_type") or "").strip().upper(),
        "amount_paise": int(item.get("amount_paise", 0)),
    } for item in payload.get("gst_details") or []]
    allowed_taxes = {"CGST", "SGST", "IGST", "CESS"}
    if any(not item["ledger_name"] or item["tax_type"] not in allowed_taxes
           or not item["amount_paise"] for item in gst_details):
        raise ValueError("Every GST detail requires a GST ledger, supported tax type, and paise")
    entry_values = {(line["ledger_name"], line["amount_paise"]) for line in entries}
    if any((item["ledger_name"], item["amount_paise"]) not in entry_values for item in gst_details):
        raise ValueError("Every GST detail must match a balanced voucher ledger entry")
    tax_total = int(payload.get("tax_total_paise", sum(abs(item["amount_paise"]) for item in gst_details)))
    if tax_total != sum(abs(item["amount_paise"]) for item in gst_details):
        raise ValueError("Tally GST total does not match the GST ledger entries")
    return {
        "date": parsed.strftime("%Y%m%d"),
        "company_guid": str(payload["company_guid"]),
        "company_name": str(payload["tally_company"]),
        "party_ledger": str(payload["party_ledger"]),
        "purchase_ledger": str(payload["purchase_ledger"]),
        "total_paise": total,
        "narration": str(payload.get("narration") or ""),
        "reference": str(payload.get("reference") or ""),
        "currency": currency,
        "entries": entries,
        "voucher_number": str(payload.get("voucher_number") or ""),
        "gst_details": gst_details,
        "tax_total_paise": tax_total,
    }


def deterministic_remote_id(action_id: str) -> str:
    return f"firmos:{action_id}"


def validate_sales(payload: dict) -> dict:
    required=("company_name","company_guid","party_ledger","sales_ledger")
    if any(not str(payload.get(key) or "").strip() for key in required):
        raise ValueError("Tally company, GUID, customer and sales ledger are required")
    raw_date=str(payload.get("date") or "")
    if len(raw_date)!=8 or not raw_date.isdigit():raise ValueError("Tally sales date must be YYYYMMDD")
    total=int(payload.get("total_paise",0));entries=payload.get("entries") or []
    if total<=0:raise ValueError("Tally sales total must be positive paise")
    normalized=[{"ledger_name":str(x.get("ledger_name") or "").strip(),"amount_paise":int(x.get("amount_paise",0))} for x in entries]
    if any(not x["ledger_name"] or not x["amount_paise"] for x in normalized) or sum(x["amount_paise"] for x in normalized)!=0:
        raise ValueError("Tally sales entries need named, non-zero, balanced ledgers")
    names={x["ledger_name"] for x in normalized}
    if not {payload["party_ledger"],payload["sales_ledger"]}.issubset(names):raise ValueError("Sales entries must include customer and income ledgers")
    return {"date":raw_date,"company_guid":str(payload["company_guid"]),"company_name":str(payload["company_name"]),
            "party_ledger":str(payload["party_ledger"]),"sales_ledger":str(payload["sales_ledger"]),
            "total_paise":total,"reference":str(payload.get("reference") or ""),
            "narration":str(payload.get("narration") or ""),"voucher_number":str(payload.get("voucher_number") or ""),
            "entries":normalized,"tax_total_paise":int(payload.get("tax_total_paise",0))}


def compare_sales(expected:dict,actual:dict,remote_id:str)->dict:
    wanted=validate_sales(expected);checks={"remote_id":remote_id,"company_guid":wanted["company_guid"],
      "voucher_type":"Sales","date":wanted["date"],"party_ledger":wanted["party_ledger"],"total_paise":wanted["total_paise"]}
    for key in ("reference","narration","voucher_number"):
        if wanted[key]:checks[key]=wanted[key]
    mismatches={key:{"expected":value,"actual":actual.get(key)} for key,value in checks.items() if str(actual.get(key) or "")!=str(value)}
    expected_entries=sorted((x["ledger_name"],x["amount_paise"]) for x in wanted["entries"])
    actual_entries=sorted((str(x.get("ledger_name") or ""),int(x.get("amount_paise",0))) for x in actual.get("entries") or [])
    if expected_entries!=actual_entries:mismatches["entries"]={"expected":expected_entries,"actual":actual_entries}
    return mismatches


def compare_purchase(expected: dict, actual: dict, remote_id: str) -> dict:
    wanted = validate_purchase(expected)
    checks = {
        "remote_id": remote_id,
        "company_guid": wanted["company_guid"],
        "voucher_type": "Purchase",
        "date": wanted["date"],
        "party_ledger": wanted["party_ledger"],
        "total_paise": wanted["total_paise"],
    }
    if wanted["reference"]:
        checks["reference"] = wanted["reference"]
    if wanted["narration"]:
        checks["narration"] = wanted["narration"]
    if wanted["voucher_number"]:
        checks["voucher_number"] = wanted["voucher_number"]
    mismatches = {
        key: {"expected": value, "actual": actual.get(key)}
        for key, value in checks.items()
        if str(actual.get(key) or "") != str(value)
    }
    entries = actual.get("entries") or []
    expected_entries = sorted(
        (line["ledger_name"], int(line["amount_paise"])) for line in wanted["entries"]
    )
    actual_entries = sorted(
        (str(line.get("ledger_name") or ""), int(line.get("amount_paise", 0))) for line in entries
    )
    if actual_entries != expected_entries:
        mismatches["entries"] = {"expected": expected_entries, "actual": actual_entries}
    expected_gst = sorted(
        (item["ledger_name"], item["tax_type"], item["amount_paise"])
        for item in wanted["gst_details"]
    )
    actual_gst = sorted(
        (str(item.get("ledger_name") or ""), str(item.get("tax_type") or "").upper(),
         int(item.get("amount_paise", 0))) for item in actual.get("gst_details") or []
    )
    if actual_gst != expected_gst:
        mismatches["gst_details"] = {"expected": expected_gst, "actual": actual_gst}
    return mismatches
