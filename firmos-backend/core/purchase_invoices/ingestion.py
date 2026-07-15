"""One-file purchase ingestion orchestration."""
from __future__ import annotations

import hashlib
import io
import json
import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from connectors.document_upload.extractor import raw_to_extracted_fields, raw_to_line_items
from core.money import paise_to_decimal
from core.private_storage import StorageUnavailable, store_private_evidence
from core.purchase_invoices.file_contract import UploadRejected, inspect_upload
from core.purchase_invoices.validation import validate_invoice, validation_state
from extraction.result import ExtractionResult
from models.schemas import Bbox, ExtractedDocument


async def _run(conn, firm_id: str, client_id: str, upload, digest: str) -> str:
    row = await conn.fetchrow(
        """INSERT INTO document_ingestion_runs(firm_id,client_id,state,original_filename,mime_type,size_bytes,content_sha256)
           VALUES($1,$2,'RECEIVED',$3,$4,$5,$6) RETURNING id""",
        firm_id, client_id, upload.filename, upload.mime_type, upload.size_bytes, digest,
    )
    return str(row["id"])


async def _state(conn, run_id: str, state: str, **values) -> None:
    await conn.execute(
        """UPDATE document_ingestion_runs SET state=$1,error_code=$2,user_action=$3,
           object_key=COALESCE($4,object_key),document_id=COALESCE($5,document_id),updated_at=NOW()
           WHERE id=$6::uuid""",
        state, values.get("error_code"), values.get("user_action"), values.get("object_key"),
        values.get("document_id"), run_id,
    )


async def _expense_head(raw: dict, firm_id: str, db_pool) -> tuple[str, str]:
    from api.routes.classify import ExpenseHeadRequest, classify_expense_head
    try:
        firm = type("Firm", (), {"firm_id": firm_id})()
        result = await classify_expense_head(
            ExpenseHeadRequest(
                description=" ".join(item.get("desc", "") for item in raw.get("line_items", [])),
                vendor_name=raw.get("vendor_name", ""), amount_paise=raw.get("total_paise", 0),
            ), firm, db_pool,
        )
        return result["suggested_head"], result["confidence"]
    except Exception:
        logging.warning("document_expense_classification_failed")
        return "General Expenses", "LOW"


def _document(doc_id: str, client_id: str, client_name: str, file_url: str, upload,
              raw: dict, expense_head: str, expense_confidence: str) -> ExtractedDocument:
    is_sales = str(raw.get("doc_kind") or "").upper() in {"SALES_INVOICE", "CUSTOMER_INVOICE"}
    compat = {
        "vendor_name": raw.get("vendor_name", ""), "vendor_gstin": raw.get("vendor_gstin", ""),
        "invoice_number": raw.get("invoice_number", ""), "invoice_date": raw.get("invoice_date", ""),
        "taxable_amount": str(paise_to_decimal(int(raw.get("taxable_amount_paise", 0)))),
        "cgst": str(paise_to_decimal(int(raw.get("cgst_paise", 0)))),
        "sgst": str(paise_to_decimal(int(raw.get("sgst_paise", 0)))),
        "igst": str(paise_to_decimal(int(raw.get("igst_paise", 0)))),
        "total": str(paise_to_decimal(int(raw.get("total_paise", 0)))),
        "expense_head": expense_head, "revenue_item": raw.get("revenue_item", "Sales"),
        "confidence": raw.get("confidence", 0.5),
        "expense_head_confidence": expense_confidence,
    }
    fields = raw_to_extracted_fields(compat, confidence=compat["confidence"], is_sales=is_sales)
    evidence_keys = {"vendorName": "vendor_name", "gstin": "vendor_gstin", "invoiceNumber": "invoice_number",
                     "invoiceDate": "invoice_date", "taxableAmount": "taxable_amount_paise",
                     "cgst": "cgst_paise", "sgst": "sgst_paise", "igst": "igst_paise", "total": "total_paise"}
    evidence = raw.get("evidence") or {}
    enriched = []
    for field in fields:
        item = evidence.get(evidence_keys.get(field.key, ""), {})
        region = item.get("region") if isinstance(item, dict) else None
        bbox = Bbox(page=int(item.get("page", 1)), **region) if isinstance(region, dict) and {"x", "y", "w", "h"}.issubset(region) else None
        enriched.append(field.model_copy(update={"bbox": bbox}) if bbox else field)
    lines = raw_to_line_items(raw.get("line_items", []))
    return ExtractedDocument(
        id=doc_id, clientId=client_id, clientName=client_name, fileUrl=f"/api/documents/{doc_id}/download",
        fileType=upload.file_type, docKind=raw.get("doc_kind", "VENDOR_BILL"),
        status="PENDING_REVIEW", vendorName=raw.get("vendor_name") or ("Unknown Customer" if is_sales else "Unknown Vendor"),
        fields=enriched, lineItems=lines, total=int(raw.get("total_paise", 0)),
        uploadedAt=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


async def ingest_purchase(file, client_id: str, client_name: str, firm, db_pool) -> ExtractedDocument:
    if not db_pool:
        raise HTTPException(status_code=503, detail="Document store unavailable")
    firm.require("books.propose")
    data, claimed_mime = await file.read(), file.content_type or ""
    digest = hashlib.sha256(data).hexdigest()
    async with db_pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id,legal_name,gstin,state FROM clients WHERE id=$1 AND firm_id=$2", client_id, firm.firm_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        duplicate = await conn.fetchrow(
            "SELECT id FROM documents WHERE firm_id=$1 AND client_id=$2 AND content_sha256=$3",
            firm.firm_id, client_id, digest,
        )
    if duplicate:
        placeholder = type("Upload", (), {"filename": file.filename or "document", "mime_type": claimed_mime,
                                           "size_bytes": len(data)})()
        async with db_pool.acquire() as conn:
            run_id = await _run(conn, firm.firm_id, client_id, placeholder, digest)
            await _state(conn, run_id, "DUPLICATE", document_id=str(duplicate["id"]),
                         user_action="Open the existing document or upload a different invoice.")
        from api.routes.documents import get_document
        return await get_document(duplicate["id"], firm, db_pool)
    try:
        inspected = inspect_upload(file.filename or "document", claimed_mime, data)
    except UploadRejected as exc:
        # Invalid bytes are audit evidence, but never permanent document evidence.
        async with db_pool.acquire() as conn:
            placeholder = type("Upload", (), {"filename": file.filename or "document", "mime_type": claimed_mime,
                                               "size_bytes": len(data)})()
            run_id = await _run(conn, firm.firm_id, client_id, placeholder, digest)
            await _state(conn, run_id, exc.state, error_code=exc.code, user_action=exc.user_action)
        raise HTTPException(status_code=422, detail={"code": exc.code, "state": exc.state,
                                                     "message": str(exc), "user_action": exc.user_action}) from exc
    upload = type("Upload", (), {**inspected.__dict__, "size_bytes": len(data)})()
    async with db_pool.acquire() as conn:
        run_id = await _run(conn, firm.firm_id, client_id, upload, digest)
        await _state(conn, run_id, "QUARANTINED")
    if upload.file_type == "image":
        try:
            from PIL import Image
            Image.open(io.BytesIO(data)).verify()
        except Exception as exc:
            async with db_pool.acquire() as conn:
                await _state(conn, run_id, "CORRUPT", error_code="IMAGE_CORRUPT",
                             user_action="Export the original image again and retry.")
            raise HTTPException(status_code=422, detail={"code": "IMAGE_CORRUPT", "state": "CORRUPT",
                                                         "message": "The image cannot be decoded."}) from exc
    doc_id = f"doc-{uuid.uuid4().hex[:12]}"
    object_key = f"{firm.firm_id}/{client_id}/{uuid.uuid4().hex}.{upload.extension}"
    try:
        file_url = await store_private_evidence("documents", object_key, data, upload.mime_type)
    except StorageUnavailable as exc:
        raise HTTPException(status_code=503, detail={"code": "PRIVATE_STORAGE_UNAVAILABLE", "retryable": True,
                                                     "message": str(exc)}) from exc
    async with db_pool.acquire() as conn:
        await _state(conn, run_id, "VALIDATED", object_key=file_url)
        await _state(conn, run_id, "READY_FOR_EXTRACTION")
    extract_data, mime = data, upload.mime_type
    if upload.file_type == "image":
        try:
            from PIL import Image
            image = Image.open(io.BytesIO(data)).convert("RGB")
            output = io.BytesIO(); image.save(output, format="JPEG", quality=95)
            extract_data, mime = output.getvalue(), "image/jpeg"
        except Exception:
            logging.warning("document_image_conversion_failed")
    started = time.monotonic()
    if upload.file_type == "spreadsheet":
        result = ExtractionResult.from_fields({
            "doc_kind": "VENDOR_BILL", "vendor_name": "", "vendor_gstin": "",
            "invoice_number": "", "invoice_date": "", "taxable_amount_paise": 0,
            "cgst_paise": 0, "sgst_paise": 0, "igst_paise": 0, "total_paise": 0,
            "line_items": [],
        }, "manual_xlsx", 0.0)
    else:
        from extraction.base import get_extractor
        result = await get_extractor().extract(extract_data, mime)
    latency_ms = int((time.monotonic() - started) * 1000)
    if not result.succeeded:
        async with db_pool.acquire() as conn:
            await _state(conn, run_id, "EXTRACTION_FAILED", error_code=result.reason_code,
                         user_action="Retry extraction or enter the invoice manually.")
            await conn.execute(
                """INSERT INTO extraction_runs(id,firm_id,client_id,evidence_url,provider,status,error_code,error_message)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",
                f"ext-{uuid.uuid4().hex[:12]}", firm.firm_id, client_id, file_url, result.provider,
                result.status, result.reason_code, result.reason_message,
            )
        raise HTTPException(status_code=422, detail={"code": "EXTRACTION_FAILED", "status": result.status,
                                                     "reason_code": result.reason_code, "message": result.reason_message})
    raw = result.fields
    raw_response_url = None
    try:
        raw_response_url = await store_private_evidence(
            "documents", f"{firm.firm_id}/{client_id}/raw/{uuid.uuid4().hex}.json",
            json.dumps(raw, separators=(",", ":")).encode(), "application/json",
        )
    except StorageUnavailable:
        logging.warning("document_raw_response_storage_failed")
    expense, expense_confidence = await _expense_head(raw, firm.firm_id, db_pool)
    doc = _document(doc_id, client_id, client_name or client["legal_name"], file_url, upload, raw, expense, expense_confidence)
    client_gstin = client.get("gstin") if hasattr(client, "get") else client["gstin"]
    canonical = dict(raw, client_gstin=client_gstin, other_charges_paise=0, currency="INR")
    identity = hashlib.sha256("|".join((str(raw.get("vendor_gstin") or "").upper(),
        str(raw.get("invoice_number") or "").casefold(), str(raw.get("invoice_date") or ""),
        str(raw.get("total_paise") or 0))).encode()).hexdigest()
    async with db_pool.acquire() as conn:
        likely_duplicate = await conn.fetchrow(
            """SELECT id FROM documents WHERE firm_id=$1 AND client_id=$2 AND invoice_identity_key=$3
               ORDER BY uploaded_at DESC LIMIT 1""", firm.firm_id, client_id, identity,
        )
    is_sales = doc.docKind in {"SALES_INVOICE", "CUSTOMER_INVOICE"}
    if is_sales:
        from core.sales_invoices.validation import validate_sales_invoice
        canonical.update({"invoice_number":raw.get("invoice_number"),"customer_name":raw.get("vendor_name"),
                          "seller_gstin":client_gstin,"customer_gstin":raw.get("vendor_gstin"),
                          "place_of_supply_state":raw.get("place_of_supply_state") or raw.get("place_of_supply")})
        findings = validate_sales_invoice(canonical)
    else:
        findings = validate_invoice(canonical)
    state = ""
    if likely_duplicate:
        findings.append({"code": "LIKELY_DUPLICATE", "severity": "ERROR", "field_key": "invoiceNumber",
                         "message": "Another invoice has the same supplier, number, date and total.",
                         "details": {"document_id": str(likely_duplicate["id"])}})
    state = validation_state(findings)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO documents(id,firm_id,client_id,client_name,file_url,file_type,doc_kind,status,vendor_name,
               fields,line_items,total,content_sha256,original_filename,mime_type,size_bytes,page_count,ingestion_state,
               validation_state,invoice_identity_key,duplicate_document_id,transaction_direction)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb,$12,$13,$14,$15,$16,$17,
               'READY_FOR_EXTRACTION',$18,$19,$20,$21)""",
            doc.id, firm.firm_id, doc.clientId, doc.clientName, file_url, doc.fileType, doc.docKind, doc.status,
            doc.vendorName, json.dumps([f.model_dump() for f in doc.fields]), json.dumps([l.model_dump() for l in doc.lineItems]),
            doc.total, digest, upload.filename, upload.mime_type, len(data), upload.page_count, state, identity,
            likely_duplicate["id"] if likely_duplicate else None, "SALE" if is_sales else "PURCHASE",
        )
        await _state(conn, run_id, "READY_FOR_EXTRACTION", document_id=doc.id)
        for finding in findings:
            await conn.execute(
                """INSERT INTO document_validation_findings(firm_id,document_id,code,severity,field_key,message,details)
                   VALUES($1,$2,$3,$4,$5,$6,$7::jsonb)""", firm.firm_id, doc.id, finding["code"], finding["severity"],
                finding["field_key"], finding["message"], json.dumps(finding["details"]),
            )
        for field_key, evidence in (raw.get("evidence") or {}).items():
            if not isinstance(evidence, dict):
                continue
            await conn.execute(
                """INSERT INTO document_field_evidence(firm_id,document_id,field_key,page,region,evidence_text,provider)
                   VALUES($1,$2,$3,$4,$5::jsonb,$6,$7) ON CONFLICT(document_id,field_key) DO NOTHING""",
                firm.firm_id, doc.id, field_key, evidence.get("page"), json.dumps(evidence.get("region")),
                str(evidence.get("text") or "")[:1000], result.provider,
            )
        await conn.execute(
            """INSERT INTO extraction_runs(id,firm_id,client_id,document_id,evidence_url,provider,status,
               model,raw_response_url,latency_ms)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""", f"ext-{uuid.uuid4().hex[:12]}", firm.firm_id, client_id,
            doc.id, file_url, result.provider, result.status, result.provider, raw_response_url, latency_ms,
        )
        await conn.execute("INSERT INTO audit_log(firm_id,action,actor,details) VALUES($1,'DOCUMENT_EXTRACTED','firmOS',$2::jsonb)",
                           firm.firm_id, json.dumps({"document_id": doc.id, "validation_state": state}))
    return doc
