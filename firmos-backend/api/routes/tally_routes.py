"""Tally Prime Cloud API Receiver Routes.

Receives synchronized ledgers and vouchers pushed over HTTPS from the local
tally_bridge daemon running in the CA's office. Stores canonical records in
tally_ledgers and tally_vouchers with strict idempotency enforcement.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import get_current_firm, FirmContext, get_db

router = APIRouter(prefix="/api/tally", tags=["tally"])
logger = logging.getLogger("api.tally")


async def _execute_many(conn, statement: str, rows: list[tuple]) -> None:
    """Use one asyncpg batch round-trip; test doubles keep the simple fallback."""
    if not rows:
        return
    if hasattr(conn, "executemany"):
        await conn.executemany(statement, rows)
        return
    for row in rows:
        await conn.execute(statement, *row)


class TallyLedgerPayload(BaseModel):
    guid: str = Field(..., description="Canonical Tally GUID or fallback unique identifier")
    name: str = Field(..., description="Ledger account name")
    parent_group: str = Field(..., description="Parent accounting group in Tally")
    opening_balance: float = Field(default=0.0, description="Opening balance amount")
    closing_balance: float = Field(default=0.0, description="Closing balance amount")
    is_revenue: bool = Field(default=False, description="Whether ledger represents revenue/expense item")


class TallyVoucherEntryPayload(BaseModel):
    ledger_name: str = Field(..., description="Name of the ledger in this voucher entry")
    amount: float = Field(default=0.0, description="Amount (debit/credit value)")


class TallyVoucherPayload(BaseModel):
    guid: str = Field(..., description="Canonical Tally GUID for this voucher")
    voucher_number: str = Field(..., description="Voucher number or UNNUMBERED")
    date: str = Field(..., description="Voucher date in YYYYMMDD format")
    voucher_type: str = Field(..., description="Voucher type name (e.g. Journal, Sales, Payment)")
    party_name: Optional[str] = Field(default="", description="Party ledger name if applicable")
    narration: Optional[str] = Field(default="", description="Voucher narration / memo")
    entries: List[TallyVoucherEntryPayload] = Field(default_factory=list, description="List of ledger line entries")


class TallySyncPeriod(BaseModel):
    from_date: str = Field(..., description="Start date in YYYYMMDD")
    to_date: str = Field(..., description="End date in YYYYMMDD")


class TallyPushPayload(BaseModel):
    sync_version: str = Field(default="1.0", description="Bridge schema protocol version")
    timestamp: str = Field(..., description="ISO timestamp of sync execution")
    tally_company: str = Field(..., description="Name of the exported Tally company")
    period: TallySyncPeriod = Field(..., description="Date range of exported vouchers")
    ledgers: List[TallyLedgerPayload] = Field(default_factory=list, description="Exported ledgers")
    vouchers: List[TallyVoucherPayload] = Field(default_factory=list, description="Exported vouchers")


@router.post("/push", status_code=status.HTTP_200_OK)
async def push_tally_data(
    payload: TallyPushPayload,
    x_idempotency_key: str = Header(..., alias="X-Idempotency-Key", description="Stable key for the exact sync payload"),
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db),
) -> Dict[str, Any]:
    """Ingest synchronized ledgers and vouchers from the office Tally bridge.
    
    Why idempotency: Network flakes over office internet can cause the bridge daemon
    to retry POST requests. Using X-Idempotency-Key and ON CONFLICT (firm_id, tally_guid)
    guarantees exact once-only processing without duplicating ledger or voucher rows.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database connection pool unavailable")
        
    async with db_pool.acquire() as conn:
        # 1. Check idempotency log
        existing_log = await conn.fetchrow(
            "SELECT id, status, ledgers_count, vouchers_count FROM tally_sync_logs WHERE firm_id = $1 AND idempotency_key = $2",
            firm.firm_id, x_idempotency_key,
        )
        if existing_log:
            logger.info("Idempotent hit for key %s (firm: %s)", x_idempotency_key, firm.firm_id)
            return {
                "status": "ok",
                "message": "Idempotent hit: payload already processed",
                "ledgers_synced": existing_log["ledgers_count"],
                "vouchers_synced": existing_log["vouchers_count"],
            }
            
        logger.info("Processing Tally push for firm %s (company: %s, ledgers: %d, vouchers: %d)",
                    firm.firm_id, payload.tally_company, len(payload.ledgers), len(payload.vouchers))
                    
        # 2. Execute ingest inside atomic database transaction
        async with conn.transaction():
            # Batch independent upserts to keep the snapshot transaction short.
            ledger_statement = """
                    INSERT INTO tally_ledgers (
                        firm_id, company_name, tally_guid, name, parent_group,
                        opening_balance, closing_balance, is_revenue, synced_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    ON CONFLICT (firm_id, tally_guid) DO UPDATE SET
                        name = EXCLUDED.name,
                        parent_group = EXCLUDED.parent_group,
                        opening_balance = EXCLUDED.opening_balance,
                        closing_balance = EXCLUDED.closing_balance,
                        is_revenue = EXCLUDED.is_revenue,
                        synced_at = NOW()
                    """
            await _execute_many(conn, ledger_statement, [
                (firm.firm_id, payload.tally_company, led.guid, led.name, led.parent_group,
                 led.opening_balance, led.closing_balance, led.is_revenue)
                for led in payload.ledgers
            ])

            voucher_statement = """
                    INSERT INTO tally_vouchers (
                        firm_id, company_name, tally_guid, voucher_number, date,
                        voucher_type, party_name, narration, entries, synced_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, NOW())
                    ON CONFLICT (firm_id, tally_guid) DO UPDATE SET
                        voucher_number = EXCLUDED.voucher_number,
                        date = EXCLUDED.date,
                        voucher_type = EXCLUDED.voucher_type,
                        party_name = EXCLUDED.party_name,
                        narration = EXCLUDED.narration,
                        entries = EXCLUDED.entries,
                        synced_at = NOW()
                    """
            await _execute_many(conn, voucher_statement, [
                (firm.firm_id, payload.tally_company, vch.guid, vch.voucher_number, vch.date,
                 vch.voucher_type, vch.party_name, vch.narration,
                 json.dumps([entry.model_dump() for entry in vch.entries]))
                for vch in payload.vouchers
            ])
                
            # Record success in idempotency log
            await conn.execute(
                """
                INSERT INTO tally_sync_logs (
                    firm_id, company_name, idempotency_key, ledgers_count, vouchers_count, status, synced_at
                ) VALUES ($1, $2, $3, $4, $5, 'SUCCESS', NOW())
                """,
                firm.firm_id, payload.tally_company, x_idempotency_key, len(payload.ledgers), len(payload.vouchers),
            )
            
    logger.info("Successfully ingested Tally sync for firm %s", firm.firm_id)
    return {
        "status": "ok",
        "message": f"Successfully synced {len(payload.ledgers)} ledgers and {len(payload.vouchers)} vouchers",
        "ledgers_synced": len(payload.ledgers),
        "vouchers_synced": len(payload.vouchers),
    }


@router.get("/status", status_code=status.HTTP_200_OK)
async def get_tally_sync_status(
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve the current synchronization status and record count for Tally Prime data."""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database connection pool unavailable")
        
    async with db_pool.acquire() as conn:
        latest_log = await conn.fetchrow(
            "SELECT company_name, synced_at, ledgers_count, vouchers_count, status FROM tally_sync_logs WHERE firm_id = $1 ORDER BY synced_at DESC LIMIT 1",
            firm.firm_id,
        )
        total_ledgers = await conn.fetchval("SELECT COUNT(*) FROM tally_ledgers WHERE firm_id = $1", firm.firm_id)
        total_vouchers = await conn.fetchval("SELECT COUNT(*) FROM tally_vouchers WHERE firm_id = $1", firm.firm_id)
        
    return {
        "is_connected": latest_log is not None,
        "company_name": latest_log["company_name"] if latest_log else "",
        "last_synced_at": latest_log["synced_at"].isoformat() if latest_log and latest_log["synced_at"] else None,
        "total_ledgers": total_ledgers or 0,
        "total_vouchers": total_vouchers or 0,
        "status": latest_log["status"] if latest_log else "DISCONNECTED",
    }
