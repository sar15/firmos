"""Explainable bank candidate scoring; amount alone can never auto-accept."""
from dataclasses import dataclass
from datetime import date
import re

from engines.bank_types import BankTransaction

ALGORITHM_VERSION = "bank-match-v1"


@dataclass(frozen=True)
class BookCandidate:
    source: str
    candidate_id: str
    txn_date: date
    amount_paise: int
    party: str
    reference: str


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: BookCandidate
    score: float
    reasons: tuple[str, ...]


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[A-Z0-9]{3,}", value.upper()))


def score_candidates(transaction: BankTransaction, candidates: list[BookCandidate]) -> list[ScoredCandidate]:
    scored = []
    transaction_tokens = set(transaction.normalized_tokens)
    for candidate in candidates:
        if abs(candidate.amount_paise - transaction.amount_paise) > 100:
            continue
        reasons = ["Amount matches within ₹1."]
        score = 0.45
        day_drift = abs((candidate.txn_date - transaction.txn_date).days)
        if day_drift <= 3:
            score += 0.2
            reasons.append(f"Date is within {day_drift} day(s).")
        reference_tokens = _tokens(f"{candidate.reference} {candidate.party}")
        overlap = transaction_tokens & reference_tokens
        if overlap:
            score += min(0.35, 0.1 * len(overlap))
            reasons.append(f"Reference/party evidence overlaps: {', '.join(sorted(overlap)[:3])}.")
        if score > 0.45:  # amount-only candidates are deliberately omitted
            scored.append(ScoredCandidate(candidate, min(score, 1.0), tuple(reasons)))
    return sorted(scored, key=lambda item: item.score, reverse=True)
