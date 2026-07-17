"""Deterministic Indian purchase-invoice validation; extraction cannot override it."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

GSTIN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GST_STATE_CODES = {
    "JAMMU AND KASHMIR": "01", "HIMACHAL PRADESH": "02", "PUNJAB": "03", "CHANDIGARH": "04",
    "UTTARAKHAND": "05", "HARYANA": "06", "DELHI": "07", "RAJASTHAN": "08", "UTTAR PRADESH": "09",
    "BIHAR": "10", "SIKKIM": "11", "ARUNACHAL PRADESH": "12", "NAGALAND": "13", "MANIPUR": "14",
    "MIZORAM": "15", "TRIPURA": "16", "MEGHALAYA": "17", "ASSAM": "18", "WEST BENGAL": "19",
    "JHARKHAND": "20", "ODISHA": "21", "CHHATTISGARH": "22", "MADHYA PRADESH": "23", "GUJARAT": "24",
    "DADRA AND NAGAR HAVELI AND DAMAN AND DIU": "26", "MAHARASHTRA": "27", "KARNATAKA": "29",
    "GOA": "30", "LAKSHADWEEP": "31", "KERALA": "32", "TAMIL NADU": "33", "PUDUCHERRY": "34",
    "ANDAMAN AND NICOBAR ISLANDS": "35", "TELANGANA": "36", "ANDHRA PRADESH": "37", "LADAKH": "38",
}
GST_STATE_ABBREVIATIONS = {
    "JK": "01", "HP": "02", "PB": "03", "CH": "04", "UK": "05", "HR": "06", "DL": "07", "RJ": "08",
    "UP": "09", "BR": "10", "SK": "11", "AR": "12", "NL": "13", "MN": "14", "MZ": "15", "TR": "16",
    "ML": "17", "AS": "18", "WB": "19", "JH": "20", "OD": "21", "CG": "22", "MP": "23", "GJ": "24",
    "DN": "26", "MH": "27", "KA": "29", "GA": "30", "LD": "31", "KL": "32", "TN": "33", "PY": "34",
    "AN": "35", "TS": "36", "AP": "37", "LA": "38",
}
GST_STATE_CODE_VALUES = frozenset(GST_STATE_CODES.values())


def _finding(code: str, message: str, field: str = "", severity: str = "ERROR", **details) -> dict:
    return {"code": code, "severity": severity, "field_key": field or None,
            "message": message, "details": details}


def _gstin_checksum(value: str) -> bool:
    if not GSTIN.fullmatch(value):
        return False
    factor, total = 2, 0
    for char in reversed(value[:-1]):
        product = factor * GST_CHARS.index(char)
        total += product // 36 + product % 36
        factor = 1 if factor == 2 else 2
    check = (36 - total % 36) % 36
    return GST_CHARS[check] == value[-1]


def validate_gstin(value: str) -> bool:
    """Compatibility-level format validation; invoice findings also enforce checksum."""
    return bool(GSTIN.fullmatch(str(value or "").strip().upper()))


def validate_arithmetic(taxable: int, cgst: int, sgst: int, igst: int, total: int) -> bool:
    return abs(taxable + cgst + sgst + igst - total) <= 100


def validate_date_not_future(value: str) -> bool:
    parsed = _invoice_date(value)
    return parsed is None or parsed <= date.today()


def compute_field_level(confidence: float, validation_passed: bool) -> str:
    if not validation_passed:
        return "LOW"
    return "HIGH" if confidence >= 0.85 else "REVIEW" if confidence >= 0.6 else "LOW"


def _invoice_date(value: object) -> date | None:
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _gst_state_code(value: object) -> str | None:
    """Normalize a GST state code, postal abbreviation, or full state name."""
    text = str(value or "").strip().upper()
    if text.isdigit() and len(text) <= 2:
        candidate = text.zfill(2)
        return candidate if candidate in GST_STATE_CODE_VALUES else None
    normalized = re.sub(r"[^A-Z]", " ", text)
    normalized = " ".join(normalized.split())
    return GST_STATE_ABBREVIATIONS.get(text) or GST_STATE_CODES.get(normalized)


def _money(data: dict, key: str) -> int:
    value = data.get(key, 0)
    if isinstance(value, bool):
        raise ValueError(key)
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(key) from exc


def validate_invoice(data: dict, *, tolerance_paise: int = 100, today: date | None = None) -> list[dict]:
    """Return stable findings for one canonical invoice expressed in paise."""
    findings: list[dict] = []
    supplier_gstin = str(data.get("vendor_gstin") or "").strip().upper()
    client_gstin = str(data.get("client_gstin") or "").strip().upper()
    if supplier_gstin and not _gstin_checksum(supplier_gstin):
        findings.append(_finding("GSTIN_INVALID", "Supplier GSTIN format or checksum is invalid.", "vendorGstin"))
    if client_gstin and not _gstin_checksum(client_gstin):
        findings.append(_finding("CLIENT_GSTIN_INVALID", "Client GSTIN format or checksum is invalid.", "clientGstin"))
    pan = str(data.get("vendor_pan") or (supplier_gstin[2:12] if len(supplier_gstin) == 15 else "")).upper()
    if pan and not PAN.fullmatch(pan):
        findings.append(_finding("PAN_INVALID", "Supplier PAN format is invalid.", "vendorPan"))

    parsed_date = _invoice_date(data.get("invoice_date"))
    current = today or date.today()
    if not parsed_date:
        findings.append(_finding("INVOICE_DATE_INVALID", "Use YYYY-MM-DD, DD/MM/YYYY, or DD-MM-YYYY.", "invoiceDate"))
    elif parsed_date > current:
        findings.append(_finding("INVOICE_DATE_FUTURE", "Invoice date cannot be in the future.", "invoiceDate"))
    elif (current - parsed_date).days > 366 * 8:
        findings.append(_finding("INVOICE_DATE_OLD", "Invoice is more than eight years old; confirm the period.", "invoiceDate", "WARNING"))

    try:
        taxable, cgst, sgst, igst = (_money(data, key) for key in (
            "taxable_amount_paise", "cgst_paise", "sgst_paise", "igst_paise"))
        other, total = _money(data, "other_charges_paise"), _money(data, "total_paise")
    except ValueError as exc:
        return findings + [_finding("MONEY_INVALID", "All monetary values must be integer paise.", str(exc))]
    expected = taxable + cgst + sgst + igst + other
    if abs(expected - total) > tolerance_paise:
        findings.append(_finding("TOTAL_MISMATCH", "Taxable value, taxes and charges do not equal the invoice total.",
                                 "total", expected_paise=expected, actual_paise=total, tolerance_paise=tolerance_paise))
    if (cgst == 0) != (sgst == 0) or abs(cgst - sgst) > tolerance_paise:
        findings.append(_finding("CGST_SGST_INCONSISTENT", "CGST and SGST must be paired and equal.", "cgst"))
    if igst and (cgst or sgst):
        findings.append(_finding("MIXED_GST_COMPONENTS", "Use IGST or CGST/SGST for one tax treatment, not both.", "igst"))
    if supplier_gstin and client_gstin:
        supplied_state = data.get("place_of_supply_state")
        if str(supplied_state or "").strip():
            supply_state = _gst_state_code(supplied_state)
            if not supply_state:
                findings.append(_finding(
                    "PLACE_OF_SUPPLY_INVALID",
                    "Use a recognised GST state name, abbreviation, or two-digit GST state code.",
                    "placeOfSupplyState",
                ))
        else:
            supply_state = client_gstin[:2]
        if supply_state:
            interstate = supplier_gstin[:2] != supply_state
            if interstate and not igst:
                findings.append(_finding("IGST_REQUIRED", "Interstate supply normally requires IGST.", "igst"))
            if not interstate and igst:
                findings.append(_finding("CGST_SGST_REQUIRED", "Intrastate supply normally requires CGST and SGST.", "igst"))

    lines = data.get("line_items") or []
    if not isinstance(lines, list) or not lines:
        findings.append(_finding("LINE_ITEMS_REQUIRED", "At least one purchase line is required.", "lineItems"))
    else:
        line_total = 0
        for index, line in enumerate(lines):
            try:
                quantity = Decimal(str(line.get("qty", 0)))
                rate = Decimal(str(line.get("rate_paise", line.get("rate", 0))))
                amount = Decimal(str(line.get("amount_paise", line.get("amount", 0))))
            except (InvalidOperation, AttributeError):
                findings.append(_finding("LINE_INVALID", f"Line {index + 1} has invalid numbers.", "lineItems"))
                continue
            if abs(quantity * rate - amount) > tolerance_paise:
                findings.append(_finding("LINE_ARITHMETIC_MISMATCH", f"Line {index + 1} quantity × rate does not equal amount.", "lineItems"))
            line_total += int(amount)
        if abs(line_total - taxable) > tolerance_paise:
            findings.append(_finding("LINE_TOTAL_MISMATCH", "Line amounts do not equal taxable value.", "lineItems",
                                     expected_paise=taxable, actual_paise=line_total))

    is_credit = str(data.get("document_type") or "").upper() == "CREDIT_NOTE"
    if (total < 0) != is_credit:
        findings.append(_finding("CREDIT_NOTE_SIGN", "Negative totals must be identified as a credit note.", "total"))
    if str(data.get("currency") or "INR").upper() != "INR":
        findings.append(_finding("CURRENCY_UNSUPPORTED", "Only INR purchase posting is currently certified.", "currency"))
    return findings


def validation_state(findings: list[dict]) -> str:
    return "FAILED" if any(item["severity"] == "ERROR" for item in findings) else (
        "WARNING" if findings else "PASSED"
    )
