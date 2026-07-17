"""Small phase-10 checks for the money and file trust boundaries."""
from datetime import date

import pytest

from core.purchase_invoices.file_contract import UploadRejected, inspect_upload
from core.purchase_invoices.validation import validate_invoice, validation_state


def invoice(**changes):
    data = {
        "vendor_gstin": "27AAPFU0939F1ZV", "invoice_date": "2026-07-01",
        "taxable_amount_paise": 100_000, "cgst_paise": 9_000, "sgst_paise": 9_000,
        "igst_paise": 0, "other_charges_paise": 0, "total_paise": 118_000,
        "line_items": [{"qty": 1, "rate_paise": 100_000, "amount_paise": 100_000}],
        "currency": "INR",
    }
    return data | changes


def test_clean_invoice_passes_deterministic_validation():
    findings = validate_invoice(invoice(), today=date(2026, 7, 15))
    assert findings == []
    assert validation_state(findings) == "PASSED"


def test_ai_confidence_cannot_hide_tax_and_total_failures():
    findings = validate_invoice(invoice(cgst_paise=0, total_paise=117_000), today=date(2026, 7, 15))
    assert {item["code"] for item in findings} >= {"TOTAL_MISMATCH", "CGST_SGST_INCONSISTENT"}
    assert validation_state(findings) == "FAILED"


def test_place_of_supply_normalizes_state_names_and_never_guesses_unknown_text():
    # Supplier and client are both Maharashtra. The full state name is therefore
    # intra-state, not a false IGST exception caused by comparing text to "27".
    normalized = validate_invoice(invoice(
        client_gstin="27AAPFU0939F1ZV", place_of_supply_state="Maharashtra",
    ), today=date(2026, 7, 15))
    assert "IGST_REQUIRED" not in {item["code"] for item in normalized}

    unknown = validate_invoice(invoice(
        client_gstin="27AAPFU0939F1ZV", place_of_supply_state="Mars Colony",
    ), today=date(2026, 7, 15))
    assert "PLACE_OF_SUPPLY_INVALID" in {item["code"] for item in unknown}


def test_file_contract_uses_bytes_not_claimed_mime():
    upload = inspect_upload("invoice.pdf", "application/pdf", b"%PDF-1.7\n/Type /Page\n%%EOF")
    assert upload.file_type == "pdf" and upload.page_count == 1
    with pytest.raises(UploadRejected) as exc:
        inspect_upload("invoice.pdf", "application/pdf", b"not a pdf")
    assert exc.value.code == "UNSUPPORTED_FILE"


def test_password_protected_pdf_stops_in_quarantine():
    with pytest.raises(UploadRejected) as exc:
        inspect_upload("locked.pdf", "application/pdf", b"%PDF-1.7\n/Encrypt true\n%%EOF")
    assert exc.value.state == "PASSWORD_PROTECTED"
