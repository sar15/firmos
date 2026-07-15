"""AY-specific ITR preparation; filing remains an evidenced external action."""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from api.deps import FirmContext, get_current_firm, get_db
from core.itr_drafting import aggregate_sources, reconciliation_pairs

router = APIRouter(prefix="/api/itr", tags=["itr-workspaces"])


def _hash(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows,sort_keys=True,default=str,separators=(",", ":")).encode()).hexdigest()


class WorkspaceRequest(BaseModel):
    client_id: str
    assessment_year: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}$")
    taxpayer_pan: str = Field(pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    taxpayer_name: str = Field(min_length=2,max_length=255)


class SourceRequest(BaseModel):
    source_type: str = Field(pattern=r"^(AIS|TIS|26AS|FORM16|FORM16A|BOOKS|BANK|EVIDENCE)$")
    source_period: str
    taxpayer_pan: str = Field(pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    source_version: str
    document_id: str|None=None
    extracted_values: dict=Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_values(self):
        if not self.extracted_values:
            raise ValueError("Extracted source values are required")
        if any(not key.endswith("_paise") or not isinstance(value,int) for key,value in self.extracted_values.items()):
            raise ValueError("Source values must be integer paise fields")
        return self


class AuthorizationRequest(BaseModel):
    authorized_by: str
    evidence_reference: str
    granted_to: str|None=None
    permissions: list[str]
    granted_at: str


class ScheduleLine(BaseModel):
    schedule_key: str
    line_key: str
    amount_paise: int
    source_links: list[dict]
    rule_id: str|None=None
    rounding_rule: str="NEAREST_RUPEE"
    reviewer_adjustment_paise: int=0
    explanation: str


class FilingEventRequest(BaseModel):
    event_type: str = Field(pattern=r"^(FILED_EXTERNALLY|PAYMENT_RECORDED|E_VERIFIED|REJECTED|ACKNOWLEDGEMENT_UPLOADED)$")
    reference: str
    evidence_reference: str|None=None
    occurred_at: str


async def _require_authorization(conn, workspace_id, permission: str, user_id: str) -> None:
    allowed=await conn.fetchval(
        "SELECT 1 FROM itr_authorizations WHERE workspace_id=$1::uuid AND $2=ANY(permissions) AND granted_to=$3::uuid AND revoked_at IS NULL LIMIT 1",
        workspace_id,permission,user_id,
    )
    if not allowed:
        raise HTTPException(409,f"Taxpayer authorization with {permission.lower()} permission is required")


@router.post("/workspaces",status_code=201)
async def create(body: WorkspaceRequest,firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    firm.require("books.propose")
    async with db_pool.acquire() as conn:
        row=await conn.fetchrow(
            """INSERT INTO itr_workspaces(firm_id,client_id,assessment_year,taxpayer_pan,taxpayer_name)
               VALUES($1,$2,$3,$4,$5) ON CONFLICT(firm_id,client_id,assessment_year) DO UPDATE SET
               taxpayer_pan=EXCLUDED.taxpayer_pan,taxpayer_name=EXCLUDED.taxpayer_name,updated_at=NOW() RETURNING *""",
            firm.firm_id,body.client_id,body.assessment_year,body.taxpayer_pan,body.taxpayer_name)
    return dict(row)


@router.get("/workspaces/latest")
async def latest(client_id:str,assessment_year:str,firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    async with db_pool.acquire() as conn:
        workspace=await conn.fetchrow("SELECT * FROM itr_workspaces WHERE firm_id=$1 AND client_id=$2 AND assessment_year=$3",firm.firm_id,client_id,assessment_year)
        if not workspace: raise HTTPException(404,"ITR workspace not created")
        sources=await conn.fetch("SELECT * FROM itr_sources WHERE workspace_id=$1 ORDER BY created_at",workspace["id"])
        reconciliation=await conn.fetch("SELECT * FROM itr_reconciliation_items WHERE workspace_id=$1 ORDER BY category",workspace["id"])
        lines=await conn.fetch("SELECT * FROM itr_schedule_lines WHERE workspace_id=$1 ORDER BY schedule_key,line_key",workspace["id"])
        authorizations=await conn.fetch("SELECT authorized_by,evidence_reference,permissions,granted_at FROM itr_authorizations WHERE workspace_id=$1 ORDER BY granted_at",workspace["id"])
    return {"workspace":dict(workspace),"sources":[dict(x) for x in sources],
            "reconciliation":[dict(x) for x in reconciliation],"schedule_lines":[dict(x) for x in lines],
            "authorizations":[dict(x) for x in authorizations]}


@router.post("/workspaces/{workspace_id}/sources",status_code=201)
async def add_source(workspace_id:str,body:SourceRequest,firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    firm.require("books.propose")
    async with db_pool.acquire() as conn,conn.transaction():
        workspace=await conn.fetchrow("SELECT * FROM itr_workspaces WHERE id=$1::uuid AND firm_id=$2 FOR UPDATE",workspace_id,firm.firm_id)
        if not workspace: raise HTTPException(404,"Workspace not found")
        await _require_authorization(conn,workspace_id,"PREPARE",firm.user_id)
        if workspace["taxpayer_pan"]!=body.taxpayer_pan: raise HTTPException(422,"Source taxpayer does not match the workspace")
        row=await conn.fetchrow(
            """INSERT INTO itr_sources(workspace_id,firm_id,source_type,source_period,taxpayer_pan,document_id,
               source_version,extracted_values) VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb) RETURNING *""",
            workspace["id"],firm.firm_id,body.source_type,body.source_period,body.taxpayer_pan,
            body.document_id,body.source_version,json.dumps(body.extracted_values))
        sources=[dict(x) for x in await conn.fetch("SELECT source_type,source_version,extracted_values FROM itr_sources WHERE workspace_id=$1 ORDER BY id",workspace["id"])]
        digest=_hash(sources)
        await conn.execute("DELETE FROM itr_schedule_lines WHERE workspace_id=$1",workspace["id"])
        await conn.execute("UPDATE itr_workspaces SET source_hash=$1,computation='{}'::jsonb,stale=(approved_source_hash IS NOT NULL AND approved_source_hash<>$1),status=CASE WHEN approved_source_hash IS NOT NULL AND approved_source_hash<>$1 THEN 'NEEDS_REVIEW' ELSE 'DATA_REQUIRED' END,updated_at=NOW() WHERE id=$2",digest,workspace["id"])
    return dict(row)


@router.post("/workspaces/{workspace_id}/authorizations",status_code=201)
async def authorize(workspace_id:str,body:AuthorizationRequest,firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    firm.require("books.propose")
    if not set(body.permissions).issubset({"VIEW","PREPARE","APPROVE"}) or not body.permissions:
        raise HTTPException(422,"Choose view, prepare, or approve permissions")
    async with db_pool.acquire() as conn:
        owned=await conn.fetchval("SELECT 1 FROM itr_workspaces WHERE id=$1::uuid AND firm_id=$2",workspace_id,firm.firm_id)
        if not owned: raise HTTPException(404,"Workspace not found")
        row=await conn.fetchrow("INSERT INTO itr_authorizations(workspace_id,firm_id,authorized_by,evidence_reference,permissions,granted_to,granted_at) VALUES($1,$2,$3,$4,$5::text[],$6::uuid,$7::timestamptz) RETURNING *",workspace_id,firm.firm_id,body.authorized_by,body.evidence_reference,body.permissions,body.granted_to or firm.user_id,body.granted_at)
    return dict(row)


@router.post("/workspaces/{workspace_id}/reconcile")
async def reconcile(workspace_id:str,firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    firm.require("books.propose")
    async with db_pool.acquire() as conn,conn.transaction():
        workspace=await conn.fetchrow("SELECT * FROM itr_workspaces WHERE id=$1::uuid AND firm_id=$2",workspace_id,firm.firm_id)
        if not workspace: raise HTTPException(404,"Workspace not found")
        await _require_authorization(conn,workspace_id,"PREPARE",firm.user_id)
        sources=await conn.fetch("SELECT source_type,extracted_values FROM itr_sources WHERE workspace_id=$1",workspace["id"])
        by_type=aggregate_sources(sources)
        await conn.execute("DELETE FROM itr_reconciliation_items WHERE workspace_id=$1",workspace["id"])
        results=[]
        for category,values in reconciliation_pairs(by_type):
            present_types=set(by_type);available={"AIS":"AIS" in present_types,"BOOKS":"BOOKS" in present_types,
              "26AS":"26AS" in present_types,"FORMS":bool({"FORM16","FORM16A"}&present_types),"BANK":"BANK" in present_types}
            present=[value for kind,value in values.items() if available[kind]]
            status="MISSING_EVIDENCE" if len(present)<2 else "MATCHED" if max(present)-min(present)<=100 else "CONFLICT"
            difference=max(present)-min(present) if present else 0
            row=await conn.fetchrow("INSERT INTO itr_reconciliation_items(workspace_id,firm_id,category,source_values,difference_paise,status) VALUES($1,$2,$3,$4::jsonb,$5,$6) RETURNING *",workspace["id"],firm.firm_id,category,json.dumps(values),difference,status)
            results.append(dict(row))
        next_status="NEEDS_REVIEW" if results and all(x["status"]=="MATCHED" for x in results) else "DATA_REQUIRED"
        await conn.execute("UPDATE itr_workspaces SET status=$1,updated_at=NOW() WHERE id=$2",next_status,workspace["id"])
    return results


@router.put("/workspaces/{workspace_id}/schedules")
async def schedules(workspace_id:str,lines:list[ScheduleLine],firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    firm.require("books.propose")
    async with db_pool.acquire() as conn,conn.transaction():
        workspace=await conn.fetchrow("SELECT * FROM itr_workspaces WHERE id=$1::uuid AND firm_id=$2",workspace_id,firm.firm_id)
        if not workspace: raise HTTPException(404,"Workspace not found")
        await _require_authorization(conn,workspace_id,"PREPARE",firm.user_id)
        await conn.execute("DELETE FROM itr_schedule_lines WHERE workspace_id=$1",workspace["id"])
        for line in lines:
            if not line.source_links: raise HTTPException(422,"Every schedule line needs source links")
            await conn.execute("INSERT INTO itr_schedule_lines(workspace_id,firm_id,schedule_key,line_key,amount_paise,source_links,rule_id,rounding_rule,reviewer_adjustment_paise,explanation) VALUES($1,$2,$3,$4,$5,$6::jsonb,$7::uuid,$8,$9,$10)",workspace["id"],firm.firm_id,line.schedule_key,line.line_key,line.amount_paise,json.dumps(line.source_links),line.rule_id,line.rounding_rule,line.reviewer_adjustment_paise,line.explanation)
        computation={"schedule_total_paise":sum(x.amount_paise+x.reviewer_adjustment_paise for x in lines),"line_count":len(lines)}
        row=await conn.fetchrow("UPDATE itr_workspaces SET computation=$1::jsonb,status='NEEDS_REVIEW',updated_at=NOW() WHERE id=$2 RETURNING *",json.dumps(computation),workspace["id"])
    return dict(row)


@router.post("/workspaces/{workspace_id}/approve")
async def approve(workspace_id:str,firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    firm.require("compliance.review")
    async with db_pool.acquire() as conn:
        await _require_authorization(conn,workspace_id,"APPROVE",firm.user_id)
        reconciliation=await conn.fetchrow("SELECT count(*) AS total,count(*) FILTER (WHERE status='MATCHED') AS matched FROM itr_reconciliation_items WHERE workspace_id=$1::uuid",workspace_id)
        if reconciliation["total"]<3 or reconciliation["matched"]!=reconciliation["total"]:
            raise HTTPException(409,"Resolve all required reconciliation checks first")
        lines=await conn.fetchval("SELECT count(*) FROM itr_schedule_lines WHERE workspace_id=$1::uuid",workspace_id)
        if not lines: raise HTTPException(409,"Draft source-linked schedules before approval")
        row=await conn.fetchrow("UPDATE itr_workspaces SET status='APPROVED',approved_by=$1,approved_at=NOW(),approved_source_hash=source_hash,stale=false,updated_at=NOW() WHERE id=$2::uuid AND firm_id=$3 AND status='NEEDS_REVIEW' AND source_hash IS NOT NULL RETURNING *",firm.user_id,workspace_id,firm.firm_id)
    if not row: raise HTTPException(409,"Workspace is not ready for approval")
    return dict(row)


@router.post("/workspaces/{workspace_id}/pack")
async def pack(workspace_id:str,firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    async with db_pool.acquire() as conn:
        workspace=await conn.fetchrow("SELECT * FROM itr_workspaces WHERE id=$1::uuid AND firm_id=$2",workspace_id,firm.firm_id)
        if not workspace or workspace["status"]!="APPROVED" or workspace["stale"]: raise HTTPException(409,"Approve a current workspace first")
        sources=[dict(x) for x in await conn.fetch("SELECT source_type,source_period,source_version,document_id FROM itr_sources WHERE workspace_id=$1",workspace["id"])]
        lines=[dict(x) for x in await conn.fetch("SELECT schedule_key,line_key,amount_paise,source_links,rule_id,rounding_rule,reviewer_adjustment_paise,explanation FROM itr_schedule_lines WHERE workspace_id=$1 ORDER BY schedule_key,line_key",workspace["id"])]
        required={"AIS","26AS","BOOKS"};missing=sorted(required-{x["source_type"] for x in sources})
        filing_pack={"label":"READY_FOR_MANUAL_FILING","submission_mode":"MANUAL_PORTAL_ENTRY",
                     "computation":workspace["computation"],"schedule_values":lines,"missing_information":missing,
                     "evidence_index":sources,"portal_checklist":["Select assessment year","Enter schedule values","Validate tax and payment","Submit and e-verify outside firmOS"]}
        row=await conn.fetchrow("UPDATE itr_workspaces SET status='READY_FOR_MANUAL_FILING',filing_pack=$1::jsonb,updated_at=NOW() WHERE id=$2 RETURNING *",json.dumps(filing_pack,default=str),workspace["id"])
    return dict(row)


@router.post("/workspaces/{workspace_id}/events")
async def event(workspace_id:str,body:FilingEventRequest,firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    states={"FILED_EXTERNALLY":"FILED_EXTERNALLY","PAYMENT_RECORDED":"FILED_EXTERNALLY","E_VERIFIED":"FILED_EXTERNALLY","REJECTED":"REJECTED","ACKNOWLEDGEMENT_UPLOADED":"COMPLETED"}
    async with db_pool.acquire() as conn,conn.transaction():
        workspace=await conn.fetchrow("SELECT * FROM itr_workspaces WHERE id=$1::uuid AND firm_id=$2 FOR UPDATE",workspace_id,firm.firm_id)
        if not workspace: raise HTTPException(404,"Workspace not found")
        if body.event_type=="FILED_EXTERNALLY" and workspace["status"]!="READY_FOR_MANUAL_FILING": raise HTTPException(409,"Manual filing pack is not ready")
        if body.event_type=="ACKNOWLEDGEMENT_UPLOADED" and (workspace["status"] not in {"FILED_EXTERNALLY","E_VERIFICATION_PENDING"} or not body.evidence_reference): raise HTTPException(409,"Acknowledgement evidence is required after external filing")
        await conn.execute("INSERT INTO itr_filing_events(workspace_id,firm_id,event_type,reference,evidence_reference,occurred_at,recorded_by) VALUES($1,$2,$3,$4,$5,$6::timestamptz,$7)",workspace["id"],firm.firm_id,body.event_type,body.reference,body.evidence_reference,body.occurred_at,firm.user_id)
        row=await conn.fetchrow("UPDATE itr_workspaces SET status=$1,updated_at=NOW() WHERE id=$2 RETURNING *",states[body.event_type],workspace["id"])
    return dict(row)
