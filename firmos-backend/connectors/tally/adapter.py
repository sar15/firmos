"""Tally Prime adapter implementing AccountingConnector protocol.

Why read-only from database: The cloud backend never initiates HTTP requests
to local office IPs (localhost:9000). Instead, this adapter queries the canonical
tally_ledgers and tally_vouchers Postgres tables that were asynchronously pushed
by the local office bridge daemon.
"""

import json
from typing import Any, Dict, List
from datetime import datetime

from connectors.accounting import AccountingConnector, LedgerRow
from connectors.gst_filing.types import PurchaseRow, SalesRow
from core.money import parse_decimal, rupees_to_paise

class TallyAccountingAdapter:
    """Read-only AccountingConnector adapter for synced Tally Prime data."""

    def __init__(self, firm_id: str, company_name: str, db_pool: Any):
        self.firm_id = firm_id
        self.company_name = company_name
        self.db_pool = db_pool

    async def capabilities(self) -> List[str]:
        """Return supported capabilities for this connector."""
        return ["ledgers", "vouchers", "registers"]

    async def get_ledgers(self) -> List[LedgerRow]:
        """Fetch chart of accounts / ledgers from canonical Postgres storage."""
        if not self.db_pool:
            raise RuntimeError("Database pool not available for Tally get_ledgers")
            
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT tally_guid, name, parent_group
                FROM tally_ledgers
                WHERE firm_id = $1 AND company_name = $2
                ORDER BY name ASC
                """,
                self.firm_id, self.company_name,
            )
            
        return [
            LedgerRow(
                id=str(row["tally_guid"]),
                name=str(row["name"]),
                code="",
                group=str(row["parent_group"]),
            )
            for row in rows
        ]

    async def create_purchase_bill(self, bill_payload: Dict[str, Any]) -> str:
        """Reject synchronous cloud-to-desktop writes."""
        raise NotImplementedError(
            "Direct synchronous writing to local Tally Prime XML gateway from the cloud API "
            "is not permitted. Accounting writes must be queued for bridge daemon export/import."
        )

    async def post_voucher(self, voucher_payload: Dict[str, Any]) -> str:
        """Reject synchronous cloud-to-desktop writes."""
        raise NotImplementedError(
            "Direct synchronous writing to local Tally Prime XML gateway from the cloud API "
            "is not permitted. Accounting writes must be queued for bridge daemon export/import."
        )

    def _format_date_to_tally(self, date_str: str) -> str:
        """Convert YYYY-MM-DD or DD/MM/YYYY to Tally YYYYMMDD format."""
        clean = date_str.replace("-", "").replace("/", "").strip()
        if len(clean) == 8:
            return clean
        return "19700101"

    async def get_sales_register(self, start_date: str, end_date: str) -> List[SalesRow]:
        """Fetch sales register rows from synced Tally vouchers."""
        if not self.db_pool:
            raise RuntimeError("Database pool not available for Tally get_sales_register")
            
        t_start = self._format_date_to_tally(start_date)
        t_end = self._format_date_to_tally(end_date)
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT voucher_number, date, party_name, entries
                FROM tally_vouchers
                WHERE firm_id = $1 AND company_name = $2
                  AND date >= $3 AND date <= $4
                  AND LOWER(voucher_type) LIKE '%sales%'
                ORDER BY date ASC
                """,
                self.firm_id, self.company_name, t_start, t_end,
            )
            
        sales_rows = []
        for row in rows:
            entries = json.loads(row["entries"]) if isinstance(row["entries"], str) else (row["entries"] or [])
            taxable_entries = [e for e in entries if any(k in str(e.get("ledger_name", "")).lower() for k in ("sales", "revenue", "income"))]
            if not taxable_entries:
                taxable_entries = [e for e in entries if str(e.get("ledger_name")) != str(row.get("party_name")) and not any(k in str(e.get("ledger_name", "")).lower() for k in ("gst", "tax", "duty"))]
            total_amt = sum(abs(parse_decimal(e.get("amount", 0))) for e in taxable_entries)
            if total_amt == 0 and entries:
                total_amt = abs(parse_decimal(entries[0].get("amount", 0)))
                
            taxable_paise = rupees_to_paise(total_amt)
            
            sales_rows.append(
                SalesRow(
                    invoice_number=str(row["voucher_number"]),
                    invoice_date=str(row["date"]),
                    customer_gstin="",
                    customer_name=str(row["party_name"] or "Cash/Bank"),
                    taxable_value_paise=taxable_paise,
                    igst_paise=0,
                    cgst_paise=0,
                    sgst_paise=0,
                    place_of_supply="",
                )
            )
        return sales_rows

    async def get_purchase_register(self, start_date: str, end_date: str) -> List[PurchaseRow]:
        """Fetch purchase register rows from synced Tally vouchers."""
        if not self.db_pool:
            raise RuntimeError("Database pool not available for Tally get_purchase_register")
            
        t_start = self._format_date_to_tally(start_date)
        t_end = self._format_date_to_tally(end_date)
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT voucher_number, date, party_name, entries
                FROM tally_vouchers
                WHERE firm_id = $1 AND company_name = $2
                  AND date >= $3 AND date <= $4
                  AND LOWER(voucher_type) LIKE '%purchase%'
                ORDER BY date ASC
                """,
                self.firm_id, self.company_name, t_start, t_end,
            )
            
        purchase_rows = []
        for row in rows:
            entries = json.loads(row["entries"]) if isinstance(row["entries"], str) else (row["entries"] or [])
            taxable_entries = [e for e in entries if any(k in str(e.get("ledger_name", "")).lower() for k in ("purchase", "expense", "cost"))]
            if not taxable_entries:
                taxable_entries = [e for e in entries if str(e.get("ledger_name")) != str(row.get("party_name")) and not any(k in str(e.get("ledger_name", "")).lower() for k in ("gst", "tax", "duty"))]
            total_amt = sum(abs(parse_decimal(e.get("amount", 0))) for e in taxable_entries)
            if total_amt == 0 and entries:
                total_amt = abs(parse_decimal(entries[0].get("amount", 0)))
                
            taxable_paise = rupees_to_paise(total_amt)
            
            purchase_rows.append(
                PurchaseRow(
                    invoice_number=str(row["voucher_number"]),
                    invoice_date=str(row["date"]),
                    supplier_gstin="",
                    supplier_name=str(row["party_name"] or "Cash/Bank"),
                    taxable_value_paise=taxable_paise,
                    total_gst_paise=0,
                )
            )
        return purchase_rows

    async def health(self) -> Dict[str, Any]:
        """Check sync health status from tally_sync_logs."""
        if not self.db_pool:
            return {"status": "error", "details": "Database pool unavailable"}
            
        async with self.db_pool.acquire() as conn:
            latest = await conn.fetchrow(
                """
                SELECT status, synced_at, ledgers_count, vouchers_count
                FROM tally_sync_logs
                WHERE firm_id = $1 AND company_name = $2
                ORDER BY synced_at DESC LIMIT 1
                """,
                self.firm_id, self.company_name,
            )
            
        if not latest:
            return {"status": "error", "details": f"No sync history found for firm '{self.firm_id}' and company '{self.company_name}'"}
            
        if str(latest["status"]) == "SUCCESS":
            return {
                "status": "healthy",
                "details": f"Synced {latest['ledgers_count']} ledgers, {latest['vouchers_count']} vouchers at {latest['synced_at']}",
            }
            
        return {"status": "error", "details": f"Last sync failed with status: {latest['status']}"}
