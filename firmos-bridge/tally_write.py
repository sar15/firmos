"""Validated Tally voucher XML construction and import-response parsing."""
import xml.etree.ElementTree as ET
from decimal import Decimal
from typing import Any, Dict

from tally_client import TallyXmlError, escape_xml_string


def build_purchase_voucher_xml(payload: Dict[str, Any], remote_id: str, company_name: str) -> str:
    """Build a purchase voucher from integer paise and validated ledger names."""
    esc_comp = escape_xml_string(company_name)
    esc_remote = escape_xml_string(remote_id)
    vch_date = escape_xml_string(str(payload.get("date", "")))
    party = escape_xml_string(str(payload.get("party_ledger", "")))
    purchase_ledger = escape_xml_string(str(payload.get("purchase_ledger", "")))
    narration = escape_xml_string(str(payload.get("narration", "")))
    amount_paise = int(payload.get("total_paise", 0))
    if amount_paise <= 0 or not party or not purchase_ledger or not vch_date:
        raise TallyXmlError("Purchase voucher requires date, party_ledger, purchase_ledger, and positive total_paise")
    amount_inr = format((Decimal(amount_paise) / Decimal(100)).quantize(Decimal("0.01")), ".2f")
    return f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
  <BODY><IMPORTDATA>
    <REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME><STATICVARIABLES>
      <SVCURRENTCOMPANY>{esc_comp}</SVCURRENTCOMPANY>
    </STATICVARIABLES></REQUESTDESC>
    <REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">
      <VOUCHER VCHTYPE="Purchase" ACTION="Create" REMOTEID="{esc_remote}">
        <DATE>{vch_date}</DATE><VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
        <PARTYLEDGERNAME>{party}</PARTYLEDGERNAME><NARRATION>{narration}</NARRATION>
        <ALLLEDGERENTRIES.LIST><LEDGERNAME>{party}</LEDGERNAME>
          <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>{amount_inr}</AMOUNT>
        </ALLLEDGERENTRIES.LIST>
        <ALLLEDGERENTRIES.LIST><LEDGERNAME>{purchase_ledger}</LEDGERNAME>
          <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-{amount_inr}</AMOUNT>
        </ALLLEDGERENTRIES.LIST>
      </VOUCHER>
    </TALLYMESSAGE></REQUESTDATA>
  </IMPORTDATA></BODY>
</ENVELOPE>"""


def parse_tally_import_response(response_xml: str) -> Dict[str, Any]:
    """Treat ambiguous or malformed import responses as review-required."""
    try:
        root = ET.fromstring(response_xml)
        errors = [err.text for err in root.findall(".//LINEERROR") if err.text]
        created = sum(int(node.text or 0) for node in root.findall(".//CREATED")
                      if node.text and node.text.isdigit())
        if errors:
            return _result("FAILED", response_xml, created, "; ".join(errors))
        if created > 0:
            return _result("SUCCEEDED", response_xml, created)
        return _result("NEEDS_REVIEW", response_xml, 0,
                       "Ambiguous Tally response: 0 created and 0 line errors reported")
    except Exception as exc:
        return _result("NEEDS_REVIEW", response_xml, 0, f"Failed to parse XML response: {exc}")


def _result(status: str, response_xml: str, created: int, error: str | None = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {"status": status, "created_count": created, "raw_preview": response_xml[:500]}
    if error:
        result["error"] = error
    return result
