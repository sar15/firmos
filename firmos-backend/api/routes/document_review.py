"""Human document-review and finance-action proposal routes."""
import json
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException

from api.deps import FirmContext, get_current_firm, get_db
from api.routes import documents as document_routes
from api.routes.documents import (
    PrepareDocumentActionRequest, _date_for_zoho, _field_value, _same_name, _tax_paise,
)
from models.schemas import ExtractedDocument, ExtractedField
from core.money import rupees_to_paise
from core.purchase_invoices.validation import validate_invoice, validation_state

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("/{doc_id}/workspace")
async def review_workspace(doc_id: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    """Validation, evidence, revisions and connector choices for the review pane."""
    await document_routes.get_document(doc_id, firm, db_pool)
    async with db_pool.acquire() as conn:
        findings = await conn.fetch(
            """SELECT code,severity,field_key,message,details FROM document_validation_findings
               WHERE firm_id=$1 AND document_id=$2 ORDER BY severity,created_at""", firm.firm_id, doc_id,
        )
        evidence = await conn.fetch(
            """SELECT field_key,page,region,evidence_text,provider FROM document_field_evidence
               WHERE firm_id=$1 AND document_id=$2 ORDER BY field_key""", firm.firm_id, doc_id,
        )
        drafts = await conn.fetch(
            """SELECT provider,status,version,validation_state,mappings,totals,payload_hash,action_id
               FROM accounting_drafts WHERE firm_id=$1 AND document_id=$2 ORDER BY updated_at DESC""",
            firm.firm_id, doc_id,
        )
        connectors = await conn.fetch(
            """SELECT provider,status FROM connector_installations WHERE firm_id=$1
               AND client_id=(SELECT client_id FROM documents WHERE id=$2) AND provider=ANY($3::text[])""",
            firm.firm_id, doc_id, ["ZOHO_BOOKS", "TALLY_PRIME"],
        )
    finding_rows = [dict(row) for row in findings]
    evidence_rows = [dict(row) for row in evidence]
    draft_rows = [dict(row) for row in drafts]
    for row in finding_rows:
        if isinstance(row.get("details"), str): row["details"] = json.loads(row["details"])
    for row in evidence_rows:
        if isinstance(row.get("region"), str): row["region"] = json.loads(row["region"])
    for row in draft_rows:
        for key in ("mappings", "totals"):
            if isinstance(row.get(key), str): row[key] = json.loads(row[key])
    return {"findings": finding_rows, "evidence": evidence_rows,
            "drafts": draft_rows, "connectors": [dict(row) for row in connectors]}


@router.put("/{doc_id}/fields/{key}", response_model=ExtractedDocument)
async def update_field(doc_id: str, key: str, value: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    firm.require("books.propose")
    doc = await document_routes.get_document(doc_id, firm, db_pool)
    fields, found = [], False
    for field in doc.fields:
        if field.key == key:
            found = True
            fields.append(ExtractedField(key=field.key, label=field.label, value=value, confidence=1.0, level="HIGH", bbox=field.bbox))
        else:
            fields.append(field)
    if not found:
        raise HTTPException(status_code=404, detail="Field not found")
    updated = doc.model_copy(update={"fields": fields})
    if db_pool:
        async with db_pool.acquire() as conn:
            locked = await conn.fetchrow(
                """SELECT EXISTS(SELECT 1 FROM accounting_drafts d JOIN finance_actions a ON a.id=d.action_id
                   WHERE d.firm_id=$1 AND d.document_id=$2
                   AND a.status NOT IN ('AWAITING_APPROVAL','CANCELLED','FAILED','NEEDS_REVIEW')) AS locked""",
                firm.firm_id, doc_id,
            )
            if locked and bool(locked.get("locked", False)):
                raise HTTPException(status_code=409, detail="This document is already approved or posted; create a correction instead")
            await conn.execute("UPDATE documents SET fields=$1::jsonb, status='PENDING_REVIEW', updated_at=NOW() WHERE id=$2 AND firm_id=$3", json.dumps([field.model_dump() for field in fields]), doc_id, firm.firm_id)
            client = await conn.fetchrow("SELECT gstin FROM clients WHERE id=$1 AND firm_id=$2", doc.clientId, firm.firm_id)
            canonical = {
                "vendor_gstin": _field_value(updated, "gstin"), "client_gstin": client["gstin"] if client else "",
                "invoice_date": _field_value(updated, "invoiceDate"),
                "taxable_amount_paise": rupees_to_paise(_field_value(updated, "taxableAmount") or 0),
                "cgst_paise": rupees_to_paise(_field_value(updated, "cgst") or 0),
                "sgst_paise": rupees_to_paise(_field_value(updated, "sgst") or 0),
                "igst_paise": rupees_to_paise(_field_value(updated, "igst") or 0),
                "other_charges_paise": 0, "total_paise": rupees_to_paise(_field_value(updated, "total") or 0),
                "line_items": [item.model_dump() for item in updated.lineItems], "currency": "INR",
            }
            findings = validate_invoice(canonical)
            await conn.execute("DELETE FROM document_validation_findings WHERE firm_id=$1 AND document_id=$2", firm.firm_id, doc_id)
            for finding in findings:
                await conn.execute(
                    """INSERT INTO document_validation_findings(firm_id,document_id,code,severity,field_key,message,details)
                       VALUES($1,$2,$3,$4,$5,$6,$7::jsonb)""", firm.firm_id, doc_id, finding["code"],
                    finding["severity"], finding["field_key"], finding["message"], json.dumps(finding["details"]),
                )
            await conn.execute("UPDATE documents SET validation_state=$1 WHERE id=$2", validation_state(findings), doc_id)
            await conn.execute("UPDATE finance_actions SET status='CANCELLED', updated_at=NOW() WHERE id IN (SELECT action_id FROM accounting_drafts WHERE firm_id=$1 AND document_id=$2) AND status='AWAITING_APPROVAL'", firm.firm_id, doc_id)
            drafts = await conn.fetch(
                """UPDATE accounting_drafts SET status='NEEDS_REVIEW',action_id=NULL,payload='{}'::jsonb,
                   payload_hash=NULL,validation_state='PENDING',version=version+1,updated_at=NOW()
                   WHERE firm_id=$1 AND document_id=$2 AND status IN ('ACTION_PROPOSED','NEEDS_MAPPING') RETURNING *""",
                firm.firm_id, doc_id,
            )
            for draft in drafts:
                await conn.execute(
                    """INSERT INTO accounting_draft_revisions(draft_id,firm_id,version,schema_version,payload,mappings,
                       totals,validation_state,changed_by,change_reason)
                       VALUES($1,$2,$3,$4,'{}'::jsonb,$5,$6,'PENDING',$7,'Reviewer edited extracted field')""",
                    draft["id"], firm.firm_id, draft["version"], draft["schema_version"], draft["mappings"],
                    draft["totals"], firm.user_id,
                )
    return updated


@router.post("/{doc_id}/post")
async def post_to_books(doc_id: str, request: PrepareDocumentActionRequest | None = None, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    """Prepare an approval-bound proposal for the customer's selected connector."""
    firm.require("books.propose")
    doc, request = await document_routes.get_document(doc_id, firm, db_pool), request or PrepareDocumentActionRequest()
    if doc.docKind in {"SALES_INVOICE", "CUSTOMER_INVOICE"}:
        from core.sales_invoices.actions import propose_sale
        return await propose_sale(doc, request, firm, db_pool, field_value=_field_value,
                                  date_parser=_date_for_zoho, tax_paise=_tax_paise)
    from core.purchase_invoices.actions import propose_purchase
    return await propose_purchase(doc, request, firm, db_pool, field_value=_field_value,
                                  date_parser=_date_for_zoho, tax_paise=_tax_paise)


def _unique_match(options: list[dict], value: str) -> str | None:
    matches = [item["id"] for item in options if _same_name(item["label"], value)]
    return matches[0] if len(matches) == 1 else None


def _line(item, key: str, mapped_id: str | None, tax_id: str | None) -> dict:
    amount = int(Decimal(str(item.amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Every bill line needs a positive amount")
    return {key: mapped_id, "rate_paise": amount, "quantity": 1, "description": item.desc} | ({"tax_id": tax_id} if tax_id else {})


@router.post("/{doc_id}/reject", response_model=ExtractedDocument)
async def reject_document(doc_id: str, reason: str = "", firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    return await _set_status(doc_id, "REJECTED", firm, db_pool)


@router.post("/{doc_id}/needs-info", response_model=ExtractedDocument)
async def mark_needs_info(doc_id: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    return await _set_status(doc_id, "NEEDS_INFO", firm, db_pool)


async def _set_status(doc_id: str, status: str, firm: FirmContext, db_pool) -> ExtractedDocument:
    document = await document_routes.get_document(doc_id, firm, db_pool)
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE documents SET status=$1, updated_at=NOW() WHERE id=$2 AND firm_id=$3", status, doc_id, firm.firm_id)
    return document.model_copy(update={"status": status})
