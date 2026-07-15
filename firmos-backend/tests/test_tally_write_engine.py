"""Unit tests for OSS-Grounded Tally Write Engine."""

import pytest
from connectors.tally.write_engine import (
    build_import_data_envelope,
    parse_import_response,
    assert_write_permitted,
    TallyWriteError,
)


def test_assert_write_permitted():
    """Verify write permission and educational license guards."""
    with pytest.raises(PermissionError, match="Tally write operations are gated"):
        assert_write_permitted(allow_write=False, license_mode="LICENSED")

    with pytest.raises(PermissionError, match="Educational version"):
        assert_write_permitted(allow_write=True, license_mode="EDUCATIONAL")

    # Should pass without exception
    assert_write_permitted(allow_write=True, license_mode="LICENSED")


def test_build_import_data_envelope_success():
    """Verify canonical <IMPORTDATA> envelope formatting and ISDEEMEDPOSITIVE signs."""
    entries = [
        {"ledger": "ACME Traders", "is_debit": False, "amount_paise": 590000},  # Credit ₹5,900.00
        {"ledger": "Purchase Account", "is_debit": True, "amount_paise": 500000},  # Debit -₹5,000.00
        {"ledger": "Input CGST", "is_debit": True, "amount_paise": 45000},       # Debit -₹450.00
        {"ledger": "Input SGST", "is_debit": True, "amount_paise": 45000},       # Debit -₹450.00
    ]
    xml_envelope = build_import_data_envelope(
        voucher_date="20260630",
        voucher_type="Purchase",
        party_ledger="ACME Traders",
        remote_id="firmos-test-inv01",
        entries=entries,
    )
    assert 'REMOTEID="firmos-test-inv01"' in xml_envelope
    assert "<PARTYLEDGERNAME>ACME Traders</PARTYLEDGERNAME>" in xml_envelope
    # Check debit sign
    assert "<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>" in xml_envelope
    assert "<AMOUNT>-5000.00</AMOUNT>" in xml_envelope
    # Check credit sign
    assert "<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>" in xml_envelope
    assert "<AMOUNT>5900.00</AMOUNT>" in xml_envelope


def test_build_import_data_envelope_unbalanced_raises():
    """Verify that unbalanced voucher entries raise TallyWriteError."""
    entries = [
        {"ledger": "ACME Traders", "is_debit": False, "amount_paise": 590000},  # Credit ₹5,900
        {"ledger": "Purchase Account", "is_debit": True, "amount_paise": 500000},  # Debit -₹5,000 (missing ₹900 tax)
    ]
    with pytest.raises(TallyWriteError, match="Voucher entries do not net to zero"):
        build_import_data_envelope(
            voucher_date="20260630",
            voucher_type="Purchase",
            party_ledger="ACME Traders",
            remote_id="firmos-test-inv02",
            entries=entries,
        )


def test_parse_import_response_created():
    """Verify parsing successful Tally create response."""
    xml_resp = """<RESPONSE>
      <CREATED>1</CREATED>
      <ALTERED>0</ALTERED>
      <ERRORS>0</ERRORS>
    </RESPONSE>"""
    res = parse_import_response(xml_resp)
    assert res["success"] is True
    assert res["created"] == 1
    assert res["errors"] == 0


def test_parse_import_response_altered():
    """An overwrite response is not certified as a V1 create success."""
    xml_resp = """<RESPONSE>
      <CREATED>0</CREATED>
      <ALTERED>1</ALTERED>
      <ERRORS>0</ERRORS>
    </RESPONSE>"""
    res = parse_import_response(xml_resp)
    assert res["success"] is False
    assert res["altered"] == 1


def test_sales_voucher_has_its_own_certified_type():
    xml = build_import_data_envelope("20260630", "Sales", "Customer", "firmos:1", [
        {"ledger": "Customer", "is_debit": True, "amount_paise": 11800},
        {"ledger": "Sales", "is_debit": False, "amount_paise": 10000},
        {"ledger": "Output GST", "is_debit": False, "amount_paise": 1800},
    ])
    assert 'VCHTYPE="Sales"' in xml


def test_parse_import_response_error():
    """Verify parsing Tally error response."""
    xml_resp = """<RESPONSE>
      <CREATED>0</CREATED>
      <ALTERED>0</ALTERED>
      <ERRORS>1</ERRORS>
      <LINEERROR>Ledger 'Missing Party' does not exist</LINEERROR>
    </RESPONSE>"""
    res = parse_import_response(xml_resp)
    assert res["success"] is False
    assert res["errors"] == 1
    assert "Missing Party" in res["error_msg"]
