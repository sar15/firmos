"""Bill extractor — stub that returns fixed shape until Phase 3 wires Gemini."""

from models.schemas import ExtractedField, LineItem
from core.money import parse_decimal, rupees_to_paise



def raw_to_extracted_fields(raw: dict, confidence: float = 0.5, is_sales: bool = False) -> list[ExtractedField]:
    """Convert raw extraction dict into ExtractedField list matching frontend schema."""
    from connectors.document_upload.validator import validate_gstin, validate_arithmetic, validate_date_not_future, compute_field_level

    field_map = [
        ("vendorName", "Customer Name" if is_sales else "Vendor Name", raw.get("vendor_name", "")),
        ("gstin", "Customer GSTIN" if is_sales else "Vendor GSTIN", raw.get("vendor_gstin", "")),
        ("invoiceNumber", "Invoice Number", raw.get("invoice_number", "")),
        ("invoiceDate", "Invoice Date", raw.get("invoice_date", "")),
        ("taxableAmount", "Taxable Amount", raw.get("taxable_amount", "0.00")),
        ("cgst", "CGST", raw.get("cgst", "0.00")),
        ("sgst", "SGST", raw.get("sgst", "0.00")),
        ("igst", "IGST", raw.get("igst", "0.00")),
        ("total", "Total Amount", raw.get("total", "0.00")),
        ("revenueHead", "Revenue Item", raw.get("revenue_item", "")) if is_sales else ("expenseHead", "Expense Head", raw.get("expense_head", "")),
    ]
    if is_sales:
        field_map.append(("placeOfSupply", "Place of Supply", raw.get("place_of_supply", "")))

    # Run deterministic validation
    gstin_valid = validate_gstin(raw.get("vendor_gstin", "")) if raw.get("vendor_gstin") else True
    try:
        arith_valid = validate_arithmetic(
            rupees_to_paise(raw.get("taxable_amount", 0)),
            rupees_to_paise(raw.get("cgst", 0)),
            rupees_to_paise(raw.get("sgst", 0)),
            rupees_to_paise(raw.get("igst", 0)),
            rupees_to_paise(raw.get("total", 0)),
        )
    except (ValueError, TypeError):
        arith_valid = False

    date_valid = validate_date_not_future(raw.get("invoice_date", "")) if raw.get("invoice_date") else True

    fields: list[ExtractedField] = []
    for key, label, value in field_map:
        # Per-field validation
        if key == "gstin":
            valid = gstin_valid
        elif key in ("taxableAmount", "cgst", "sgst", "igst", "total"):
            valid = arith_valid
        elif key == "invoiceDate":
            valid = date_valid
        else:
            valid = True

        level = compute_field_level(confidence, valid)
        if key in ("expenseHead", "revenueHead") and raw.get("expense_head_confidence") == "LOW":
            level = "LOW"
            
        fields.append(ExtractedField(
            key=key,
            label=label,
            value=str(value),
            confidence=confidence if valid else min(confidence, 0.4),
            level=level,
        ))

    return fields


def raw_to_line_items(raw_items: list[dict]) -> list[LineItem]:
    """Convert raw line items to LineItem models."""
    items = []
    for item in raw_items:
        items.append(LineItem(
            desc=item.get("desc", ""),
            hsn=item.get("hsn"),
            qty=parse_decimal(item.get("qty", 0)),
            rate=int(item["rate_paise"]) if "rate_paise" in item else rupees_to_paise(item.get("rate", 0)),
            amount=int(item["amount_paise"]) if "amount_paise" in item else rupees_to_paise(item.get("amount", 0)),
        ))
    return items
