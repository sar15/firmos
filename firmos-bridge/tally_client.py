"""Dependency-free Tally Prime XML read client for the local office bridge."""

import logging
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

logger = logging.getLogger("tally_bridge.client")


class TallyConnectionError(Exception):
    """Raised when the local Tally Prime gateway is unreachable or unresponsive."""
    pass


class TallyXmlError(Exception):
    """Raised when Tally Prime returns an XML error or malformed response."""
    pass


def escape_xml_string(value: str) -> str:
    """Escape XML special characters to prevent XML injection in TDL queries.
    
    Why: Company names, ledger names, and narration strings in accounting
    frequently contain ampersands ('&'), quotes, or angle brackets.
    """
    if not value:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def post_tally_xml(
    xml_query: str,
    host: str = "localhost",
    port: int = 9000,
    timeout: int = 15,
) -> str:
    """Send a raw POST request containing TDL XML to the local Tally gateway.
    
    Why: Tally Prime does not use standard REST or JSON; it listens on an HTTP
    port for POST requests with raw XML payloads and responds with UTF-16/UTF-8 XML.
    """
    url = f"http://{host}:{port}"
    data = xml_query.encode("utf-8")
    
    headers = {
        "Content-Type": "text/xml;charset=utf-8",
        "Content-Length": str(len(data)),
        "User-Agent": "firmOS-TallyBridge/1.0",
    }
    
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        logger.debug("Sending XML request (%d bytes) to %s", len(data), url)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_bytes = response.read()
            # Tally Prime sometimes returns UTF-16LE or UTF-16BE with BOM
            for encoding in ("utf-8", "utf-16", "utf-16le", "iso-8859-1"):
                try:
                    return raw_bytes.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return raw_bytes.decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise TallyConnectionError(
            f"Could not connect to Tally Prime at {url}. "
            f"Ensure Tally is open and configured to listen on port {port} "
            f"(F1 -> Settings -> Connectivity -> Enable ODBC/HTTP: Yes)."
        ) from exc
    except Exception as exc:
        raise TallyConnectionError(f"Unexpected error communicating with Tally: {exc}") from exc


def fetch_tally_companies(host: str = "localhost", port: int = 9000) -> List[Dict[str, str]]:
    """Fetch the list of currently open companies in Tally Prime.
    
    Why: To prevent syncing data to the wrong firm, the bridge probes active
    companies and requires the CA to specify or verify which company to sync.
    """
    xml_query = """<ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>List of Companies</REPORTNAME>
                    <STATICVARIABLES>
                        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                    </STATICVARIABLES>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY>
    </ENVELOPE>"""
    
    response_xml = post_tally_xml(xml_query, host=host, port=port)
    companies = []
    
    try:
        root = ET.fromstring(response_xml)
        # Check for Tally line errors
        for line_error in root.findall(".//LINEERROR"):
            raise TallyXmlError(f"Tally TDL error: {line_error.text}")
            
        for company_node in root.findall(".//COMPANY"):
            name_node = company_node.find("NAME")
            if name_node is not None and name_node.text:
                companies.append({
                    "name": name_node.text.strip(),
                    "guid": company_node.find("GUID").text if company_node.find("GUID") is not None else "",
                })
    except ET.ParseError as exc:
        logger.warning("Failed to parse company list XML from Tally: %s", exc)
        
    return companies


def fetch_tally_ledgers(
    company_name: str,
    host: str = "localhost",
    port: int = 9000,
) -> List[Dict[str, Any]]:
    """Export all ledgers from the specified Tally company with GUIDs and balances.
    
    Why GUIDs: Tally ledger names can change (e.g. 'HDFC Bank' -> 'HDFC Bank A/c 1234').
    Using GUID as canonical primary key ensures immutability and prevents duplicate
    accounts in firmOS when ledgers are renamed in Tally.
    """
    escaped_company = escape_xml_string(company_name)
    xml_query = f"""<ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>List of Accounts</REPORTNAME>
                    <STATICVARIABLES>
                        <SVCURRENTCOMPANY>{escaped_company}</SVCURRENTCOMPANY>
                        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                        <ACCOUNTTYPE>Ledgers</ACCOUNTTYPE>
                    </STATICVARIABLES>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY>
    </ENVELOPE>"""
    
    response_xml = post_tally_xml(xml_query, host=host, port=port)
    ledgers = []
    
    try:
        root = ET.fromstring(response_xml)
        for error_node in root.findall(".//LINEERROR"):
            raise TallyXmlError(f"Tally ledger export error: {error_node.text}")
            
        for ledger_node in root.findall(".//LEDGER"):
            name_node = ledger_node.find("NAME")
            if name_node is None or not name_node.text:
                continue
            name = name_node.text.strip()
            
            # Extract canonical GUID or fall back to deterministic hash/string if missing
            guid_node = ledger_node.find("GUID")
            guid = guid_node.text.strip() if (guid_node is not None and guid_node.text) else f"fallback-{company_name}-{name}"
            
            parent_node = ledger_node.find("PARENT")
            parent_group = parent_node.text.strip() if (parent_node is not None and parent_node.text) else "Primary"
            
            opening_node = ledger_node.find("OPENINGBALANCE")
            closing_node = ledger_node.find("CLOSINGBALANCE")
            
            def parse_tally_amount(amt_str: Optional[str]) -> str:
                if not amt_str:
                    return "0.00"
                clean = amt_str.replace(",", "").strip()
                # Tally format: negative represents debit in some reports, or ends with Dr/Cr
                try:
                    if clean.endswith("Dr"):
                        return str(Decimal(clean[:-2].strip()))
                    if clean.endswith("Cr"):
                        return str(-Decimal(clean[:-2].strip()))
                    return str(Decimal(clean))
                except InvalidOperation:
                    return "0.00"

            ledgers.append({
                "guid": guid,
                "name": name,
                "parent_group": parent_group,
                "opening_balance": parse_tally_amount(opening_node.text if opening_node is not None else None),
                "closing_balance": parse_tally_amount(closing_node.text if closing_node is not None else None),
                "is_revenue": any(k in parent_group.lower() for k in ("sales", "income", "purchase", "expense", "duty", "tax", "gst", "tds")),
            })
    except ET.ParseError as exc:
        raise TallyXmlError(f"Malformed XML response from Tally during ledger export: {exc}") from exc
        
    logger.info("Exported %d ledgers for company '%s'", len(ledgers), company_name)
    return ledgers


def fetch_tally_vouchers(
    company_name: str,
    from_date: str,
    to_date: str,
    host: str = "localhost",
    port: int = 9000,
) -> List[Dict[str, Any]]:
    """Export accounting vouchers between from_date and to_date (format: YYYYMMDD).
    
    Why: Pulls transactional history for GST reconciliation, TDS checks, and
    audit working papers without modifying the client's live Tally database.
    """
    escaped_company = escape_xml_string(company_name)
    xml_query = f"""<ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>Voucher Register</REPORTNAME>
                    <STATICVARIABLES>
                        <SVCURRENTCOMPANY>{escaped_company}</SVCURRENTCOMPANY>
                        <SVFROMDATE>{from_date}</SVFROMDATE>
                        <SVTODATE>{to_date}</SVTODATE>
                        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                    </STATICVARIABLES>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY>
    </ENVELOPE>"""
    
    response_xml = post_tally_xml(xml_query, host=host, port=port)
    vouchers = []
    
    try:
        root = ET.fromstring(response_xml)
        for error_node in root.findall(".//LINEERROR"):
            raise TallyXmlError(f"Tally voucher export error: {error_node.text}")
            
        for voucher_node in root.findall(".//VOUCHER"):
            guid_node = voucher_node.find("GUID")
            vch_num_node = voucher_node.find("VOUCHERNUMBER")
            date_node = voucher_node.find("DATE")
            type_node = voucher_node.find("VOUCHERTYPENAME")
            party_node = voucher_node.find("PARTYLEDGERNAME")
            narration_node = voucher_node.find("NARRATION")
            
            vch_num = vch_num_node.text.strip() if (vch_num_node is not None and vch_num_node.text) else "UNNUMBERED"
            vch_date = date_node.text.strip() if (date_node is not None and date_node.text) else ""
            
            guid = guid_node.text.strip() if (guid_node is not None and guid_node.text) else f"vch-{company_name}-{vch_date}-{vch_num}"
            vch_type = type_node.text.strip() if (type_node is not None and type_node.text) else "Journal"
            party_name = party_node.text.strip() if (party_node is not None and party_node.text) else ""
            narration = narration_node.text.strip() if (narration_node is not None and narration_node.text) else ""
            
            entries = []
            for entry_node in voucher_node.findall(".//ALLLEDGERENTRIES.LIST"):
                l_name = entry_node.find("LEDGERNAME")
                l_amt = entry_node.find("AMOUNT")
                if l_name is not None and l_name.text:
                    amt_val = "0.00"
                    if l_amt is not None and l_amt.text:
                        try:
                            amt_val = str(Decimal(l_amt.text.replace(",", "").strip()))
                        except InvalidOperation:
                            amt_val = "0.00"
                    entries.append({
                        "ledger_name": l_name.text.strip(),
                        "amount": amt_val,
                    })
                    
            vouchers.append({
                "guid": guid,
                "voucher_number": vch_num,
                "date": vch_date,
                "voucher_type": vch_type,
                "party_name": party_name,
                "narration": narration,
                "entries": entries,
            })
    except ET.ParseError as exc:
        raise TallyXmlError(f"Malformed XML response from Tally during voucher export: {exc}") from exc
        
    logger.info("Exported %d vouchers for company '%s' (%s to %s)", len(vouchers), company_name, from_date, to_date)
    return vouchers


from tally_write import build_purchase_voucher_xml, parse_tally_import_response  # noqa: E402,F401
