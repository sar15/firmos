"""Versioned, deterministic GSTR-2B matching with human-readable reasons."""
from dataclasses import dataclass
from datetime import date
import re

from engines.gstr2b_types import Gstr2bDocument
from models.schemas import ReconLine

ALGORITHM_VERSION = "g2b-match-v1"
VALUE_TOLERANCE_PAISE = 100
DATE_TOLERANCE_DAYS = 5


@dataclass(frozen=True)
class Gstr2bMatch:
    purchase_id: str | None
    document: Gstr2bDocument | None
    bucket: str
    score: float | None
    reasons: tuple[str, ...]
    differences: dict[str, int | str]
    warnings: tuple[str, ...] = ()

    @property
    def clean(self) -> bool:
        return self.bucket == "EXACT" and not self.warnings


def _number(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _book_date(line: ReconLine) -> date | None:
    try:
        return date.fromisoformat(line.date)
    except ValueError:
        return None


def match_gstr2b(
    purchases: list[ReconLine], documents: tuple[Gstr2bDocument, ...], claimed_keys: set[str] | None = None,
) -> list[Gstr2bMatch]:
    claimed_keys = claimed_keys or set()
    results: list[Gstr2bMatch] = []
    used: set[str] = set()
    counts: dict[str, int] = {}
    for document in documents:
        counts[document.identity_key] = counts.get(document.identity_key, 0) + 1

    for purchase in purchases:
        candidates = [d for d in documents if d.identity_key not in used and d.supplier_gstin == (purchase.gstin or "").upper()]
        same_number = [d for d in candidates if _number(d.invoice_number) == _number(purchase.ref)]
        pool = same_number or candidates
        if not pool:
            results.append(Gstr2bMatch(purchase.id, None, "MISSING_IN_2B", None, ("No 2B document has this supplier GSTIN.",), {}))
            continue
        book_date = _book_date(purchase)
        document = min(pool, key=lambda item: abs(item.total_paise - int(purchase.amount)))
        used.add(document.identity_key)
        value_diff = document.total_paise - int(purchase.amount)
        date_diff = (document.invoice_date - book_date).days if book_date else 0
        differences = {"value_paise": value_diff, "date_days": date_diff}
        warnings: list[str] = []
        if document.identity_key in claimed_keys:
            warnings.append("This 2B document was already accepted for ITC in another period.")
        if counts[document.identity_key] > 1:
            bucket, reasons, score = "DUPLICATE", ("The same canonical 2B identity appears more than once.",), 0.0
        elif document.amendment_of_key or document.document_type != "INVOICE":
            bucket, reasons, score = "AMENDMENT_CREDIT_NOTE", ("This is an amendment or credit/debit note and needs reviewer treatment.",), 0.7
        elif same_number and value_diff == 0 and date_diff == 0:
            bucket, reasons, score = "EXACT", ("GSTIN, normalized invoice number, date and value match.",), 1.0
        elif same_number and abs(value_diff) <= VALUE_TOLERANCE_PAISE and abs(date_diff) <= DATE_TOLERANCE_DAYS:
            bucket, reasons, score = "PROBABLE", ("Identity matches with a small date or rounding variation.",), 0.92
        elif same_number:
            bucket, reasons, score = "MISMATCH", ("GSTIN and invoice number match, but date or value differs.",), 0.8
        else:
            bucket, reasons, score = "MANUAL_REVIEW", ("Supplier matches but invoice identity is not deterministic.",), 0.5
        results.append(Gstr2bMatch(purchase.id, document, bucket, score, reasons, differences, tuple(warnings)))

    for document in documents:
        if document.identity_key not in used:
            bucket = "DUPLICATE" if counts[document.identity_key] > 1 else "MISSING_IN_BOOKS"
            results.append(Gstr2bMatch(None, document, bucket, None, ("This 2B document has no purchase-register match.",), {}))
    return results
