"""Sales-specific checks using the proven invoice validation boundary."""
from core.purchase_invoices.validation import validate_invoice


def validate_sales_invoice(data: dict) -> list[dict]:
    """Validate sales fields without duplicating extraction or money rules."""
    canonical = dict(data)
    canonical["vendor_gstin"] = data.get("seller_gstin")
    canonical["client_gstin"] = data.get("customer_gstin")
    canonical["place_of_supply_state"] = data.get("place_of_supply_state")
    findings = validate_invoice(canonical)
    required = {
        "customer_name": "Customer is required.",
        "invoice_number": "Invoice number is required.",
        "place_of_supply_state": "Place of supply is required.",
    }
    for key, message in required.items():
        if not str(data.get(key) or "").strip():
            findings.append({"code": f"{key.upper()}_REQUIRED", "severity": "ERROR",
                             "field_key": key, "message": message, "details": {}})
    return findings
