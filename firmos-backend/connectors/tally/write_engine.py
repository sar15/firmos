"""OSS-Grounded TallyPrime XML Write Engine.

Implements <IMPORTDATA> envelope generation, REMOTEID idempotency,
ISDEEMEDPOSITIVE debit/credit sign rules, pre-flight zero-balance assertion,
and response body validation based on TallyConnector / Tally.Py standards.
"""

from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from decimal import Decimal


class TallyWriteError(Exception):
    """Raised when voucher write envelope validation or Tally response fails."""
    pass


def assert_write_permitted(allow_write: bool, license_mode: str = "LICENSED") -> None:
    """Enforce Prerequisite Gates before building or transmitting voucher writes."""
    if not allow_write:
        raise PermissionError(
            "Tally write operations are gated. Gate 1 (CA sign-off) / Gate 2 unconfirmed."
        )
    if "EDUCATIONAL" in license_mode.upper():
        raise PermissionError(
            "Tally write prohibited on Educational version. Educational mode corrupts voucher dates."
        )


def build_import_data_envelope(
    voucher_date: str,
    voucher_type: str,
    party_ledger: str,
    remote_id: str,
    entries: list[dict],
) -> str:
    """Build canonical <IMPORTDATA> XML envelope for Tally voucher import.

    Args:
        voucher_date: YYYYMMDD string (e.g. '20260630').
        voucher_type: e.g. 'Purchase' or 'Sales'.
        party_ledger: Exact ledger name of counterparty.
        remote_id: Deterministic idempotency key (e.g. 'firmos-f1-inv01').
        entries: List of dicts with keys:
            - 'ledger': Ledger name
            - 'is_debit': bool (True for Debit/Yes, False for Credit/No)
            - 'amount_paise': int (signed or unsigned; will be converted to decimal rupees)

    Returns:
        Complete XML envelope string.
    """
    if voucher_type not in {"Purchase", "Sales"}:
        raise TallyWriteError("Tally permits only separately certified Purchase or Sales vouchers")

    # 1. Sign Rule & Net-Zero Balance Check
    total_rupees_check = Decimal(0)
    formatted_entries = []

    for item in entries:
        ledger_name = escape(item["ledger"])
        is_debit = bool(item["is_debit"])
        abs_paise = abs(int(item["amount_paise"]))
        rupees_val = (Decimal(abs_paise) / 100).quantize(Decimal("0.01"))

        # ISDEEMEDPOSITIVE sign contract: Yes = Debit (-ve amount), No = Credit (+ve amount)
        if is_debit:
            signed_amount = -rupees_val
            is_deemed_pos = "Yes"
        else:
            signed_amount = rupees_val
            is_deemed_pos = "No"

        total_rupees_check += signed_amount
        formatted_entries.append(
            f"""            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>{ledger_name}</LEDGERNAME>
              <ISDEEMEDPOSITIVE>{is_deemed_pos}</ISDEEMEDPOSITIVE>
              <AMOUNT>{signed_amount:.2f}</AMOUNT>
            </ALLLEDGERENTRIES.LIST>"""
        )

    if round(total_rupees_check, 2) != 0.00:
        raise TallyWriteError(
            f"Voucher entries do not net to zero (diff={total_rupees_check:.2f}). "
            "Tally rejects unbalanced vouchers."
        )

    entries_xml = "\n".join(formatted_entries)

    return f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME></REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          <VOUCHER VCHTYPE="{escape(voucher_type)}" ACTION="Create" OBJVIEW="Invoice Voucher View" REMOTEID="{escape(remote_id)}">
            <DATE>{escape(voucher_date)}</DATE>
            <PARTYLEDGERNAME>{escape(party_ledger)}</PARTYLEDGERNAME>
            <VOUCHERTYPENAME>{escape(voucher_type)}</VOUCHERTYPENAME>
{entries_xml}
          </VOUCHER>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>"""


def parse_import_response(xml_resp: str) -> dict:
    """Parse Tally XML response body, asserting <CREATED> or <ALTERED> and <ERRORS>0."""
    try:
        root = ET.fromstring(xml_resp)
    except ET.ParseError as exc:
        raise TallyWriteError(f"Malformed XML response from Tally: {exc}") from exc

    def get_tag_int(tag_name: str) -> int:
        elem = root.find(f".//{tag_name}")
        if elem is not None and elem.text:
            try:
                return int(elem.text.strip())
            except ValueError:
                return 0
        return 0

    created = get_tag_int("CREATED")
    altered = get_tag_int("ALTERED")
    errors = get_tag_int("ERRORS")

    line_error_elem = root.find(".//LINEERROR")
    error_msg = line_error_elem.text.strip() if line_error_elem is not None and line_error_elem.text else ""

    success = errors == 0 and created > 0
    return {
        "success": success,
        "created": created,
        "altered": altered,
        "errors": errors,
        "error_msg": error_msg,
    }
