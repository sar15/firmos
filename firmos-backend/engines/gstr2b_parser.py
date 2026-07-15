"""Strict Decimal/paise parser for official GSTR-2B JSON and Excel exports."""
from __future__ import annotations

from datetime import datetime
import hashlib
import io
import re
from typing import Any, Iterable

from core.errors import AppError
from core.money import MoneyParseError, rupees_to_paise
from engines.gstr2b_types import Gstr2bDocument, Gstr2bParseResult

PARSER_VERSION = "gstr2b-v2"
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z0-9]{13}$")


def _clean_gstin(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _invoice_number(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _date(value: Any):
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime().date()
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value.date() if hasattr(value, "date") else value
    text = str(value or "").strip()
    for pattern in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise AppError("INVALID_GSTR2B_DATE", f"Unsupported invoice date: {text}", status_code=422)


def _paise(value: Any) -> int:
    try:
        return rupees_to_paise(value or 0)
    except MoneyParseError as exc:
        raise AppError("INVALID_GSTR2B_AMOUNT", "A GSTR-2B amount is not a valid decimal value.", status_code=422) from exc


def _identity(gstin: str, number: str, invoice_date, document_type: str) -> str:
    raw = f"{gstin}|{number}|{invoice_date.isoformat()}|{document_type}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _taxes(items: Iterable[dict[str, Any]]) -> tuple[int, int, int, int, int]:
    taxable = igst = cgst = sgst = cess = 0
    for item in items:
        detail = item.get("itm_det", item)
        taxable += _paise(detail.get("txval"))
        igst += _paise(detail.get("iamt"))
        cgst += _paise(detail.get("camt"))
        sgst += _paise(detail.get("samt"))
        cess += _paise(detail.get("csamt"))
    return taxable, igst, cgst, sgst, cess


def _document(supplier: dict[str, Any], raw: dict[str, Any], section: str) -> Gstr2bDocument:
    gstin = _clean_gstin(supplier.get("ctin") or raw.get("gstin"))
    number = str(raw.get("inum") or raw.get("ntnum") or raw.get("invoice_number") or "").strip()
    normalized_number = _invoice_number(number)
    invoice_date = _date(raw.get("idt") or raw.get("ntdt") or raw.get("invoice_date"))
    doc_type = {
        "b2b": "INVOICE", "b2ba": "INVOICE", "cdnr": "CREDIT_NOTE", "cdnra": "CREDIT_NOTE",
    }.get(section, str(raw.get("document_type") or "IMPORT").upper())
    if not GSTIN_PATTERN.match(gstin) or not normalized_number:
        raise AppError("INVALID_GSTR2B_DOCUMENT", "A supplier GSTIN or invoice number is missing/invalid.", status_code=422)
    taxable, igst, cgst, sgst, cess = _taxes(raw.get("itms", []))
    total = _paise(raw.get("val") or raw.get("invoice_value"))
    original_number = _invoice_number(raw.get("oinum") or raw.get("ont_num"))
    amendment_key = _identity(gstin, original_number, _date(raw.get("oidt") or raw.get("ont_dt")), doc_type) if original_number else None
    return Gstr2bDocument(
        identity_key=_identity(gstin, normalized_number, invoice_date, doc_type), supplier_gstin=gstin,
        invoice_number=number, invoice_date=invoice_date, document_type=doc_type,
        amendment_of_key=amendment_key, taxable_paise=taxable, igst_paise=igst, cgst_paise=cgst,
        sgst_paise=sgst, cess_paise=cess, total_paise=total, original={"section": section, **raw},
    )


def _unwrap(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AppError("INVALID_GSTR2B_SCHEMA", "The uploaded file is not a JSON object.", status_code=422)
    data = payload.get("data", payload)
    return data.get("docdata", data) if isinstance(data, dict) else {}


def parse_gstr2b_json(payload: dict[str, Any]) -> Gstr2bParseResult:
    docdata = _unwrap(payload)
    documents: list[Gstr2bDocument] = []
    counts: dict[str, int] = {}
    for section, child in (("b2b", "inv"), ("b2ba", "inv"), ("cdnr", "nt"), ("cdnra", "nt")):
        for supplier in docdata.get(section, []) or []:
            for raw in supplier.get(child, []) or []:
                documents.append(_document(supplier, raw, section))
                counts[section] = counts.get(section, 0) + 1
    if not documents:
        raise AppError("EMPTY_GSTR2B", "No supported invoices or notes were found in this GSTR-2B file.", status_code=422)
    gstin = _clean_gstin(payload.get("gstin") or docdata.get("gstin") or docdata.get("ctin"))
    period = str(payload.get("rtnprd") or payload.get("return_period") or docdata.get("rtnprd") or "")
    totals = {
        "taxable_paise": sum(d.taxable_paise for d in documents),
        "tax_paise": sum(d.igst_paise + d.cgst_paise + d.sgst_paise + d.cess_paise for d in documents),
        "total_paise": sum(d.total_paise for d in documents),
    }
    return Gstr2bParseResult(gstin, period, PARSER_VERSION, tuple(documents), counts, totals)


def parse_gstr2b_excel(content: bytes) -> Gstr2bParseResult:
    import pandas as pd
    try:
        frame = pd.read_excel(io.BytesIO(content))
    except Exception as exc:
        raise AppError("CORRUPT_GSTR2B_FILE", "The Excel export could not be read.", status_code=422) from exc
    frame.columns = [str(column).strip().lower().replace(" ", "_") for column in frame.columns]
    rows = frame.where(frame.notna(), None).to_dict("records")
    payload = {"return_period": next((r.get("return_period") for r in rows if r.get("return_period")), ""), "docdata": {"b2b": []}}
    suppliers: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        gstin = _clean_gstin(row.get("gstin") or row.get("supplier_gstin"))
        suppliers.setdefault(gstin, []).append({
            "inum": row.get("invoice_number"), "idt": row.get("invoice_date"), "val": row.get("invoice_value"),
            "itms": [{"txval": row.get("taxable_value"), "iamt": row.get("igst"), "camt": row.get("cgst"), "samt": row.get("sgst"), "csamt": row.get("cess")}],
        })
    payload["docdata"]["b2b"] = [{"ctin": gstin, "inv": invoices} for gstin, invoices in suppliers.items()]
    return parse_gstr2b_json(payload)
