"""Validated immutable Zoho purchase-bill request builder."""
from dataclasses import dataclass
import hashlib
import json

from connectors.zoho_books.models import ZohoBillCreate


@dataclass(frozen=True)
class PurchaseBillRequest:
    payload: dict
    request_hash: str


def build_purchase_bill(canonical: dict) -> PurchaseBillRequest:
    if canonical.get("currency_code", "INR") != "INR":
        raise ValueError("Zoho V1 purchase bills require INR currency")
    if not canonical.get("organization_id"):
        raise ValueError("organization_id is required")
    if not str(canonical.get("reference_number") or "").strip():
        raise ValueError("reference_number is required for exactly-once recovery")
    lines = canonical.get("line_items") or []
    calculated_subtotal = sum(
        int(line.get("rate_paise", 0)) * int(line.get("quantity", 1)) for line in lines
    )
    if calculated_subtotal <= 0 or int(canonical.get("subtotal_paise", calculated_subtotal)) != calculated_subtotal:
        raise ValueError("line totals must equal subtotal_paise")
    if "total_paise" not in canonical:
        raise ValueError("total_paise is required")
    tax_total = int(canonical.get("tax_total_paise", 0))
    if int(canonical["total_paise"]) != calculated_subtotal + tax_total:
        raise ValueError("subtotal plus tax must equal total_paise")
    if tax_total and any(not line.get("tax_id") for line in lines):
        raise ValueError("every taxed line requires an approved tax mapping")
    model = ZohoBillCreate.from_dict(canonical)
    payload = model.to_zoho_json()
    payload["currency_code"] = "INR"
    payload["reference_number"] = str(canonical["reference_number"])
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return PurchaseBillRequest(payload, hashlib.sha256(encoded).hexdigest())
