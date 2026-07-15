"""Conservative GST component extraction from provider records.

# ponytail: use Zoho's stated components when present; unknown tax labels stay
# unverified instead of guessing an intra-state split.
"""
from __future__ import annotations
from typing import Any
from core.money import rupees_to_paise as paise


def extract_components(record: dict[str, Any]) -> dict[str, int | bool]:
    """Return component paise and whether the provider supplied a reconciling split."""
    taxes = record.get("taxes") or []
    total_tax = paise(record.get("tax_total", record.get("tax_total_amount", 0)))
    parts = {"igst_paise": 0, "cgst_paise": 0, "sgst_paise": 0, "cess_paise": 0}
    known = bool(taxes)
    for tax in taxes:
        label = " ".join(str(tax.get(key, "")) for key in ("tax_type", "tax_name", "tax_specification")).upper()
        amount = paise(tax.get("tax_amount", tax.get("amount", 0)))
        if "IGST" in label:
            parts["igst_paise"] += amount
        elif "CGST" in label:
            parts["cgst_paise"] += amount
        elif "SGST" in label or "UTGST" in label:
            parts["sgst_paise"] += amount
        elif "CESS" in label:
            parts["cess_paise"] += amount
        else:
            known = False
    parts["taxable_paise"] = paise(record.get("sub_total", record.get("subtotal", 0)))
    if not parts["taxable_paise"] and total_tax <= paise(record.get("total")):
        parts["taxable_paise"] = paise(record.get("total")) - total_tax
    parts["components_verified"] = known and sum(parts[key] for key in ("igst_paise", "cgst_paise", "sgst_paise", "cess_paise")) == total_tax
    return parts
