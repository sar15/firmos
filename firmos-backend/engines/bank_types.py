"""Typed canonical bank statement parse contracts."""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BankTransaction:
    txn_date: date
    value_date: date | None
    description: str
    reference: str
    debit_paise: int
    credit_paise: int
    balance_paise: int | None
    source_row: int | None
    source_page: int | None
    normalized_tokens: tuple[str, ...]

    @property
    def amount_paise(self) -> int:
        return self.credit_paise or self.debit_paise

    @property
    def txn_type(self) -> str:
        return "CREDIT" if self.credit_paise else "DEBIT"


@dataclass(frozen=True)
class BankParseResult:
    adapter: str
    parser_version: str
    bank_name: str
    account_number_masked: str | None
    period_start: date
    period_end: date
    opening_balance_paise: int | None
    closing_balance_paise: int | None
    transactions: tuple[BankTransaction, ...]
    integrity: dict
