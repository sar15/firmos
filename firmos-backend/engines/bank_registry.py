"""Small parser registry: explicit adapters, strict unsupported-format failures."""
from __future__ import annotations

from datetime import date
import re

from core.errors import AppError
from api.routes.bank_statement_parsing import parse_csv_or_excel, parse_pdf_digital, validate_running_balance
from engines.bank_types import BankParseResult, BankTransaction

PARSER_VERSION = "bank-parser-v1"
SUPPORTED = {"csv": "GENERIC_CSV", "xls": "GENERIC_XLS", "xlsx": "GENERIC_XLSX", "pdf": "GENERIC_DIGITAL_PDF"}


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(sorted(set(re.findall(r"[A-Z0-9]{3,}", text.upper()))))


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AppError("INVALID_BANK_DATE", f"Unsupported transaction date: {value}", status_code=422) from exc


def parse_bank_statement(content: bytes, filename: str, bank_hint: str | None = None) -> BankParseResult:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    adapter = SUPPORTED.get(extension)
    if not adapter:
        raise AppError("UNSUPPORTED_FORMAT", "This bank statement format is not supported.", status_code=415,
                       user_action="Upload CSV, XLS, XLSX, or a digital PDF export.")
    try:
        rows = parse_pdf_digital(content) if extension == "pdf" else parse_csv_or_excel(content, filename.lower())
    except Exception as exc:
        raise AppError("BANK_PARSE_FAILED", "The bank statement could not be parsed.", status_code=422,
                       user_action="Download a fresh statement export from the bank.") from exc
    if not rows:
        code = "UNSUPPORTED_FORMAT" if extension == "pdf" else "BANK_PARSE_FAILED"
        raise AppError(code, "No supported transaction table was found.", status_code=422,
                       user_action="Use a digital statement or CSV/Excel export.")
    transactions = []
    for index, row in enumerate(rows, start=2):
        amount = int(row["amount"])
        credit = amount if row["txn_type"] == "CREDIT" else 0
        debit = amount if row["txn_type"] == "DEBIT" else 0
        balance = int(row.get("running_balance") or 0) or None
        transactions.append(BankTransaction(
            txn_date=_date(row["txn_date"]), value_date=_date(row["value_date"]) if row.get("value_date") else None,
            description=row["description"], reference=row.get("ref_no", ""), debit_paise=debit,
            credit_paise=credit, balance_paise=balance, source_row=row.get("source_row", index),
            source_page=row.get("source_page"), normalized_tokens=_tokens(f"{row['description']} {row.get('ref_no', '')}"),
        ))
    check = validate_running_balance(rows)
    balances = [item.balance_paise for item in transactions if item.balance_paise is not None]
    return BankParseResult(
        adapter=f"{(bank_hint or 'GENERIC').upper()}:{adapter}", parser_version=PARSER_VERSION,
        bank_name=(bank_hint or "Unknown bank").strip(), account_number_masked=None,
        period_start=min(item.txn_date for item in transactions), period_end=max(item.txn_date for item in transactions),
        opening_balance_paise=None, closing_balance_paise=balances[-1] if balances else None,
        transactions=tuple(transactions), integrity=check,
    )
