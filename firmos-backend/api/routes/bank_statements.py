"""Bank statement ingestion — PDF/CSV/Excel parse + running-balance validator.

Parse ladder (ponytail: try cheap → escalate):
  1. CSV/Excel → pandas (free, in-memory)
  2. PDF (digital text) → pdfplumber (free, no ML)
  3. PDF (scanned) → Sarvam Vision in 10-page chunks (₹0.50/pg)
"""

import hashlib
import json
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from api.deps import get_current_firm, FirmContext, get_db
from core.private_storage import StorageUnavailable, create_signed_url, local_evidence_path, store_private_evidence
from api.routes.bank_statement_parsing import parse_csv_or_excel, validate_running_balance
from engines.bank_registry import parse_bank_statement

# Kept for the existing live-verification script while parser code lives separately.
_parse_csv_or_excel = parse_csv_or_excel

router = APIRouter(prefix="/api/bank-statements", tags=["bank-statements"])
logger = logging.getLogger(__name__)


@router.post("/upload")
async def upload_bank_statement(
    file: UploadFile = File(...),
    client_id: str = Form(...),
    bank_hint: str | None = Form(default=None),
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db),
):
    """POST /api/bank-statements/upload

    Accepts CSV, Excel (.xlsx), or PDF bank statements.
    Parse ladder: CSV/Excel → pandas, PDF → pdfplumber, scanned → Sarvam Vision.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    content = await file.read()
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    upload_hash = hashlib.sha256(content).hexdigest()
    parsed = parse_bank_statement(content, file.filename, bank_hint)
    statement_id = f"bs-{uuid.uuid4().hex[:8]}"

    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not available")

    async with db_pool.acquire() as conn:
        duplicate = await conn.fetchrow(
            "SELECT id,status FROM bank_statements WHERE firm_id=$1 AND client_id=$2 AND upload_hash=$3",
            firm.firm_id, client_id, upload_hash,
        )
        if duplicate:
            return {"ok": True, "statementId": duplicate["id"], "status": duplicate["status"], "duplicateUpload": True}

    try:
        file_url = await store_private_evidence(
            "bank-statements", f"{firm.firm_id}/{statement_id}.{ext}", content,
            file.content_type or "application/octet-stream",
        )
    except StorageUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "PRIVATE_STORAGE_UNAVAILABLE", "retryable": True, "message": str(exc)},
        ) from exc

    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO bank_statements
               (id,firm_id,client_id,file_url,status,upload_hash,source_format,parser_adapter,parser_version,bank_name,
                account_number_masked,period_start,period_end,opening_balance_paise,closing_balance_paise,integrity_status,integrity_details)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17::jsonb)""",
            statement_id, firm.firm_id, client_id, file_url, "PARSED", upload_hash, ext.upper(), parsed.adapter,
            parsed.parser_version, parsed.bank_name, parsed.account_number_masked, parsed.period_start, parsed.period_end,
            parsed.opening_balance_paise, parsed.closing_balance_paise,
            "VALID" if parsed.integrity.get("valid") else "BALANCE_BREAK", json.dumps(parsed.integrity),
        )

        if parsed.transactions:
            await conn.executemany(
                """INSERT INTO bank_transactions (
                    id,statement_id,firm_id,client_id,txn_date,value_date,description,reference,amount,txn_type,
                    running_balance,debit_paise,credit_paise,source_row,source_page,normalized_tokens,canonical_hash
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)""",
                [
                    (
                        f"txn-{uuid.uuid4().hex[:8]}",
                        statement_id, firm.firm_id, client_id, t.txn_date, t.value_date, t.description, t.reference,
                        t.amount_paise, t.txn_type, t.balance_paise or 0, t.debit_paise, t.credit_paise,
                        t.source_row, t.source_page, list(t.normalized_tokens), hashlib.sha256(
                            f"{t.txn_date}|{t.reference}|{t.debit_paise}|{t.credit_paise}".encode()
                        ).hexdigest(),
                    )
                    for t in parsed.transactions
                ],
            )

    return {
        "ok": True,
        "statementId": statement_id,
        "transactionsCount": len(parsed.transactions),
        "balanceValidation": parsed.integrity,
        "period": {"start": parsed.period_start, "end": parsed.period_end},
    }


@router.get("")
async def list_bank_statements(
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db),
):
    """GET /api/bank-statements → list all statements for the firm."""
    if not db_pool:
        return []

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM bank_statements WHERE firm_id = $1 ORDER BY uploaded_at DESC",
            firm.firm_id,
        )
        return [
            {
                key: value for key, value in dict(row).items() if key != "file_url"
            } | {"download_url": f"/api/bank-statements/{row['id']}/download"}
            for row in rows
        ]


@router.get("/{statement_id}/download")
async def get_bank_statement_download(
    statement_id: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    """Issue a short-lived evidence link only after firm-scoped authorization."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Bank statement store unavailable")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT file_url FROM bank_statements WHERE id=$1 AND firm_id=$2", statement_id, firm.firm_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Bank statement not found")
    file_url = str(row["file_url"] or "")
    if file_url.startswith("storage://bank-statements/"):
        try:
            return {"url": await create_signed_url(file_url), "expires_in_seconds": 300}
        except StorageUnavailable as exc:
            raise HTTPException(status_code=503, detail="Bank statement evidence is unavailable") from exc
    if file_url.startswith("local://bank-statements/"):
        try:
            return FileResponse(local_evidence_path(file_url))
        except StorageUnavailable as exc:
            raise HTTPException(status_code=404, detail="Bank statement evidence is unavailable") from exc
    raise HTTPException(status_code=409, detail="Legacy statement storage location cannot be served securely")
