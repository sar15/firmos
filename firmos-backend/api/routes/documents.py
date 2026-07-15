"""Thin document read and ingestion endpoints."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from api.deps import FirmContext, get_current_firm, get_db
from core.money import rupees_to_paise
from models.schemas import ExtractedDocument, ExtractedField, LineItem

router = APIRouter(prefix="/api/documents", tags=["documents"])


class PrepareDocumentActionRequest(BaseModel):
    """Reviewer choices plus the connector the customer selected."""
    provider: str = "ZOHO_BOOKS"
    vendor_id: str | None = None
    account_id: str | None = None
    customer_id: str | None = None
    item_id: str | None = None
    tax_id: str | None = None
    party_ledger: str | None = None
    purchase_ledger: str | None = None
    sales_ledger: str | None = None
    cgst_ledger: str | None = None
    sgst_ledger: str | None = None
    igst_ledger: str | None = None


def _field_value(doc: ExtractedDocument, *keys: str) -> str:
    return next((field.value.strip() for field in doc.fields if field.key in keys and field.value.strip()), "")


def _same_name(left: object, right: object) -> bool:
    return " ".join(str(left or "").casefold().split()) == " ".join(str(right or "").casefold().split())


def _date_for_zoho(value: str) -> str:
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError("Invoice date must use YYYY-MM-DD, DD/MM/YYYY, or DD-MM-YYYY")


def _taxable_paise(doc: ExtractedDocument) -> int:
    return rupees_to_paise(_field_value(doc, "taxableAmount", "taxable_amount") or 0)


def _tax_paise(doc: ExtractedDocument) -> int:
    return sum(rupees_to_paise(_field_value(doc, key) or 0) for key in ("cgst", "sgst", "igst"))


def _document_file_url(doc_id: str, stored_url: str) -> str:
    return f"/api/documents/{doc_id}/download" if stored_url.startswith(("storage://documents/", "local://documents/")) else stored_url


def _model(row) -> ExtractedDocument:
    fields = json.loads(row["fields"]) if isinstance(row["fields"], str) else row["fields"]
    items = json.loads(row["line_items"]) if isinstance(row["line_items"], str) else row["line_items"]
    return ExtractedDocument(
        id=row["id"], clientId=row["client_id"], clientName=row["client_name"],
        fileUrl=_document_file_url(row["id"], row["file_url"]), fileType=row["file_type"],
        docKind=row["doc_kind"], status=row["status"], vendorName=row["vendor_name"],
        fields=[ExtractedField(**field) for field in fields], lineItems=[LineItem(**item) for item in items],
        total=row["total"], uploadedAt=row["uploaded_at"].isoformat().replace("+00:00", "Z"),
    )


@router.get("/{doc_id}", response_model=Optional[ExtractedDocument])
async def get_document(doc_id: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM documents WHERE id=$1 AND firm_id=$2", doc_id, firm.firm_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return _model(row)


@router.post("/upload", response_model=ExtractedDocument)
async def upload_document(
    file: UploadFile = File(...), client_id: str = Form(...), client_name: str = Form(default=""),
    firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db),
):
    from core.purchase_invoices.ingestion import ingest_purchase
    return await ingest_purchase(file, client_id, client_name, firm, db_pool)
