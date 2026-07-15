"""Device-owned purchase execution with mandatory cloud-verified read-back."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from api.deps import get_db
from api.routes.tally_agent_auth import DeviceContext, require_device
from connectors.platform.provider_objects import record_verification
from connectors.tally.canonical import compare_purchase, compare_sales, deterministic_remote_id, validate_purchase, validate_sales
from connectors.tally.versions import version_support
from core.feature_flags import scoped_write_block_reason

router = APIRouter()
OPERATIONS = ("tally.write.purchase_voucher.create", "tally.write.sales_voucher.create")


class ActionResult(BaseModel):
    status: str = Field(pattern="^(PROVIDER_ACCEPTED|FAILED|AMBIGUOUS)$")
    provider_guid: str = Field(default="", max_length=255)
    voucher_number: str = Field(default="", max_length=100)
    error_code: str = Field(default="", max_length=100)
    readback: dict | None = None


async def _precondition(conn, device: DeviceContext, operation: str) -> str | None:
    row = await conn.fetchrow(
        """SELECT last_seen_at,license_mode,tally_version,write_enabled,
           (last_seen_at>NOW()-interval '15 minutes') AS healthy
           FROM tally_devices WHERE id=$1::uuid""", device.id,
    )
    if not row or not row["healthy"]:
        return "DEVICE_UNHEALTHY"
    if str(row["license_mode"] or "").upper() in {"EDUCATIONAL", "SILVER EDUCATIONAL"}:
        return "TALLY_LICENSE_UNSUPPORTED"
    if not version_support(str(row["tally_version"] or ""))["xml_write"]:
        return "TALLY_VERSION_UNCERTIFIED"
    if not row["write_enabled"]:
        return "INSTALLATION_WRITE_DISABLED"
    synced = await conn.fetchval(
        """SELECT 1 FROM tally_sync_logs WHERE installation_id=$1::uuid
           AND company_guid=$2 AND status='SUCCESS' AND completeness='COMPLETE' LIMIT 1""",
        device.installation_id, device.company_guid,
    )
    if not synced:
        return "READ_SYNC_REQUIRED"
    certified = await conn.fetchval(
        """SELECT 1 FROM capability_certifications WHERE firm_id=$1 AND capability_key=$2
           AND provider='TALLY_PRIME' AND provider_version=$3 AND installation_id=$4::uuid
           AND certification_level=5""",
        device.firm_id, operation, row["tally_version"], device.installation_id,
    )
    if not certified:
        return "CERTIFICATION_L5_REQUIRED"
    types = set(await conn.fetchval(
        """SELECT COALESCE(array_agg(DISTINCT mapping_type),'{}') FROM connector_mappings
           WHERE installation_id=$1::uuid AND active""",
        device.installation_id,
    ) or [])
    if not {"company", "ledger"}.issubset(types):
        return "MAPPINGS_REQUIRED"
    return await scoped_write_block_reason(
        conn, "TALLY_PRIME", firm_id=device.firm_id, client_id=device.client_id,
        capability_key=operation,
    )


@router.post("/actions/claim")
async def claim_action(
    response: Response, device: DeviceContext=Depends(require_device), db_pool=Depends(get_db),
):
    async with db_pool.acquire() as conn, conn.transaction():
        await conn.execute(
            """UPDATE finance_actions SET status='RETRY_SCHEDULED',lease_device_id=NULL,
               lease_expires_at=NULL WHERE installation_id=$1::uuid AND provider='TALLY_PRIME'
               AND status='CLAIMED' AND lease_expires_at<NOW()""", device.installation_id,
        )
        await conn.execute(
            """UPDATE finance_actions SET status='QUEUED' WHERE installation_id=$1::uuid
               AND provider='TALLY_PRIME' AND status='RETRY_SCHEDULED' AND attempt_number<3""",
            device.installation_id,
        )
        action = await conn.fetchrow(
            """SELECT * FROM finance_actions WHERE firm_id=$1 AND client_id=$2
               AND installation_id=$3::uuid AND provider='TALLY_PRIME' AND operation=ANY($4::text[])
               AND status='QUEUED' AND attempt_number<3
               ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1""",
            device.firm_id, device.client_id, device.installation_id, list(OPERATIONS),
        )
        if not action:
            response.status_code = 204
            return None
        reason = await _precondition(conn, device, action["operation"])
        if reason: raise HTTPException(status_code=409, detail={"code": reason})
        payload = validate_sales(dict(action["payload"])) if action["operation"] == OPERATIONS[1] else validate_purchase(dict(action["payload"]))
        if payload["company_guid"] != device.company_guid:
            raise HTTPException(status_code=409, detail={"code": "COMPANY_IDENTITY_MISMATCH"})
        ledger_names = list({line["ledger_name"] for line in payload["entries"]})
        ledger_count = await conn.fetchval(
            """SELECT count(DISTINCT name) FROM tally_ledgers WHERE installation_id=$1::uuid
               AND company_guid=$2 AND active AND name=ANY($3::text[])""",
            device.installation_id, device.company_guid,
            ledger_names,
        )
        if ledger_count != len(ledger_names):
            raise HTTPException(status_code=409, detail={"code": "LEDGER_IDENTITY_NOT_FOUND"})
        await conn.execute(
            """UPDATE finance_actions SET status='CLAIMED',lease_device_id=$1,
               lease_expires_at=NOW()+interval '90 seconds',attempt_number=attempt_number+1
               WHERE id=$2""", device.id, action["id"],
        )
        await conn.execute(
            """UPDATE automation_jobs SET status='CLAIMED',lease_owner=$1,
               lease_expires_at=NOW()+interval '90 seconds',attempt_count=attempt_count+1,
               updated_at=NOW() WHERE kind='FINANCE_ACTION' AND aggregate_id=$2""",
            f"tally:{device.id}", str(action["id"]),
        )
    return {
        "action_id": str(action["id"]), "operation": action["operation"],
        "remote_id": deterministic_remote_id(str(action["id"])), "payload": payload,
        "correlation_id": action["correlation_id"] or str(uuid.uuid4()),
    }


@router.post("/actions/{action_id}/lease")
async def renew_lease(
    action_id: uuid.UUID, device: DeviceContext=Depends(require_device), db_pool=Depends(get_db),
):
    async with db_pool.acquire() as conn:
        renewed = await conn.fetchval(
            """UPDATE finance_actions SET lease_expires_at=NOW()+interval '90 seconds'
               WHERE id=$1 AND firm_id=$2 AND installation_id=$3::uuid
               AND lease_device_id=$4 AND status='CLAIMED' RETURNING id""",
            action_id, device.firm_id, device.installation_id, device.id,
        )
    if not renewed:
        raise HTTPException(status_code=409, detail={"code": "ACTION_LEASE_INVALID"})
    return {"status": "CLAIMED", "lease_seconds": 90}


@router.post("/actions/{action_id}/result")
async def report_result(
    action_id: uuid.UUID, body: ActionResult, device: DeviceContext=Depends(require_device),
    db_pool=Depends(get_db),
):
    async with db_pool.acquire() as conn, conn.transaction():
        action = await conn.fetchrow(
            """SELECT * FROM finance_actions WHERE id=$1 AND firm_id=$2 AND installation_id=$3::uuid
               AND lease_device_id=$4 AND status='CLAIMED' FOR UPDATE""",
            action_id, device.firm_id, device.installation_id, device.id,
        )
        if not action:
            raise HTTPException(status_code=409, detail={"code": "ACTION_LEASE_INVALID"})
        await conn.execute("UPDATE finance_actions SET status='EXECUTING' WHERE id=$1", action_id)
        if body.status != "PROVIDER_ACCEPTED" or not body.provider_guid or not body.readback:
            await conn.execute(
                """UPDATE finance_actions SET status=$1,lease_expires_at=NULL WHERE id=$2""",
                "NEEDS_REVIEW" if body.status == "AMBIGUOUS" else "FAILED", action_id,
            )
            job_state = "NEEDS_REVIEW" if body.status == "AMBIGUOUS" else "FAILED"
            await _finish_job(conn, action_id, job_state, body.error_code or body.status)
            return {"status": job_state, "verified": False}
        remote_id = deterministic_remote_id(str(action_id))
        is_sales = action["operation"] == OPERATIONS[1]
        mismatches = (compare_sales if is_sales else compare_purchase)(dict(action["payload"]), body.readback, remote_id)
        if str(body.readback.get("guid") or "") != body.provider_guid:
            mismatches["provider_guid"] = {
                "expected": body.provider_guid, "actual": body.readback.get("guid"),
            }
        await conn.execute(
            """UPDATE finance_actions SET status='PROVIDER_ACCEPTED',external_reference_id=$1 WHERE id=$2""",
            body.provider_guid, action_id,
        )
        await conn.execute("UPDATE finance_actions SET status='VERIFYING' WHERE id=$1", action_id)
        verification_id = await record_verification(
            conn, firm_id=device.firm_id, installation_id=device.installation_id,
            action_id=str(action_id), object_type="tally_sales_voucher" if is_sales else "tally_purchase_voucher",
            provider_id=body.provider_guid, values=body.readback, mismatches=mismatches,
            correlation_id=action["correlation_id"] or str(uuid.uuid4()),
            provider_version=body.readback.get("tally_version"),
        )
        final = "NEEDS_REVIEW" if mismatches else "SUCCEEDED"
        if not mismatches:
            if is_sales:
                from core.sales_invoices.projection import project_verified_sale
                await project_verified_sale(conn, str(action_id), verification_id)
            else:
                from core.purchase_invoices.projection import project_verified_purchase
                await project_verified_purchase(conn, str(action_id), verification_id)
        await conn.execute(
            "UPDATE finance_actions SET status=$1,lease_expires_at=NULL WHERE id=$2", final, action_id,
        )
        await _finish_job(conn, action_id, final, "READBACK_MISMATCH" if mismatches else "")
    return {"status": final, "verified": not mismatches, "verification_id": verification_id,
            "mismatches": mismatches}


async def _finish_job(conn, action_id, status: str, error: str) -> None:
    await conn.execute(
        """UPDATE automation_jobs SET status=$1,lease_owner=NULL,lease_expires_at=NULL,updated_at=NOW()
           WHERE kind='FINANCE_ACTION' AND aggregate_id=$2""", status, str(action_id),
    )
