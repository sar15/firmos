"""Unit tests for firmos-bridge local Tally XML builder and response parser.

# ponytail: Runnable tests verifying local bridge XML generation and response safeguards.
"""
import sys
import os

# Add firmos-bridge directory to path so we can import tally_client
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../firmos-bridge")))

from tally_client import build_purchase_voucher_xml, parse_tally_import_response


def test_build_purchase_voucher_xml():
    payload = {
        "date": "20260630",
        "party_ledger": "Acme Suppliers & Co",
        "purchase_ledger": "Purchase @ 18%",
        "narration": "Invoice INV-001",
        "total_paise": 1180000,
    }
    xml = build_purchase_voucher_xml(payload, remote_id="action-uuid-1", company_name="Acme Trading Ltd")

    assert "REMOTEID=\"action-uuid-1\"" in xml
    assert "<SVCURRENTCOMPANY>Acme Trading Ltd</SVCURRENTCOMPANY>" in xml
    assert "<PARTYLEDGERNAME>Acme Suppliers &amp; Co</PARTYLEDGERNAME>" in xml
    assert "<AMOUNT>11800.00</AMOUNT>" in xml
    assert "<AMOUNT>-11800.00</AMOUNT>" in xml


def test_parse_tally_import_response_safeguards():
    # 1. Success response with CREATED > 0
    success_xml = "<RESPONSE><CREATED>1</CREATED><ERRORS>0</ERRORS></RESPONSE>"
    res_success = parse_tally_import_response(success_xml)
    assert res_success["status"] == "SUCCEEDED"
    assert res_success["created_count"] == 1

    # 2. Ambiguous response (0 created, 0 error) returns NEEDS_REVIEW, never SUCCEEDED
    ambiguous_xml = "<RESPONSE><CREATED>0</CREATED></RESPONSE>"
    res_ambiguous = parse_tally_import_response(ambiguous_xml)
    assert res_ambiguous["status"] == "NEEDS_REVIEW"

    # 3. Line error returns FAILED
    error_xml = "<RESPONSE><LINEERROR>Ledger 'Acme' does not exist</LINEERROR></RESPONSE>"
    res_error = parse_tally_import_response(error_xml)
    assert res_error["status"] == "FAILED"
    assert "Ledger 'Acme' does not exist" in res_error["error"]
