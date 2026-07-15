"""Read-only agent tools for Zoho bank-match review."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import FirmContext, get_current_firm, get_db
from core.money import rupees_to_paise

router = APIRouter(prefix="/api/agent", tags=["agent-tools"])


class BankCandidateRequest(BaseModel):
    client_id: str
    period: str = Field(pattern=r"^(0[1-9]|1[0-2])\d{4}$")
    account_id: str
    bank_transaction_id: str


class ProposeBankMatchRequest(BankCandidateRequest):
    candidate_ids: list[str] = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=8, max_length=255)


async def _zoho_plugin(db_pool, firm_id: str, client_id: str):
    from connectors.zoho_books.credentials import ZohoCredentialService
    from connectors.zoho_books.plugin import ZohoBooksPlugin

    async with db_pool.acquire() as conn:
        installation = await conn.fetchrow(
            """SELECT id FROM connector_installations WHERE firm_id=$1 AND client_id=$2
               AND provider='ZOHO_BOOKS' AND status='AVAILABLE'""",
            firm_id,
            client_id,
        )
    if not installation:
        raise HTTPException(status_code=409, detail="Zoho Books is not connected")
    service = ZohoCredentialService(db_pool, str(installation["id"]))
    return ZohoBooksPlugin(await service.client())


@router.post("/bank-match-candidates")
async def get_bank_match_candidates(
    request: BankCandidateRequest,
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    """Read Zoho candidates and retain the evidence for operator review."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Bank matching store unavailable")
    firm.require("books.read")
    plugin = await _zoho_plugin(db_pool, firm.firm_id, request.client_id)
    result = await plugin.read(
        "zoho.read.bank_transaction.match_candidates",
        {"bank_transaction_id": request.bank_transaction_id},
    )
    candidates = result["matching_transactions"]
    async with db_pool.acquire() as conn:
        case = await conn.fetchrow(
            """INSERT INTO zoho_bank_match_cases
               (firm_id,client_id,period,account_id,bank_transaction_id,provider_snapshot)
               VALUES ($1,$2,$3,$4,$5,$6::jsonb)
               ON CONFLICT (firm_id,client_id,account_id,bank_transaction_id)
               DO UPDATE SET period=EXCLUDED.period,status='OPEN',
                 provider_snapshot=EXCLUDED.provider_snapshot,fetched_at=NOW()
               RETURNING id""",
            firm.firm_id,
            request.client_id,
            request.period,
            request.account_id,
            request.bank_transaction_id,
            json.dumps(result),
        )
        await conn.execute(
            "DELETE FROM zoho_bank_match_candidates WHERE case_id=$1", case["id"]
        )
        for candidate in candidates:
            await conn.execute(
                """INSERT INTO zoho_bank_match_candidates
                   (case_id,external_transaction_id,transaction_type,transaction_date,
                    amount_paise,counterparty,reference_number,is_best_match,raw)
                   VALUES ($1,$2,$3,$4::date,$5,$6,$7,$8,$9::jsonb)""",
                case["id"],
                str(candidate.get("transaction_id", "")),
                str(candidate.get("transaction_type", "")),
                candidate.get("date") or None,
                rupees_to_paise(candidate.get("amount", 0)),
                candidate.get("contact_name"),
                candidate.get("reference_number"),
                bool(candidate.get("is_best_match")),
                json.dumps(candidate),
            )
    return {
        "case_id": str(case["id"]),
        "bank_transaction_id": request.bank_transaction_id,
        "candidates": candidates,
    }


@router.post("/bank-match/propose")
async def propose_bank_match(
    request: ProposeBankMatchRequest,
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    """Fail closed until bank-match writes receive separate certification."""
    firm.require("books.propose")
    raise HTTPException(
        status_code=409, detail="Zoho bank-match writes are not certified in V1"
    )
