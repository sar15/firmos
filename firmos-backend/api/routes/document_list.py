"""Read and private-download document routes."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.deps import FirmContext, get_current_firm, get_db
from api.routes.documents import _model
from core.private_storage import StorageUnavailable, create_signed_url, local_evidence_path
from models.schemas import ExtractedDocument

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=list[ExtractedDocument])
async def list_documents(firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    if not db_pool:
        return []
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM documents WHERE firm_id = $1 ORDER BY uploaded_at DESC", firm.firm_id)
    return [_model(row) for row in rows]


@router.get("/{doc_id}/download")
async def get_document_download(doc_id: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Document store unavailable")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT file_url FROM documents WHERE id=$1 AND firm_id=$2", doc_id, firm.firm_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    stored_url = str(row["file_url"] or "")
    try:
        if stored_url.startswith("storage://documents/"):
            return {"url": await create_signed_url(stored_url), "expires_in_seconds": 300}
        if stored_url.startswith("local://documents/"):
            return FileResponse(local_evidence_path(stored_url))
    except StorageUnavailable as exc:
        raise HTTPException(status_code=503, detail="Document evidence is unavailable") from exc
    raise HTTPException(status_code=409, detail="Legacy public document location cannot be served securely")
