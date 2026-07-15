"""Zoho payloads mapped into stable financial objects using integer paise."""
from decimal import Decimal
import re

from connectors.platform.types import CanonicalObject
from core.money import rupees_to_paise

GSTIN = re.compile(r"^[0-9]{2}[A-Z0-9]{13}$")


def normalize_gstin(value: object) -> str | None:
    normalized = re.sub(r"\s+", "", str(value or "")).upper()
    return normalized if GSTIN.fullmatch(normalized) else None


def _paise(value: object) -> int:
    return rupees_to_paise(str(value or "0"))


def _line(line: dict) -> dict:
    quantity = Decimal(str(line.get("quantity") or 1))
    return {
        "item_id": str(line.get("item_id") or ""),
        "account_id": str(line.get("account_id") or ""),
        "tax_id": str(line.get("tax_id") or ""),
        "description": str(line.get("description") or line.get("name") or ""),
        "quantity": str(quantity),
        "rate_paise": _paise(line.get("rate")),
        "line_total_paise": _paise(line.get("item_total") or line.get("line_item_total")),
        "tax_total_paise": _paise(line.get("tax_amount")),
        "igst_paise": _paise(line.get("igst_amount")),
        "cgst_paise": _paise(line.get("cgst_amount")),
        "sgst_paise": _paise(line.get("sgst_amount")),
        "cess_paise": _paise(line.get("cess_amount")),
    }


def map_bill(payload: dict, organization_id: str) -> CanonicalObject:
    return CanonicalObject("purchase_bill", str(payload.get("bill_id") or ""), {
        "organization_id": organization_id,
        "vendor_id": str(payload.get("vendor_id") or ""),
        "vendor_name": str(payload.get("vendor_name") or ""),
        "vendor_gstin": normalize_gstin(payload.get("gst_no") or payload.get("gstin")),
        "bill_number": str(payload.get("bill_number") or ""),
        "reference_number": str(payload.get("reference_number") or ""),
        "date": str(payload.get("date") or ""),
        "currency": str(payload.get("currency_code") or "INR"),
        "status": str(payload.get("status") or ""),
        "place_of_supply": str(payload.get("source_of_supply") or ""),
        "reverse_charge": bool(payload.get("is_reverse_charge_applied", False)),
        "subtotal_paise": _paise(payload.get("sub_total")),
        "tax_total_paise": _paise(payload.get("tax_total")),
        "total_paise": _paise(payload.get("total")),
        "line_items": [_line(line) for line in payload.get("line_items", [])],
    }, str(payload.get("last_modified_time") or "") or None)


def map_invoice(payload: dict, organization_id: str) -> CanonicalObject:
    mapped = map_bill(payload, organization_id)
    values = dict(mapped.values)
    values["customer_id"] = str(payload.get("customer_id") or "")
    values["customer_name"] = str(payload.get("customer_name") or "")
    values["customer_gstin"] = normalize_gstin(payload.get("gst_no") or payload.get("gstin"))
    values["invoice_number"] = str(payload.get("invoice_number") or "")
    values["place_of_supply"] = str(payload.get("place_of_supply") or payload.get("source_of_supply") or "")
    values["e_invoice"] = {
        key: payload[key] for key in ("irn", "ack_no", "ack_date", "ewaybill_number") if payload.get(key)
    }
    return CanonicalObject("sales_invoice", str(payload.get("invoice_id") or ""), values, mapped.provider_version)


def compare_bill(expected: dict, actual: CanonicalObject, organization_id: str) -> dict:
    wanted = {
        "organization_id": organization_id,
        "vendor_id": str(expected.get("vendor_id") or ""),
        "bill_number": str(expected.get("bill_number") or ""),
        "reference_number": str(expected.get("reference_number") or ""),
        "date": str(expected.get("date") or ""),
        "currency": str(expected.get("currency_code") or "INR"),
    }
    mismatches = {key: {"expected": value, "actual": actual.values.get(key)} for key, value in wanted.items() if value != actual.values.get(key)}
    expected_lines = expected.get("line_items", [])
    actual_lines = actual.values.get("line_items", [])
    if len(expected_lines) != len(actual_lines):
        mismatches["line_items.count"] = {"expected": len(expected_lines), "actual": len(actual_lines)}
    for index, line in enumerate(expected_lines[:len(actual_lines)]):
        for key in ("account_id", "item_id", "tax_id"):
            if str(line.get(key) or "") != actual_lines[index].get(key):
                mismatches[f"line_items.{index}.{key}"] = {"expected": line.get(key), "actual": actual_lines[index].get(key)}
        expected_rate = int(line["rate_paise"]) if "rate_paise" in line else _paise(line.get("rate"))
        if expected_rate != actual_lines[index].get("rate_paise"):
            mismatches[f"line_items.{index}.rate_paise"] = {"expected": expected_rate, "actual": actual_lines[index].get("rate_paise")}
        if str(line.get("quantity", 1)) != str(actual_lines[index].get("quantity")):
            mismatches[f"line_items.{index}.quantity"] = {
                "expected": str(line.get("quantity", 1)), "actual": actual_lines[index].get("quantity"),
            }
    for key in ("subtotal_paise", "tax_total_paise", "total_paise"):
        if expected.get(key) is not None and int(expected[key]) != actual.values.get(key):
            mismatches[key] = {"expected": int(expected[key]), "actual": actual.values.get(key)}
    if expected.get("expected_status") and expected["expected_status"] != actual.values.get("status"):
        mismatches["status"] = {"expected": expected["expected_status"], "actual": actual.values.get("status")}
    return mismatches
