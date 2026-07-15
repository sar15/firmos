"""Deterministic currency conversion; application money is integer paise."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

PAISE = Decimal("0.01")


class MoneyParseError(ValueError):
    pass


def parse_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise MoneyParseError("Money value is missing or invalid")
    text = str(value).strip().replace(",", "").replace("₹", "")
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise MoneyParseError("Money value is invalid") from exc
    if not amount.is_finite():
        raise MoneyParseError("Money value must be finite")
    return amount


def rupees_to_paise(value: Any, *, strict_precision: bool = True) -> int:
    amount = parse_decimal(value)
    if strict_precision and amount != amount.quantize(PAISE):
        raise MoneyParseError("Money value has more than two decimal places")
    return int((amount.quantize(PAISE, rounding=ROUND_HALF_UP) * 100).to_integral_exact())


def paise_to_decimal(value: int) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MoneyParseError("Paise must be an integer")
    return (Decimal(value) / 100).quantize(PAISE)


def parse_signed_amount(value: Any, marker: str | None = None) -> int:
    text = str(value).strip()
    suffix = (marker or "").strip().upper()
    for candidate in ("DR", "CR"):
        if text.upper().endswith(candidate):
            suffix, text = candidate, text[:-2].strip()
            break
    amount = abs(rupees_to_paise(text))
    return -amount if suffix == "DR" else amount


def currency_precision(currency: str) -> int:
    return 0 if currency.upper() in {"JPY", "KRW"} else 2
