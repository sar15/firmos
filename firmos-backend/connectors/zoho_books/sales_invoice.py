"""Deterministic Zoho sales-invoice payload and read-back comparison."""
from dataclasses import dataclass
import hashlib
import json

from connectors.platform.types import CanonicalObject


@dataclass(frozen=True)
class SalesInvoiceRequest:
    payload: dict
    request_hash: str


def build_sales_invoice(data: dict) -> SalesInvoiceRequest:
    required = ("organization_id", "customer_id", "invoice_number", "date", "place_of_supply", "line_items")
    if any(not data.get(key) for key in required) or not isinstance(data["line_items"], list):
        raise ValueError("Sales invoice needs customer, number, date, place of supply and lines")
    lines = []
    for line in data["line_items"]:
        if not (line.get("item_id") or line.get("account_id")) or not line.get("tax_id"):
            raise ValueError("Every sales line needs income/item and tax mappings")
        rate = int(line.get("rate_paise", 0))
        if rate <= 0:
            raise ValueError("Every sales line needs a positive rate")
        lines.append({key: value for key, value in {
            "item_id": line.get("item_id"), "account_id": line.get("account_id"),
            "tax_id": line.get("tax_id"), "description": line.get("description", ""),
            "quantity": line.get("quantity", 1), "rate": f"{rate / 100:.2f}",
        }.items() if value not in (None, "")})
    payload = {
        "customer_id": str(data["customer_id"]), "invoice_number": str(data["invoice_number"]),
        "date": str(data["date"]), "place_of_supply": str(data["place_of_supply"]),
        "line_items": lines, "reference_number": str(data.get("reference_number") or ""),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return SalesInvoiceRequest(payload, hashlib.sha256(encoded).hexdigest())


def compare_sales_invoice(expected: dict, actual: CanonicalObject, organization_id: str) -> dict:
    wanted = {
        "organization_id": organization_id, "customer_id": str(expected.get("customer_id") or ""),
        "invoice_number": str(expected.get("invoice_number") or ""), "date": str(expected.get("date") or ""),
        "place_of_supply": str(expected.get("place_of_supply") or ""),
    }
    mismatches = {key: {"expected": value, "actual": actual.values.get(key)}
                  for key, value in wanted.items() if value != actual.values.get(key)}
    if expected.get("total_paise") is not None and int(expected["total_paise"]) != actual.values.get("total_paise"):
        mismatches["total_paise"] = {"expected": int(expected["total_paise"]),
                                     "actual": actual.values.get("total_paise")}
    return mismatches
