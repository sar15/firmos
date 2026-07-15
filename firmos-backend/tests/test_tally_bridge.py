"""Tests for local Tally Prime XML client and bridge daemon.

Why: Ensures XML escaping prevents TDL injection, parsing handles real-world
Tally UTF-8/UTF-16 XML responses without crashing, and GUID fallbacks work.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Ensure firmos-bridge is on path for import
bridge_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../firmos-bridge"))
if bridge_path not in sys.path:
    sys.path.insert(0, bridge_path)

from tally_client import (
    escape_xml_string,
    post_tally_xml,
    fetch_tally_companies,
    fetch_tally_ledgers,
    fetch_tally_vouchers,
    TallyConnectionError,
    TallyXmlError,
)
from bridge_daemon import push_to_cloud, CloudPushError


def test_escape_xml_string():
    """Verify XML injection prevention on account names and narration."""
    assert escape_xml_string("HDFC Bank & Co <Acct>") == "HDFC Bank &amp; Co &lt;Acct&gt;"
    assert escape_xml_string('Ledger "A\'s" A/C') == "Ledger &quot;A&apos;s&quot; A/C"
    assert escape_xml_string("") == ""


@patch("urllib.request.urlopen")
def test_post_tally_xml_success(mock_urlopen):
    """Test sending TDL query and receiving UTF-8 XML response."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"<RESPONSE>Success</RESPONSE>"
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp
    
    res = post_tally_xml("<QUERY></QUERY>", host="localhost", port=9000)
    assert res == "<RESPONSE>Success</RESPONSE>"
    assert mock_urlopen.called


@patch("urllib.request.urlopen", side_effect=Exception("Connection refused"))
def test_post_tally_xml_connection_error(mock_urlopen):
    """Test nice connection error messages when Tally Prime is closed."""
    with pytest.raises(TallyConnectionError) as exc_info:
        post_tally_xml("<QUERY></QUERY>")
    assert "Unexpected error communicating with Tally" in str(exc_info.value)


@patch("tally_client.post_tally_xml")
def test_fetch_tally_companies(mock_post):
    """Test parsing active company list XML from Tally."""
    mock_post.return_value = """<ENVELOPE>
        <BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME></REQUESTDESC>
        <COMPANY><NAME>Acme Industries 2024-25</NAME><GUID>com-guid-101</GUID></COMPANY>
        <COMPANY><NAME>Beta Trading Co</NAME></COMPANY>
        </EXPORTDATA></BODY>
    </ENVELOPE>"""
    
    companies = fetch_tally_companies()
    assert len(companies) == 2
    assert companies[0]["name"] == "Acme Industries 2024-25"
    assert companies[0]["guid"] == "com-guid-101"
    assert companies[1]["name"] == "Beta Trading Co"
    assert companies[1]["guid"] == ""


@patch("tally_client.post_tally_xml")
def test_fetch_tally_ledgers(mock_post):
    """Test ledger extraction with opening/closing balance parsing and GUID fallback."""
    mock_post.return_value = """<ENVELOPE>
        <BODY><EXPORTDATA>
        <LEDGER><NAME>HDFC Bank A/c</NAME><GUID>led-guid-001</GUID><PARENT>Bank Accounts</PARENT><OPENINGBALANCE>1,50,000.00 Dr</OPENINGBALANCE><CLOSINGBALANCE>2,00,000.00 Dr</CLOSINGBALANCE></LEDGER>
        <LEDGER><NAME>Sales Account</NAME><PARENT>Sales Accounts</PARENT><CLOSINGBALANCE>5,00,000.00 Cr</CLOSINGBALANCE></LEDGER>
        </EXPORTDATA></BODY>
    </ENVELOPE>"""
    
    ledgers = fetch_tally_ledgers("Acme Industries 2024-25")
    assert len(ledgers) == 2
    
    # Check bank ledger
    assert ledgers[0]["guid"] == "led-guid-001"
    assert ledgers[0]["name"] == "HDFC Bank A/c"
    assert ledgers[0]["opening_balance"] == "150000.00"
    assert ledgers[0]["closing_balance"] == "200000.00"
    assert not ledgers[0]["is_revenue"]
    
    # Check sales ledger with GUID fallback
    assert ledgers[1]["guid"] == "fallback-Acme Industries 2024-25-Sales Account"
    assert ledgers[1]["closing_balance"] == "-500000.00"
    assert ledgers[1]["is_revenue"]


@patch("tally_client.post_tally_xml")
def test_fetch_tally_vouchers(mock_post):
    """Test accounting voucher extraction and multi-line ledger entries."""
    mock_post.return_value = """<ENVELOPE>
        <BODY><EXPORTDATA>
        <VOUCHER>
            <GUID>vch-guid-888</GUID>
            <VOUCHERNUMBER>INV/2024/001</VOUCHERNUMBER>
            <DATE>20240615</DATE>
            <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
            <PARTYLEDGERNAME>Acme Client Corp</PARTYLEDGERNAME>
            <NARRATION>Being goods sold on credit</NARRATION>
            <ALLLEDGERENTRIES.LIST><LEDGERNAME>Acme Client Corp</LEDGERNAME><AMOUNT>-1,18,000.00</AMOUNT></ALLLEDGERENTRIES.LIST>
            <ALLLEDGERENTRIES.LIST><LEDGERNAME>Sales Account</LEDGERNAME><AMOUNT>1,00,000.00</AMOUNT></ALLLEDGERENTRIES.LIST>
            <ALLLEDGERENTRIES.LIST><LEDGERNAME>Output IGST</LEDGERNAME><AMOUNT>18,000.00</AMOUNT></ALLLEDGERENTRIES.LIST>
        </VOUCHER>
        </EXPORTDATA></BODY>
    </ENVELOPE>"""
    
    vouchers = fetch_tally_vouchers("Acme Industries 2024-25", "20240401", "20250331")
    assert len(vouchers) == 1
    vch = vouchers[0]
    assert vch["guid"] == "vch-guid-888"
    assert vch["voucher_number"] == "INV/2024/001"
    assert vch["voucher_type"] == "Sales"
    assert len(vch["entries"]) == 3
    assert vch["entries"][1]["ledger_name"] == "Sales Account"
    assert vch["entries"][1]["amount"] == "100000.00"


@patch("urllib.request.urlopen")
def test_push_to_cloud_success(mock_urlopen):
    """Test pushing JSON sync payload to firmOS cloud API."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"status": "ok", "message": "Synced 10 ledgers"}'
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp
    
    res = push_to_cloud("http://localhost:8000", "dev_token", {"test": "data"})
    assert res["status"] == "ok"
    assert mock_urlopen.called
