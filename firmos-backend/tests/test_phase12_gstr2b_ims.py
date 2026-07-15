from datetime import date

import pytest

from core.errors import AppError
from engines.gstr2b_matcher import match_gstr2b
from engines.gstr2b_parser import parse_gstr2b_json
from engines.gstr2b_types import Gstr2bDocument
from models.schemas import ReconLine


def payload(number="INV/001", invoice_date="10-06-2026", value="118.00", section="b2b"):
    child = "inv" if section.startswith("b2b") else "nt"
    number_key, date_key = ("inum", "idt") if child == "inv" else ("ntnum", "ntdt")
    return {
        "gstin": "27ABCDE1234F1Z5", "rtnprd": "062026",
        "docdata": {section: [{"ctin": "29ABCDE1234F1Z7", child: [{
            number_key: number, date_key: invoice_date, "val": value,
            "itms": [{"itm_det": {"txval": "100", "iamt": "18"}}],
        }]}]},
    }


def purchase(number="INV001", invoice_date="2026-06-10", amount=11800):
    return ReconLine(id="purchase-1", date=invoice_date, description="Purchase", counterparty="Vendor",
                     amount=amount, ref=number, gstin="29ABCDE1234F1Z7")


def test_typed_decimal_parse_and_canonical_identity():
    result = parse_gstr2b_json(payload())
    assert result.gstin == "27ABCDE1234F1Z5"
    assert result.return_period == "062026"
    assert result.source_totals == {"taxable_paise": 10000, "tax_paise": 1800, "total_paise": 11800}
    assert result.documents[0].invoice_number == "INV/001"
    assert len(result.documents[0].identity_key) == 64


@pytest.mark.parametrize("number,invoice_date,amount,bucket", [
    ("INV001", "2026-06-10", 11800, "EXACT"),
    ("INV-001", "2026-06-12", 11850, "PROBABLE"),
    ("INV001", "2026-06-20", 12500, "MISMATCH"),
])
def test_versioned_matching_matrix(number, invoice_date, amount, bucket):
    parsed = parse_gstr2b_json(payload())
    assert match_gstr2b([purchase(number, invoice_date, amount)], parsed.documents)[0].bucket == bucket


def test_missing_duplicate_credit_note_amendment_and_duplicate_claim_warning():
    document = parse_gstr2b_json(payload()).documents[0]
    assert match_gstr2b([purchase("OTHER")], ())[0].bucket == "MISSING_IN_2B"
    assert match_gstr2b([], (document,))[0].bucket == "MISSING_IN_BOOKS"
    assert match_gstr2b([purchase()], (document, document))[0].bucket == "DUPLICATE"
    assert match_gstr2b([purchase()], (document,), {document.identity_key})[0].warnings
    note = Gstr2bDocument(**{**document.__dict__, "document_type": "CREDIT_NOTE"})
    assert match_gstr2b([purchase()], (note,))[0].bucket == "AMENDMENT_CREDIT_NOTE"


def test_corrupt_and_empty_files_never_return_empty_results():
    with pytest.raises(AppError):
        parse_gstr2b_json({"docdata": {}})
    with pytest.raises(AppError):
        parse_gstr2b_json({"data": []})


def test_changed_purchase_register_recomputes_bucket():
    parsed = parse_gstr2b_json(payload())
    assert match_gstr2b([purchase(amount=11800)], parsed.documents)[0].bucket == "EXACT"
    assert match_gstr2b([purchase(amount=13000)], parsed.documents)[0].bucket == "MISMATCH"
