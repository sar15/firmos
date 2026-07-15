"""Read-only compatibility boundary for the retired Python bridge write API."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import FirmContext, get_current_firm, get_db

router = APIRouter(prefix="/api/bridge/actions", tags=["tally-bridge-actions"])


class TallyBridgeClaimRequest(BaseModel):
    tally_company: str = Field(min_length=1)
    bridge_device_id: str = Field(min_length=1)


class TallyBridgeResultRequest(BaseModel):
    correlation_id: str
    bridge_device_id: str
    status: Literal["SUCCEEDED", "FAILED", "NEEDS_REVIEW"]
    error_message: str | None = None


@router.post("/claim")
async def claim_action(
    _payload: TallyBridgeClaimRequest,
    _firm: FirmContext=Depends(get_current_firm), db_pool=Depends(get_db),
):
    """Python bridge reads remain compatible; writes require the secure desktop agent."""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database pool unavailable")
    return {"claimed": False, "action": None, "reason_code": "DESKTOP_AGENT_REQUIRED"}


@router.post("/{action_id}/result")
async def report_action_result(
    action_id: str, payload: TallyBridgeResultRequest,
    firm: FirmContext=Depends(get_current_firm), db_pool=Depends(get_db),
):
    """Close an old lease safely, but never certify an unverified legacy write."""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database pool unavailable")
    async with db_pool.acquire() as conn, conn.transaction():
        action = await conn.fetchrow(
            """SELECT status,lease_device_id,lease_expires_at FROM finance_actions
               WHERE id=$1 AND firm_id=$2 FOR UPDATE""", action_id, firm.firm_id,
        )
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        if action["status"] != "EXECUTING" or action["lease_device_id"] != payload.bridge_device_id:
            raise HTTPException(status_code=409, detail="Legacy action lease is invalid")
        if not action["lease_expires_at"] or action["lease_expires_at"] <= datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail="Legacy action lease has expired")
        final = "FAILED" if payload.status == "FAILED" else "NEEDS_REVIEW"
        await conn.execute(
            """UPDATE finance_actions SET status=$1,lease_device_id=NULL,lease_expires_at=NULL,
               updated_at=NOW() WHERE id=$2""", final, action_id,
        )
        await conn.execute(
            """UPDATE finance_runs SET status=$1,error_message=$2,finished_at=NOW()
               WHERE action_id=$3 AND correlation_id=$4""",
            final, payload.error_message or "Secure desktop read-back required", action_id,
            payload.correlation_id,
        )
    return {"ok": True, "action_id": action_id, "status": final}
