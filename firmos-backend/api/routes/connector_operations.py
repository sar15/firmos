"""Read-only connector operations plus explicit mapping approval."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.deps import FirmContext, get_current_firm, get_db
from connectors.platform.mappings import approve_mapping

router = APIRouter(prefix="/api/connector-operations", tags=["connector-operations"])


@router.get("")
async def operations(firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    firm.require("books.read")
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT i.id,i.client_id,i.provider,i.display_name,i.status,i.configuration,
              i.last_probe_at,i.last_success_at,
              EXISTS(SELECT 1 FROM connector_credentials c WHERE c.installation_id=i.id AND c.revoked_at IS NULL) credential_healthy,
              (SELECT c.expires_at FROM connector_credentials c WHERE c.installation_id=i.id AND c.revoked_at IS NULL ORDER BY c.version DESC LIMIT 1) token_expires_at,
              (SELECT c.data_center FROM connector_credentials c WHERE c.installation_id=i.id AND c.revoked_at IS NULL ORDER BY c.version DESC LIMIT 1) data_center,
              COALESCE((SELECT to_jsonb(c.scopes) FROM connector_credentials c WHERE c.installation_id=i.id AND c.revoked_at IS NULL ORDER BY c.version DESC LIMIT 1),'[]') scopes,
              COALESCE((SELECT jsonb_agg(jsonb_build_object('key',c.capability_key,'state',c.state,'reason',c.reason_code)) FROM connector_capabilities c WHERE c.installation_id=i.id),'[]') capabilities,
              (SELECT max(finished_at) FROM connector_sync_jobs j WHERE j.installation_id=i.id AND j.completeness='COMPLETE') last_complete_sync,
              (SELECT count(*) FROM connector_mappings m WHERE m.installation_id=i.id AND m.active) mapping_count,
              (SELECT count(*) FROM connector_sync_jobs j WHERE j.installation_id=i.id
               AND j.completeness='PARTIAL' AND j.status IN ('QUEUED','FAILED')) partial_syncs,
              COALESCE((SELECT jsonb_agg(jsonb_build_object('capability_key',c.capability_key,
               'level',c.certification_level,'provider_version',c.provider_version))
               FROM capability_certifications c WHERE c.installation_id=i.id),'[]') certifications,
              EXISTS(SELECT 1 FROM worker_heartbeats h WHERE h.firm_id=i.firm_id AND h.seen_at>NOW()-interval '2 minutes') worker_healthy,
              (SELECT count(*) FROM automation_jobs j JOIN finance_actions a ON a.id::text=j.aggregate_id
               WHERE a.installation_id=i.id AND j.status IN ('QUEUED','CLAIMED','EXECUTING')) pending_writes,
              (SELECT count(*) FROM automation_jobs j JOIN finance_actions a ON a.id::text=j.aggregate_id
               WHERE a.installation_id=i.id AND j.status IN ('FAILED','DEAD_LETTER')) failed_writes,
              (SELECT count(*) FROM verification_results v JOIN finance_actions a ON a.id=v.action_id
               WHERE a.installation_id=i.id AND v.status!='MATCHED') verification_mismatches,
              COALESCE((SELECT jsonb_agg(x) FROM (SELECT j.id,j.capability_key,j.status,j.completeness,
               j.processed_count,j.mapping_blockers,j.finished_at FROM connector_sync_jobs j
               WHERE j.installation_id=i.id ORDER BY j.created_at DESC LIMIT 8) x),'[]') recent_syncs,
              COALESCE((SELECT jsonb_agg(x) FROM (SELECT v.mismatches,v.created_at
               FROM verification_results v JOIN finance_actions a ON a.id=v.action_id
               WHERE a.installation_id=i.id AND v.status!='MATCHED'
               ORDER BY v.created_at DESC LIMIT 3) x),'[]') mismatch_details
              FROM connector_installations i WHERE i.firm_id=$1 ORDER BY i.provider""", firm.firm_id,
        )
    return {"installations": [dict(row) for row in rows]}


class MappingApproval(BaseModel):
    installation_id: str; mapping_type: str; internal_id: str; provider_id: str


@router.post("/mappings/approve")
async def approve(request: MappingApproval, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    firm.require("connector.manage")
    async with db_pool.acquire() as conn:
        installation = await conn.fetchval("SELECT id FROM connector_installations WHERE id=$1 AND firm_id=$2", request.installation_id, firm.firm_id)
        if not installation: raise HTTPException(status_code=404, detail={"code": "INSTALLATION_NOT_FOUND"})
        await approve_mapping(conn, firm_id=firm.firm_id, installation_id=request.installation_id,
                              mapping_type=request.mapping_type, internal_id=request.internal_id,
                              provider_id=request.provider_id, approved_by=firm.user_id)
    return {"status": "APPROVED"}


@router.post("/sync-jobs/{job_id}/retry")
async def retry_sync_job(
    job_id: uuid.UUID, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db),
):
    """Resume a failed read job from its saved cursor; financial writes are never retried here."""
    firm.require("connector.manage")
    async with db_pool.acquire() as conn, conn.transaction():
        job = await conn.fetchrow(
            """SELECT j.id FROM connector_sync_jobs j JOIN connector_installations i
               ON i.id=j.installation_id WHERE j.id=$1 AND i.firm_id=$2
               AND j.status='FAILED' FOR UPDATE""", job_id, firm.firm_id,
        )
        if not job:
            raise HTTPException(status_code=409, detail={"code": "SYNC_JOB_NOT_RETRYABLE"})
        await conn.execute(
            """UPDATE connector_sync_jobs SET status='QUEUED',lease_owner=NULL,
               lease_expires_at=NULL,finished_at=NULL,mapping_blockers='[]'::jsonb WHERE id=$1""",
            job_id,
        )
    return {"status": "QUEUED", "job_id": str(job_id)}
