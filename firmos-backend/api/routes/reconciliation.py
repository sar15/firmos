"""Evidence-first bank and GSTR-2B reconciliation."""
from __future__ import annotations

from datetime import date, timedelta
import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.deps import FirmContext, get_current_firm, get_db
from engines.gstr2b_parser import parse_gstr2b_json
from engines.reconcile import reconcile
from models.schemas import ReconLine, ReconciliationResult
from core.errors import AppError
from core.money import rupees_to_paise

router = APIRouter(prefix="/api/reconciliation", tags=["reconciliation"])
logger = logging.getLogger(__name__)


def _period_bounds(period: str) -> tuple[str, str]:
    """Return inclusive ISO date bounds for GSTN MMYYYY periods."""
    if len(period) != 6 or not period.isdigit() or not 1 <= int(period[:2]) <= 12:
        raise HTTPException(status_code=422, detail="period must use MMYYYY, for example 062026")
    start = date(int(period[2:]), int(period[:2]), 1)
    end = (date(start.year + (start.month == 12), start.month % 12 + 1, 1) - timedelta(days=1))
    return start.isoformat(), end.isoformat()


async def _build_purchase_source(conn, firm_id: str, client_id: str, period: str) -> list[ReconLine]:
    """Use the period projection the reviewer can open, never a live current-month guess."""
    rows = await conn.fetch(
        """SELECT id, bill_number, vendor_name, vendor_gstin, bill_date, total_paise
           FROM purchase_register
           WHERE firm_id = $1 AND client_id = $2 AND period = $3
           ORDER BY bill_date, id""",
        firm_id, client_id, period,
    )
    return [
        ReconLine(
            id=row["id"], date=row["bill_date"].isoformat(),
            description=f"Purchase - {row['vendor_name'] or 'Unknown'}",
            counterparty=row["vendor_name"] or "Unknown", amount=int(row["total_paise"]),
            ref=row["bill_number"] or None, gstin=row["vendor_gstin"] or None,
        )
        for row in rows
    ]


async def _build_uploaded_2b_target(conn, firm_id: str, client_id: str, period: str) -> list[ReconLine]:
    row = await conn.fetchrow(
        """SELECT payload FROM gstr2b_uploads
           WHERE firm_id = $1 AND client_id = $2 AND period = $3""",
        firm_id, client_id, period,
    )
    if not row:
        return []
    payload = row.get("payload")
    if payload is None:
        return []
    return parse_gstr2b_json(json.loads(payload) if isinstance(payload, str) else payload).lines


async def _build_bank_target_from_zoho(
    conn, firm_id: str, period: str, bank_account_id: str | None,
) -> list[ReconLine]:
    """Read the selected Zoho bank account for one period; never guess an account."""
    from core.security import decrypt_token
    from connectors.zoho_books.client import ZohoClient
    from connectors.zoho_books.sync import list_accounts, list_bank_transactions

    row = await conn.fetchrow(
        """SELECT access_token_enc, refresh_token_enc, external_account_id FROM connections
           WHERE firm_id = $1 AND connector_id = 'c1'""", firm_id,
    )
    if not row or not row["access_token_enc"]:
        raise AppError("CONNECTOR_AUTH_REQUIRED", "Connect Zoho Books before bank reconciliation.", status_code=409,
                       user_action="Reconnect Zoho Books.")
    try:
        client = ZohoClient(decrypt_token(row["access_token_enc"]), row["refresh_token_enc"], row["external_account_id"])
        if not bank_account_id:
            accounts = [a for a in (await list_accounts(client)).get("chartofaccounts", []) if a.get("account_type") == "bank"]
            if len(accounts) != 1:
                raise AppError("BANK_ACCOUNT_REQUIRED", "Select exactly one Zoho bank account.", status_code=409,
                               user_action="Choose the bank account to reconcile.")
            bank_account_id = accounts[0].get("account_id")
        start, end = _period_bounds(period)
        transactions = (await list_bank_transactions(client, bank_account_id, start, end)).get("banktransactions", [])
    except HTTPException:
        raise
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ZOHO_BANK_READ_FAILED", "Zoho bank transactions could not be read.", status_code=503,
                       retryable=True, user_action="Retry the reconciliation.") from exc
    return [
        ReconLine(
            id=f"zb-{txn.get('transaction_id', '')}", date=txn.get("date", ""),
            description=txn.get("reference_number") or txn.get("description", ""),
            counterparty=txn.get("payee") or txn.get("description") or "Unknown",
            amount=rupees_to_paise(txn.get("amount", 0)), ref=txn.get("reference_number") or None,
        )
        for txn in transactions
    ]


async def _build_bank_source(conn, firm_id: str, client_id: str, period: str) -> list[ReconLine]:
    start_text, end_text = _period_bounds(period)
    start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
    rows = await conn.fetch(
        """SELECT id, txn_date, description, amount, txn_type
           FROM bank_transactions
           WHERE firm_id = $1 AND client_id = $2 AND txn_date BETWEEN $3::date AND $4::date
           ORDER BY txn_date, id""", firm_id, client_id, start, end,
    )
    return [
        ReconLine(
            id=row["id"], date=row["txn_date"].isoformat(), description=row["description"],
            counterparty="Bank", amount=int(row["amount"]) if row["txn_type"] == "CREDIT" else -int(row["amount"]),
        )
        for row in rows
    ]


@router.get("/{client_id}", response_model=ReconciliationResult)
async def get_reconciliation(
    client_id: str,
    mode: Literal["GSTR2B_VS_PURCHASE", "BANK_STATEMENT"] = Query(default="GSTR2B_VS_PURCHASE"),
    period: str = Query(..., description="GSTN period in MMYYYY"),
    bank_account_id: str | None = Query(default=None),
    firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db),
):
    """Compare period-bound books against uploaded evidence or a selected Zoho account."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    _period_bounds(period)
    async with db_pool.acquire() as conn:
        if mode == "GSTR2B_VS_PURCHASE":
            source = await _build_purchase_source(conn, firm.firm_id, client_id, period)
            target = await _build_uploaded_2b_target(conn, firm.firm_id, client_id, period)
        else:
            source = await _build_bank_source(conn, firm.firm_id, client_id, period)
            target = await _build_bank_target_from_zoho(conn, firm.firm_id, period, bank_account_id)
    return reconcile(source, target)


class ReconciliationDecision(BaseModel):
    client_id: str
    period: str
    mode: Literal["GSTR2B_VS_PURCHASE", "BANK_STATEMENT"]
    source_id: str
    target_id: str | None = None


async def _save_decision(conn, match_id: str, decision: ReconciliationDecision, firm_id: str, status: str) -> None:
    await conn.execute(
        """INSERT INTO reconciliation_matches (id, firm_id, client_id, period, mode, source_id, target_id, status)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
           ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, target_id = EXCLUDED.target_id, updated_at = NOW()""",
        match_id, firm_id, decision.client_id, decision.period, decision.mode,
        decision.source_id, decision.target_id, status,
    )


@router.post("/matches/{match_id}/accept")
async def accept_match(match_id: str, decision: ReconciliationDecision, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    _period_bounds(decision.period)
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db_pool.acquire() as conn:
        await _save_decision(conn, match_id, decision, firm.firm_id, "ACCEPTED")
    return {"ok": True, "matchId": match_id, "status": "ACCEPTED"}


@router.post("/matches/{match_id}/reject")
async def reject_match(match_id: str, decision: ReconciliationDecision, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    _period_bounds(decision.period)
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db_pool.acquire() as conn:
        await _save_decision(conn, match_id, decision, firm.firm_id, "REJECTED")
    return {"ok": True, "matchId": match_id, "status": "REJECTED"}


@router.post("/bulk-accept")
async def bulk_accept_clean(
    client_id: str, period: str, mode: Literal["GSTR2B_VS_PURCHASE", "BANK_STATEMENT"] = Query(default="GSTR2B_VS_PURCHASE"),
    bank_account_id: str | None = Query(default=None), firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db),
):
    result = await get_reconciliation(client_id, mode, period, bank_account_id, firm, db_pool)
    accepted = [match for match in result.matches if match.status == "AUTO_MATCHED" and not match.flag and match.target]
    if db_pool:
        async with db_pool.acquire() as conn:
            for match in accepted:
                await _save_decision(conn, match.id, ReconciliationDecision(
                    client_id=client_id, period=period, mode=mode, source_id=match.source.id, target_id=match.target.id,
                ), firm.firm_id, "ACCEPTED")
    return {"ok": True, "accepted": len(accepted)}


@router.post("/upload-2b", response_model=ReconciliationResult)
async def upload_2b_and_reconcile(
    payload: dict, client_id: str, period: str,
    firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db),
):
    """Store a GSTN-downloaded 2B file as evidence, then reconcile that exact period."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    _period_bounds(period)
    target = parse_gstr2b_json(payload).lines
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO gstr2b_uploads (firm_id, client_id, period, payload)
               VALUES ($1, $2, $3, $4::jsonb)
               ON CONFLICT (firm_id, client_id, period) DO UPDATE SET payload = EXCLUDED.payload, uploaded_at = NOW()""",
            firm.firm_id, client_id, period, json.dumps(payload),
        )
        source = await _build_purchase_source(conn, firm.firm_id, client_id, period)
    return reconcile(source, target)
