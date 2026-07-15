"""Provider-read GSTR-2B reconciliation for WhiteBooks."""

from __future__ import annotations

from typing import Any

from connectors.gst_filing.types import PurchaseRow, ReconMatchRow, ReconReport


async def reconcile_gstr2b(
    client: Any, gstin: str, period: str, purchase_ledger: list[PurchaseRow]
) -> ReconReport:
    """Reconcile provider-read GSTR-2B data with the purchase ledger."""
    from engines.reconcile import reconcile
    from models.schemas import ReconLine

    gstr2b = await client.fetch_2b(gstin, period)
    source_lines = [
        ReconLine(
            id=f"pr-{row.invoice_number}", date=row.invoice_date,
            description=f"Purchase - {row.supplier_name}", counterparty=row.supplier_name,
            amount=row.taxable_value_paise + row.total_gst_paise, ref=row.invoice_number,
            gstin=row.supplier_gstin,
        )
        for row in purchase_ledger
    ]
    target_lines = [
        ReconLine(
            id=f"2b-{entry.invoice_number}", date=entry.invoice_date,
            description=f"B2B - {entry.supplier_name}", counterparty=entry.supplier_name,
            amount=entry.invoice_value_paise, gstin=entry.supplier_gstin,
        )
        for entry in gstr2b.entries
    ]
    result = reconcile(source_lines, target_lines)
    rows: list[ReconMatchRow] = []
    matched = mismatched = missing_2b = missing_books = eligible = ineligible = 0
    for match in result.matches:
        if match.status == "AUTO_MATCHED" and not match.flag:
            status, matched, eligible = "MATCHED", matched + 1, eligible + match.source.amount
        elif match.status == "AUTO_MATCHED":
            status, mismatched, ineligible = "MISMATCHED", mismatched + 1, ineligible + match.source.amount
        elif match.flag == "SUPPLIER_NOT_FILED":
            status, missing_books, ineligible = "MISSING_IN_BOOKS", missing_books + 1, ineligible + match.source.amount
        elif match.status == "UNMATCHED":
            status, missing_2b, ineligible = "MISSING_IN_2B", missing_2b + 1, ineligible + match.source.amount
        else:
            status, mismatched, ineligible = "MISMATCHED", mismatched + 1, ineligible + match.source.amount
        target_amount = match.target.amount if match.target else 0
        rows.append(ReconMatchRow(
            invoice_number=match.source.ref or match.source.id,
            supplier_gstin=match.source.gstin or "", status=status,
            books_amount_paise=match.source.amount, gstr2b_amount_paise=target_amount,
            difference_paise=abs(match.source.amount - target_amount), itc_eligible=status == "MATCHED",
        ))
    return ReconReport(
        gstin=gstin, period=period, matched_count=matched, mismatched_count=mismatched,
        missing_in_2b_count=missing_2b, missing_in_books_count=missing_books,
        total_itc_eligible_paise=eligible, total_itc_ineligible_paise=ineligible, rows=rows,
    )
