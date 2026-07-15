"""Import runs, IMS decisions, clean acceptance, and versioned workpapers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from api.deps import FirmContext, get_current_firm, get_db
from api.routes.reconciliation import _build_purchase_source, _period_bounds
from engines.gstr2b_matcher import ALGORITHM_VERSION, match_gstr2b
from engines.gstr2b_parser import parse_gstr2b_excel, parse_gstr2b_json

router = APIRouter(prefix="/api/gstr2b", tags=["gstr2b-reconciliation"])


def _format(filename: str) -> str:
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in {"json", "xls", "xlsx"}:
        raise HTTPException(status_code=415, detail={"code": "UNSUPPORTED_FORMAT", "message": "Use official JSON or a supported Excel export."})
    return extension.upper()


async def _store_documents(conn, run_id, firm_id, client_id, documents) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}
    for document in documents:
        document_id = uuid.uuid4()
        ids[document.identity_key] = document_id
        await conn.execute(
            """INSERT INTO gstr2b_documents
               (id,run_id,firm_id,client_id,identity_key,supplier_gstin,invoice_number,invoice_date,document_type,
                amendment_of_key,taxable_paise,igst_paise,cgst_paise,sgst_paise,cess_paise,total_paise,original)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17::jsonb)""",
            document_id, run_id, firm_id, client_id, document.identity_key, document.supplier_gstin,
            document.invoice_number, document.invoice_date, document.document_type, document.amendment_of_key,
            document.taxable_paise, document.igst_paise, document.cgst_paise, document.sgst_paise,
            document.cess_paise, document.total_paise, json.dumps(document.original, default=str),
        )
    return ids


@router.post("/runs")
async def create_run(
    file: UploadFile = File(...), client_id: str = Form(...), period: str = Form(...),
    firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db),
):
    firm.require("books.read")
    _period_bounds(period)
    source_format = _format(file.filename or "")
    content = await file.read()
    upload_hash = hashlib.sha256(content).hexdigest()
    try:
        parsed = parse_gstr2b_json(json.loads(content)) if source_format == "JSON" else parse_gstr2b_excel(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail={"code": "CORRUPT_GSTR2B_FILE", "message": "The JSON file is corrupt."}) from exc
    async with db_pool.acquire() as conn:
        client = await conn.fetchrow("SELECT gstin FROM clients WHERE id=$1 AND firm_id=$2", client_id, firm.firm_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        selected_gstin = str(client["gstin"] or "").upper()
        file_gstin = parsed.gstin or selected_gstin
        identity_errors = []
        if file_gstin != selected_gstin:
            identity_errors.append({"code": "GSTIN_MISMATCH", "selected": selected_gstin, "file": file_gstin})
        if parsed.return_period and parsed.return_period != period:
            identity_errors.append({"code": "PERIOD_MISMATCH", "selected": period, "file": parsed.return_period})
        run_id = uuid.uuid4()
        status = "IDENTITY_MISMATCH" if identity_errors else "READY"
        existing = await conn.fetchrow(
            "SELECT id,status FROM gstr2b_import_runs WHERE firm_id=$1 AND client_id=$2 AND upload_hash=$3",
            firm.firm_id, client_id, upload_hash,
        )
        if existing:
            return {"runId": str(existing["id"]), "status": existing["status"], "duplicateUpload": True}
        await conn.execute(
            """INSERT INTO gstr2b_import_runs
               (id,firm_id,client_id,upload_hash,gstin,return_period,source_format,parser_version,source_counts,
                source_totals,status,errors,uploaded_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11,$12::jsonb,$13::uuid)""",
            run_id, firm.firm_id, client_id, upload_hash, file_gstin, period, source_format, parsed.parser_version,
            json.dumps(parsed.source_counts), json.dumps(parsed.source_totals), status, json.dumps(identity_errors), firm.user_id,
        )
        if identity_errors:
            return {"runId": str(run_id), "status": status, "identityErrors": identity_errors}
        document_ids = await _store_documents(conn, run_id, firm.firm_id, client_id, parsed.documents)
        purchases = await _build_purchase_source(conn, firm.firm_id, client_id, period)
        claimed = {row["identity_key"] for row in await conn.fetch(
            "SELECT identity_key FROM gstr2b_itc_claim_history WHERE firm_id=$1 AND client_id=$2 AND status='ACCEPTED'",
            firm.firm_id, client_id,
        )}
        matches = match_gstr2b(purchases, parsed.documents, claimed)
        for match in matches:
            await conn.execute(
                """INSERT INTO gstr2b_match_results
                   (run_id,firm_id,client_id,purchase_id,gstr2b_document_id,bucket,algorithm_version,score,reasons,differences,warnings)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11::jsonb)""",
                run_id, firm.firm_id, client_id, match.purchase_id,
                document_ids.get(match.document.identity_key) if match.document else None,
                match.bucket, ALGORITHM_VERSION, match.score, json.dumps(match.reasons),
                json.dumps(match.differences), json.dumps(match.warnings),
            )
        await conn.execute("UPDATE gstr2b_import_runs SET status='RECONCILED' WHERE id=$1", run_id)
    return {"runId": str(run_id), "status": "RECONCILED", "counts": parsed.source_counts, "totals": parsed.source_totals}


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    async with db_pool.acquire() as conn:
        run = await conn.fetchrow("SELECT * FROM gstr2b_import_runs WHERE id=$1 AND firm_id=$2", run_id, firm.firm_id)
        if not run:
            raise HTTPException(status_code=404, detail="Import run not found")
        rows = await conn.fetch(
            """SELECT m.*,d.supplier_gstin,d.invoice_number,d.invoice_date,d.total_paise,d.document_type,
                      p.vendor_name,p.vendor_gstin,p.bill_number,p.bill_date,p.total_paise AS book_total_paise
               FROM gstr2b_match_results m LEFT JOIN gstr2b_documents d ON d.id=m.gstr2b_document_id
               LEFT JOIN purchase_register p ON p.id=m.purchase_id WHERE m.run_id=$1 ORDER BY m.bucket,m.created_at""", run_id,
        )
    items = [dict(row) | {"supplier_follow_up": f"Please review invoice {row['invoice_number'] or row['bill_number'] or ''} for the selected GSTR-2B period."} for row in rows]
    return {"run": dict(run), "items": items}


class ImsDecision(BaseModel):
    match_decision: str
    ims_decision: str = "NO_ACTION"


@router.patch("/matches/{match_id}")
async def decide(match_id: uuid.UUID, body: ImsDecision, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    firm.require("compliance.review")
    if body.match_decision not in {"PENDING", "ACCEPTED", "REJECTED"} or body.ims_decision not in {"ACCEPT", "REJECT", "PENDING", "NO_ACTION"}:
        raise HTTPException(status_code=422, detail="Invalid reconciliation or IMS decision")
    async with db_pool.acquire() as conn,conn.transaction():
        scope=await conn.fetchrow("SELECT client_id,(SELECT return_period FROM gstr2b_import_runs WHERE id=run_id) period FROM gstr2b_match_results WHERE id=$1 AND firm_id=$2",match_id,firm.firm_id)
        result = await conn.execute(
            """UPDATE gstr2b_match_results SET match_decision=$1,ims_decision=$2,decided_by=$3::uuid,decided_at=NOW()
               WHERE id=$4 AND firm_id=$5""", body.match_decision, body.ims_decision, firm.user_id, match_id, firm.firm_id,
        )
        if scope and result.endswith("1"):
            await conn.execute("UPDATE gst_workpapers SET stale=true,status='NEEDS_REVIEW',updated_at=NOW() WHERE firm_id=$1 AND client_id=$2 AND period=$3 AND return_type='GSTR3B' AND status IN ('APPROVED','READY_FOR_MANUAL_FILING')",firm.firm_id,scope["client_id"],scope["period"])
    return {"ok": result.endswith("1"), "portalActionPerformed": False}


@router.post("/runs/{run_id}/bulk-accept")
async def bulk_accept(run_id: uuid.UUID, confirm: bool = False, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    firm.require("compliance.review")
    async with db_pool.acquire() as conn,conn.transaction():
        clean = await conn.fetch(
            """SELECT m.id,d.identity_key,d.amendment_of_key,d.total_paise,r.return_period,m.client_id
               FROM gstr2b_match_results m JOIN gstr2b_documents d ON d.id=m.gstr2b_document_id
               JOIN gstr2b_import_runs r ON r.id=m.run_id
               WHERE m.run_id=$1 AND m.firm_id=$2 AND m.bucket='EXACT' AND m.warnings='[]'::jsonb AND m.match_decision='PENDING'""",
            run_id, firm.firm_id,
        )
        preview = {"count": len(clean), "total_paise": sum(row["total_paise"] for row in clean)}
        if not confirm:
            return preview | {"confirmationRequired": True}
        for row in clean:
            await conn.execute("UPDATE gstr2b_match_results SET match_decision='ACCEPTED',decided_by=$1::uuid,decided_at=NOW() WHERE id=$2", firm.user_id, row["id"])
            await conn.execute(
                """INSERT INTO gstr2b_itc_claim_history (firm_id,client_id,identity_key,amendment_root_key,claim_period,match_result_id,status)
                   VALUES ($1,$2,$3,$4,$5,$6,'ACCEPTED') ON CONFLICT DO NOTHING""",
                firm.firm_id, row["client_id"], row["identity_key"], row["amendment_of_key"], row["return_period"], row["id"],
            )
        if clean:
            await conn.execute("UPDATE gst_workpapers SET stale=true,status='NEEDS_REVIEW',updated_at=NOW() WHERE firm_id=$1 AND client_id=$2 AND period=$3 AND return_type='GSTR3B' AND status IN ('APPROVED','READY_FOR_MANUAL_FILING')",firm.firm_id,clean[0]["client_id"],clean[0]["return_period"])
    return preview | {"accepted": True}


@router.post("/runs/{run_id}/workpapers")
async def create_workpaper(run_id: uuid.UUID, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    firm.require("compliance.review")
    async with db_pool.acquire() as conn:
        run = await conn.fetchrow("SELECT * FROM gstr2b_import_runs WHERE id=$1 AND firm_id=$2", run_id, firm.firm_id)
        if not run:
            raise HTTPException(status_code=404, detail="Import run not found")
        rows = await conn.fetch("SELECT bucket,match_decision,ims_decision,warnings FROM gstr2b_match_results WHERE run_id=$1", run_id)
        version = await conn.fetchval("SELECT COALESCE(MAX(version),0)+1 FROM gstr2b_workpapers WHERE run_id=$1", run_id)
        unresolved = [dict(row) for row in rows if row["match_decision"] == "PENDING" or row["warnings"]]
        summary = {"items": len(rows), "accepted": sum(row["match_decision"] == "ACCEPTED" for row in rows), "unresolved": len(unresolved)}
        workpaper_id = await conn.fetchval(
            """INSERT INTO gstr2b_workpapers (run_id,firm_id,client_id,version,source_hashes,summary,unresolved_items,reviewer_id)
               VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb,$8::uuid) RETURNING id""",
            run_id, firm.firm_id, run["client_id"], version, json.dumps([run["upload_hash"]]),
            json.dumps(summary), json.dumps(unresolved, default=str), firm.user_id,
        )
    return {"workpaperId": str(workpaper_id), "version": version, "summary": summary}
