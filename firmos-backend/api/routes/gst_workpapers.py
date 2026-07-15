"""Source-linked GST workpapers and manual filing lifecycle."""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import FirmContext, get_current_firm, get_db
from core.gst_workpapers import build_source_rows, summarize_tables

router = APIRouter(prefix="/api/gst", tags=["gst-workpapers"])


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


class Adjustment(BaseModel):
    adjustment_id:str=Field(min_length=3,max_length=100)
    table_key:str=Field(min_length=2,max_length=100)
    component:str=Field(pattern=r"^(taxable_paise|igst_paise|cgst_paise|sgst_paise|cess_paise)$")
    amount_paise:int
    reason:str=Field(min_length=3,max_length=1000)


class PrepareRequest(BaseModel):
    client_id: str
    period: str = Field(pattern=r"^(0[1-9]|1[0-2])[0-9]{4}$")
    return_type: str = Field(pattern=r"^(GSTR1|GSTR3B)$")
    adjustments:list[Adjustment]=Field(default_factory=list)


class AcknowledgementRequest(BaseModel):
    acknowledgement_number: str = Field(min_length=3, max_length=200)
    filed_at: str
    evidence_reference: str = Field(min_length=3, max_length=1000)


async def _source_rows(conn, firm_id: str, client_id: str, period: str, return_type: str) -> tuple[list[dict],list[dict]]:
    sales = [dict(row) for row in await conn.fetch(
        """SELECT id,source_version,taxable_paise,cgst_paise,sgst_paise,igst_paise,cess_paise,total_paise
                  ,customer_gstin,place_of_supply
           FROM sales_register WHERE firm_id=$1 AND client_id=$2 AND period=$3 AND active
           AND (provider_object_id IS NOT NULL OR verification_id IS NOT NULL) ORDER BY id""",
        firm_id, client_id, period,
    )]
    purchases = []
    if return_type == "GSTR3B":
        purchases = [dict(row) for row in await conn.fetch(
            """SELECT p.id,p.source_version,p.taxable_paise,p.cgst_paise,p.sgst_paise,p.igst_paise,
               0::bigint cess_paise,p.reverse_charge,p.itc_classification,m.match_decision,m.ims_decision,
               d.document_type
               FROM purchase_register p LEFT JOIN LATERAL (
                 SELECT match_decision,ims_decision,gstr2b_document_id FROM gstr2b_match_results
                 WHERE purchase_id=p.id ORDER BY created_at DESC LIMIT 1
               ) m ON true LEFT JOIN gstr2b_documents d ON d.id=m.gstr2b_document_id
               WHERE p.firm_id=$1 AND p.client_id=$2 AND p.period=$3 AND p.active
               AND (p.provider_object_id IS NOT NULL OR p.verification_id IS NOT NULL) ORDER BY p.id""",
            firm_id, client_id, period,
        )]
    return build_source_rows(sales,purchases,return_type)


def _tables(rows: list[dict], adjustments: list[dict]) -> dict:
    return summarize_tables(rows,adjustments)


@router.post("/workpapers", status_code=201)
async def prepare(body: PrepareRequest, firm: FirmContext=Depends(get_current_firm), db_pool=Depends(get_db)):
    firm.require("books.propose")
    async with db_pool.acquire() as conn, conn.transaction():
        adjustments=[item.model_dump() for item in body.adjustments]
        rows, source_exceptions = await _source_rows(conn, firm.firm_id, body.client_id, body.period, body.return_type)
        period_end = f"{body.period[2:]}-{body.period[:2]}-01"
        rule_rows = await conn.fetch(
            """SELECT rule_key,version FROM gst_rule_versions WHERE jurisdiction='IN'
               AND effective_from<=($1::date + INTERVAL '1 month - 1 day')
               AND (effective_to IS NULL OR effective_to>=$1::date)""",period_end,
        )
        versions = [{"kind": row["source_kind"], "id": row["source_id"], "version": row["source_version"]} for row in rows]
        source_hash = _hash({"sources": versions, "adjustments": adjustments})
        await conn.execute(
            """UPDATE gst_workpapers SET stale=true,updated_at=NOW() WHERE firm_id=$1 AND client_id=$2
               AND period=$3 AND return_type=$4 AND approved_source_hash IS NOT NULL AND source_hash<>$5""",
            firm.firm_id, body.client_id, body.period, body.return_type, source_hash,
        )
        version = await conn.fetchval(
            "SELECT COALESCE(MAX(version),0)+1 FROM gst_workpapers WHERE firm_id=$1 AND client_id=$2 AND period=$3 AND return_type=$4",
            firm.firm_id, body.client_id, body.period, body.return_type,
        )
        exceptions = list(source_exceptions)
        if not rows: exceptions.append({"code": "VERIFIED_REGISTER_EMPTY", "message": "Verified source rows are required."})
        if not rule_rows: exceptions.append({"code": "EFFECTIVE_RULE_REQUIRED", "message": "A reviewed GST rule version is required for this return period."})
        paper = await conn.fetchrow(
            """INSERT INTO gst_workpapers(firm_id,client_id,return_type,period,version,status,source_versions,
               rule_versions,adjustments,tables,exceptions,source_hash,prepared_by)
               VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,$10::jsonb,$11::jsonb,$12,$13) RETURNING *""",
            firm.firm_id,body.client_id,body.return_type,body.period,version,
            "NEEDS_REVIEW" if rows and rule_rows and not source_exceptions else "DATA_REQUIRED",json.dumps(versions),json.dumps([dict(x) for x in rule_rows]),
            json.dumps(adjustments),json.dumps(_tables(rows,adjustments)),json.dumps(exceptions),source_hash,firm.user_id,
        )
        for row in rows:
            await conn.execute(
                """INSERT INTO gst_workpaper_sources(workpaper_id,firm_id,table_key,source_kind,source_id,
                   source_version,amount_paise,treatment,details) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)""",
                paper["id"],firm.firm_id,row["table_key"],row["source_kind"],row["source_id"],
                row["source_version"],row["amount_paise"],row["treatment"],json.dumps(row["details"],default=str),
            )
        for item in adjustments:
            await conn.execute(
                """INSERT INTO gst_workpaper_sources(workpaper_id,firm_id,table_key,source_kind,source_id,
                   source_version,amount_paise,treatment,details) VALUES($1,$2,$3,'REVIEWER_ADJUSTMENT',$4,$5,$6,
                   'REVIEWER_ADJUSTED',$7::jsonb)""",paper["id"],firm.firm_id,item["table_key"],item["adjustment_id"],
                str(version),item["amount_paise"],json.dumps(item),
            )
    return dict(paper)


@router.get("/workpapers/latest")
async def latest(client_id: str, period: str, return_type: str, firm: FirmContext=Depends(get_current_firm), db_pool=Depends(get_db)):
    async with db_pool.acquire() as conn:
        paper = await conn.fetchrow(
            """SELECT * FROM gst_workpapers WHERE firm_id=$1 AND client_id=$2 AND period=$3 AND return_type=$4
               ORDER BY version DESC LIMIT 1""", firm.firm_id,client_id,period,return_type,
        )
        if not paper:
            raise HTTPException(404,"Workpaper not prepared")
        sources = await conn.fetch("SELECT * FROM gst_workpaper_sources WHERE workpaper_id=$1 ORDER BY table_key,source_id",paper["id"])
    return {"workpaper":dict(paper),"sources":[dict(row) for row in sources]}


@router.post("/workpapers/{workpaper_id}/approve")
async def approve(workpaper_id: str, firm: FirmContext=Depends(get_current_firm), db_pool=Depends(get_db)):
    firm.require("compliance.review")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE gst_workpapers SET status='APPROVED',reviewed_by=$1,approved_at=NOW(),
               approved_source_hash=source_hash,updated_at=NOW() WHERE id=$2::uuid AND firm_id=$3
               AND status='NEEDS_REVIEW' AND NOT stale RETURNING *""",firm.user_id,workpaper_id,firm.firm_id,
        )
    if not row: raise HTTPException(409,"Only a current reviewed workpaper can be approved")
    return dict(row)


@router.post("/workpapers/{workpaper_id}/pack")
async def make_pack(workpaper_id: str, firm: FirmContext=Depends(get_current_firm), db_pool=Depends(get_db)):
    async with db_pool.acquire() as conn:
        paper = await conn.fetchrow("SELECT * FROM gst_workpapers WHERE id=$1::uuid AND firm_id=$2",workpaper_id,firm.firm_id)
        if not paper or paper["status"]!="APPROVED" or paper["stale"]: raise HTTPException(409,"Approve a current workpaper first")
        schedules=[dict(row) for row in await conn.fetch("SELECT table_key,source_kind,source_id,source_version,amount_paise,treatment,details FROM gst_workpaper_sources WHERE workpaper_id=$1 ORDER BY table_key,source_kind,source_id",paper["id"])]
        pack={"label":"READY_FOR_MANUAL_FILING","submission_mode":"MANUAL_PORTAL_ENTRY",
              "table_summary":paper["tables"],"detailed_schedules":schedules,
              "exceptions":paper["exceptions"],"source_versions":paper["source_versions"],
              "review_json":{"return_type":paper["return_type"],"period":paper["period"],"tables":paper["tables"]},
              "portal_checklist":["Open the correct GSTIN and period","Enter table totals","Cross-check liability and ITC","Submit outside firmOS"]}
        row=await conn.fetchrow("UPDATE gst_workpapers SET status='READY_FOR_MANUAL_FILING',filing_pack=$1::jsonb,updated_at=NOW() WHERE id=$2 RETURNING *",json.dumps(pack,default=str),paper["id"])
    return dict(row)


@router.post("/workpapers/{workpaper_id}/filed-externally")
async def filed(workpaper_id: str, firm: FirmContext=Depends(get_current_firm), db_pool=Depends(get_db)):
    async with db_pool.acquire() as conn:
        row=await conn.fetchrow("UPDATE gst_workpapers SET status='FILED_EXTERNALLY',updated_at=NOW() WHERE id=$1::uuid AND firm_id=$2 AND status='READY_FOR_MANUAL_FILING' RETURNING *",workpaper_id,firm.firm_id)
    if not row: raise HTTPException(409,"Manual filing pack is not ready")
    return dict(row)


@router.post("/workpapers/{workpaper_id}/acknowledgement")
async def acknowledge(workpaper_id: str, body: AcknowledgementRequest, firm: FirmContext=Depends(get_current_firm), db_pool=Depends(get_db)):
    async with db_pool.acquire() as conn,conn.transaction():
        paper=await conn.fetchrow("SELECT id FROM gst_workpapers WHERE id=$1::uuid AND firm_id=$2 AND status='FILED_EXTERNALLY' FOR UPDATE",workpaper_id,firm.firm_id)
        if not paper: raise HTTPException(409,"Record external filing before acknowledgement")
        await conn.execute("INSERT INTO gst_filing_acknowledgements(workpaper_id,firm_id,acknowledgement_number,filed_at,evidence_reference,uploaded_by) VALUES($1,$2,$3,$4::timestamptz,$5,$6)",paper["id"],firm.firm_id,body.acknowledgement_number,body.filed_at,body.evidence_reference,firm.user_id)
        await conn.execute("UPDATE gst_workpapers SET status='ACKNOWLEDGEMENT_UPLOADED',updated_at=NOW() WHERE id=$1",paper["id"])
        row=await conn.fetchrow("UPDATE gst_workpapers SET status='COMPLETED',updated_at=NOW() WHERE id=$1 RETURNING *",paper["id"])
    return dict(row)
