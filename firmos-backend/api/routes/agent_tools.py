"""Typed finance-agent tools.

# ponytail: the chat surface may propose only declared actions; accounting data
# stays behind explicit read tools and typed action proposals.
"""

import hashlib
import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.deps import FirmContext, get_current_firm, get_db
from core.finance_actions import (
    FinanceActionEngine,
    FinanceActionError,
    PayloadHashMismatchError,
)
from connectors.zoho_books.purchase_bill import build_purchase_bill
from connectors.tally.canonical import validate_purchase
from core.agent_experience import action_view, exception_view

router = APIRouter(prefix="/api/agent", tags=["agent-tools"])


class ProposeActionRequest(BaseModel):
    client_id: str
    period: str = Field(pattern=r"^(0[1-9]|1[0-2])\d{4}$")
    input_source_ids: list[str] = Field(min_length=1, max_length=50)
    provider: Literal["ZOHO_BOOKS", "TALLY_PRIME"]
    operation: Literal[
        "zoho.write.purchase_bill.create", "tally.write.purchase_voucher.create"
    ]
    payload: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=255)


class ApproveActionRequest(BaseModel):
    payload_hash: str = Field(min_length=64, max_length=64)


@router.get("/clients/{client_id}/context")
async def get_client_context(
    client_id: str,
    period: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    """Read the minimal evidence an agent needs before proposing an action."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Agent context unavailable")
    firm.require("books.read")
    async with db_pool.acquire() as conn:
        client_exists = await conn.fetchval(
            "SELECT 1 FROM clients WHERE id=$1 AND firm_id=$2",
            client_id,
            firm.firm_id,
        )
        if not client_exists:
            raise HTTPException(status_code=404, detail="Client was not found")
        sales = await conn.fetchrow(
            "SELECT COUNT(*) AS count, COALESCE(SUM(total_paise),0) AS total FROM sales_register WHERE firm_id=$1 AND client_id=$2 AND period=$3",
            firm.firm_id,
            client_id,
            period,
        )
        purchases = await conn.fetchrow(
            "SELECT COUNT(*) AS count, COALESCE(SUM(total_paise),0) AS total FROM purchase_register WHERE firm_id=$1 AND client_id=$2 AND period=$3",
            firm.firm_id,
            client_id,
            period,
        )
        rows = await conn.fetch(
            """SELECT a.*,d.document_id,d.missing_mappings FROM finance_actions a
               LEFT JOIN accounting_drafts d ON d.action_id=a.id AND d.firm_id=a.firm_id
               WHERE a.firm_id=$1 AND a.client_id=$2
               ORDER BY a.created_at DESC LIMIT 20""",
            firm.firm_id,
            client_id,
        )
        blockers = await conn.fetch(
            """SELECT id::text AS id,'MAPPING_BLOCKER' AS status,2 AS priority,
                      operation,'Approve the missing accounting mappings.' AS recovery_action
               FROM accounting_drafts WHERE firm_id=$1 AND client_id=$2
                 AND jsonb_typeof(missing_mappings)='array'
                 AND jsonb_array_length(missing_mappings)>0
               UNION ALL
               SELECT id,'EVIDENCE_FAILURE',1,'documents.extract.invoice',
                      'Open the document and retry extraction with readable evidence.'
               FROM extraction_runs WHERE firm_id=$1 AND client_id=$2
                 AND (status='FAILED' OR error_code IS NOT NULL)
               UNION ALL
               SELECT id,'DEADLINE_RISK',3,'compliance.review',
                      'Review the high-priority compliance decision and its evidence.'
               FROM decisions WHERE firm_id=$1 AND client_id=$2
                 AND lower(urgency)='high' AND status='needs_review'
               LIMIT 20""",
            firm.firm_id,
            client_id,
        )
    actions = [action_view(dict(row)) for row in rows]
    exceptions = [item for action in actions if (item := exception_view(action))]
    exceptions.extend(
        {
            "action_id": row["id"],
            "status": row["status"],
            "priority": row["priority"],
            "operation": row["operation"],
            "recovery_action": row["recovery_action"],
            "correlation_id": "",
        }
        for row in blockers
    )
    exceptions.sort(key=lambda item: item["priority"])
    return {
        "period": period,
        "sales": {"count": int(sales["count"]), "total_paise": int(sales["total"])},
        "purchases": {
            "count": int(purchases["count"]),
            "total_paise": int(purchases["total"]),
        },
        "recent_actions": actions,
        "exceptions": exceptions,
    }


@router.post("/actions/propose")
async def propose_action(
    payload: ProposeActionRequest,
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    """Create a typed action proposal; execution remains approval-gated."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Action store unavailable")
    firm.require("books.propose")
    expected = "ZOHO_BOOKS" if payload.operation.startswith("zoho.") else "TALLY_PRIME"
    if payload.provider != expected:
        raise HTTPException(
            status_code=422, detail="Provider does not support this operation"
        )
    source_ids = list(dict.fromkeys(payload.input_source_ids))
    async with db_pool.acquire() as conn:
        source_count = await conn.fetchval(
            """SELECT COUNT(*) FROM documents WHERE firm_id=$1 AND client_id=$2
               AND id=ANY($3::varchar[])""",
            firm.firm_id,
            payload.client_id,
            source_ids,
        )
    if source_count != len(source_ids):
        raise HTTPException(
            status_code=404, detail="One or more source documents were not found"
        )
    action_payload = {
        **payload.payload,
        "period": payload.period,
        "input_source_ids": source_ids,
        "source_document_id": source_ids[0],
    }
    installation_id = None
    if payload.operation == "zoho.write.purchase_bill.create":
        async with db_pool.acquire() as conn:
            installation = await conn.fetchrow(
                """SELECT id,configuration FROM connector_installations WHERE firm_id=$1
                   AND client_id=$2 AND provider='ZOHO_BOOKS' AND status='AVAILABLE'""",
                firm.firm_id,
                payload.client_id,
            )
        if not installation:
            raise HTTPException(
                status_code=409, detail="Zoho Books is not connected for this client"
            )
        configuration = installation["configuration"]
        if isinstance(configuration, str):
            configuration = json.loads(configuration)
        action_payload["organization_id"] = configuration.get("organization_id")
        action_payload.setdefault(
            "reference_number",
            f"FIRMOS-{hashlib.sha256(payload.idempotency_key.encode()).hexdigest()[:24]}",
        )
        build_purchase_bill(action_payload)
        installation_id = str(installation["id"])
    else:
        required = (
            "date",
            "party_ledger",
            "purchase_ledger",
            "total_paise",
            "tally_company",
        )
        if any(not payload.payload.get(key) for key in required):
            raise HTTPException(
                status_code=422,
                detail="Tally purchase voucher requires date, party_ledger, purchase_ledger, total_paise, and tally_company",
            )
        async with db_pool.acquire() as conn:
            installation = await conn.fetchrow(
                """SELECT id,configuration FROM connector_installations WHERE firm_id=$1
                   AND client_id=$2 AND provider='TALLY_PRIME' AND status='AVAILABLE'""",
                firm.firm_id,
                payload.client_id,
            )
        if not installation:
            raise HTTPException(
                status_code=409, detail="Tally Agent is not connected for this client"
            )
        configuration = installation["configuration"]
        if isinstance(configuration, str):
            configuration = json.loads(configuration)
        action_payload["tally_company"] = configuration.get("company_name")
        action_payload["company_guid"] = configuration.get("company_guid")
        validate_purchase(action_payload)
        installation_id = str(installation["id"])

    action = await FinanceActionEngine(db_pool).propose_action(
        firm_id=firm.firm_id,
        client_id=payload.client_id,
        provider=payload.provider,
        operation=payload.operation,
        payload=action_payload,
        idempotency_key=payload.idempotency_key,
        risk_level="HIGH",
        installation_id=installation_id,
        source_identity="agent-tool",
    )
    return action


@router.post("/actions/{action_id}/approve")
async def approve_action(
    action_id: str,
    approval: ApproveActionRequest,
    request: Request,
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    """Approve an unchanged proposal and atomically enqueue it for a worker."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Action store unavailable")
    firm.require("books.approve")
    engine = FinanceActionEngine(db_pool)
    try:
        async with db_pool.acquire() as conn:
            bound = await conn.fetchval(
                """SELECT 1 FROM finance_actions a LEFT JOIN accounting_drafts d
                   ON d.action_id=a.id AND d.firm_id=a.firm_id
                   WHERE a.id=$1::uuid AND a.firm_id=$2 AND a.payload_hash=$3 AND (
                     a.source_identity='agent-tool' OR
                     (d.version::text=a.source_version AND d.payload_hash=$3)
                   )""",
                action_id,
                firm.firm_id,
                approval.payload_hash,
            )
        if not bound:
            raise PayloadHashMismatchError(
                "The reviewed draft version changed; prepare it again before approval"
            )
        result = await engine.approve_action(
            action_id,
            firm.firm_id,
            firm.user_id,
            approval.payload_hash,
            request.state.correlation_id,
        )
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE accounting_drafts SET status='QUEUED',updated_at=NOW()
                   WHERE firm_id=$1 AND action_id=$2::uuid AND payload_hash=$3""",
                firm.firm_id,
                action_id,
                approval.payload_hash,
            )
        return result
    except PayloadHashMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FinanceActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/actions/{action_id}/cancel")
async def cancel_action(
    action_id: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    firm.require("books.approve")
    try:
        return await FinanceActionEngine(db_pool).cancel_action(action_id, firm.firm_id)
    except FinanceActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
