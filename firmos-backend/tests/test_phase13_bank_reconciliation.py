from datetime import date

import pytest

from core.errors import AppError
from engines.bank_matcher import BookCandidate, score_candidates
from engines.bank_registry import parse_bank_statement
from engines.bank_types import BankTransaction


CSV = b"Date,Description,Debit,Credit,Balance,Reference\n01/06/2026,Vendor payment,100.50,,899.50,INV001\n02/06/2026,Customer receipt,,200.00,1099.50,RCPT9\n"


def test_registry_parses_canonical_paise_and_integrity():
    result = parse_bank_statement(CSV, "statement.csv", "HDFC")
    assert result.adapter == "HDFC:GENERIC_CSV"
    assert result.transactions[0].debit_paise == 10050
    assert result.transactions[1].credit_paise == 20000
    assert result.transactions[0].source_row == 2
    assert result.integrity["valid"] is True


def test_registry_accepts_abbreviated_months_and_identifies_invalid_source_rows():
    abbreviated = CSV.replace(b"01/06/2026", b"01-Jun-26")
    assert parse_bank_statement(abbreviated, "statement.csv").transactions[0].txn_date == date(2026, 6, 1)
    invalid = CSV.replace(b"01/06/2026", b"not-a-date")
    with pytest.raises(AppError) as error:
        parse_bank_statement(invalid, "statement.csv")
    assert error.value.code == "INVALID_BANK_DATE"
    assert error.value.details == {"sourceRow": 2, "value": "not-a-date"}


def test_unknown_and_empty_formats_are_explicit_errors():
    with pytest.raises(AppError):
        parse_bank_statement(b"anything", "statement.txt")
    with pytest.raises(AppError):
        parse_bank_statement(b"Date,Description\n", "statement.csv")


def transaction(reference="INV001"):
    return BankTransaction(date(2026, 6, 1), None, "Vendor payment", reference, 10050, 0, 89950, 2, None,
                           ("INV001", "VENDOR", "PAYMENT"))


def test_explainable_candidate_requires_more_than_amount():
    amount_only = BookCandidate("PAYMENT", "p1", date(2026, 7, 1), 10050, "Other", "NONE")
    strong = BookCandidate("PAYMENT", "p2", date(2026, 6, 2), 10050, "Vendor", "INV001")
    scored = score_candidates(transaction(), [amount_only, strong])
    assert [item.candidate.candidate_id for item in scored] == ["p2"]
    assert any("Reference/party" in reason for reason in scored[0].reasons)


def test_value_tolerance_and_date_window_are_explainable():
    candidate = BookCandidate("PAYMENT", "p1", date(2026, 6, 4), 10100, "Vendor", "INV001")
    result = score_candidates(transaction(), [candidate])[0]
    assert result.score > 0.45
    assert any("Date" in reason for reason in result.reasons)
