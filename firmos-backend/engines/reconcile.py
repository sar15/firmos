"""Fuzzy reconciliation engine — matches invoices across two sources.

Pure Python, NO AI. Uses rapidfuzz for string matching.
All amounts are in PAISE (integer).
"""
from __future__ import annotations

import hashlib

from rapidfuzz import fuzz

from models.schemas import ReconLine, ReconMatch, ReconciliationSummary, ReconciliationResult


# Match thresholds
AMOUNT_TOLERANCE_PAISE = 100  # ₹1 tolerance
DATE_DRIFT_DAYS = 5
FUZZY_THRESHOLD = 75  # rapidfuzz score threshold


def reconcile(
    source_lines: list[ReconLine],
    target_lines: list[ReconLine],
) -> ReconciliationResult:
    """Match source lines against target lines using amount + fuzzy counterparty matching.
    
    source = e.g. purchase register
    target = e.g. GSTR-2B entries
    """
    matched_target_ids: set[str] = set()
    matches: list[ReconMatch] = []
    def stable_match_id(source_id: str, target_id: str = "") -> str:
        # Stable across refreshes so a reviewer decision remains auditable.
        return "rm-" + hashlib.sha256(f"{source_id}:{target_id}".encode()).hexdigest()[:24]

    for src in source_lines:
        best_match: ReconLine | None = None
        best_score: float = 0
        best_flag: str | None = None

        for tgt in target_lines:
            if tgt.id in matched_target_ids:
                continue

            # GST-standard hard key: (gstin, ref). This is the legally correct
            # reconciliation key and MUST take priority over fuzzy name matching,
            # because the GSTR-2B parser stores the GSTIN as `counterparty` while
            # books store the supplier trade name -- fuzzy name matching alone can
            # never align them.
            key_match = bool(
                src.gstin and tgt.gstin and src.gstin == tgt.gstin
                and src.ref and tgt.ref and src.ref == tgt.ref
            )

            # Amount check (both in paise). Allow a keyed match even when the
            # amount differs (flagged below) so mismatches are surfaced, not dropped.
            amount_diff = abs(src.amount - tgt.amount)
            if not key_match and amount_diff > AMOUNT_TOLERANCE_PAISE:
                continue  # too far apart, skip

            # Counterparty fuzzy match (fallback signal)
            name_score = fuzz.token_sort_ratio(
                src.counterparty.lower(), tgt.counterparty.lower()
            )
            if not key_match and name_score < FUZZY_THRESHOLD:
                continue

            # Compute combined score. A keyed match is authoritative.
            amount_score = max(0, 100 - (amount_diff / 100))
            if key_match:
                combined = 1.0
            else:
                combined = (name_score * 0.6 + amount_score * 0.4) / 100

            # Check for flags
            flag = None
            if amount_diff > AMOUNT_TOLERANCE_PAISE:
                flag = "AMOUNT_MISMATCH"

            if combined > best_score:
                best_match = tgt
                best_score = combined
                best_flag = flag

        if best_match and best_score >= 0.8:
            matched_target_ids.add(best_match.id)
            matches.append(ReconMatch(
                id=stable_match_id(src.id, best_match.id),
                status="AUTO_MATCHED",
                score=round(best_score, 2),
                source=src,
                target=best_match,
                flag=best_flag,
            ))
        elif best_match:
            matched_target_ids.add(best_match.id)
            matches.append(ReconMatch(
                id=stable_match_id(src.id, best_match.id),
                status="SUGGESTED",
                score=round(best_score, 2),
                source=src,
                target=best_match,
                flag=best_flag,
            ))
        else:
            matches.append(ReconMatch(
                id=stable_match_id(src.id),
                status="UNMATCHED",
                score=None,
                source=src,
                target=None,
            ))

    # Keep a portal-only row on the target side. A GSTR-2B document missing
    # from books is not evidence that the supplier failed to file.
    for tgt in target_lines:
        if tgt.id not in matched_target_ids:
            matches.append(ReconMatch(
                id=stable_match_id(tgt.id),
                status="UNMATCHED",
                score=None,
                source=None,
                target=tgt,
                flag="PORTAL_ENTRY_NOT_IN_BOOKS",
            ))

    # Compute summary
    auto = [m for m in matches if m.status == "AUTO_MATCHED"]
    suggested = [m for m in matches if m.status == "SUGGESTED"]
    unmatched = [m for m in matches if m.status == "UNMATCHED"]

    summary = ReconciliationSummary(
        autoMatched=len(auto),
        suggested=len(suggested),
        unmatched=len(unmatched),
        totalAutoMatched=sum((m.source or m.target).amount for m in auto),
        totalSuggested=sum((m.source or m.target).amount for m in suggested),
        totalUnmatched=sum((m.source or m.target).amount for m in unmatched),
    )

    return ReconciliationResult(matches=matches, summary=summary)
