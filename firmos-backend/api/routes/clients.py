"""Clients API routes — mirrors clients.api.ts seam."""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional

from api.deps import get_current_firm, FirmContext, get_db
from models.schemas import Client, Decision, ExtractedDocument

router = APIRouter(prefix="/api/clients", tags=["clients"])


def _books_provider(value: Optional[str]) -> str:
    return value or "NONE"


@router.get("", response_model=list[Client])
async def list_clients(
    entity_type: Optional[str] = Query(None, alias="entityType"),
    status: Optional[str] = None,
    books_provider: Optional[str] = Query(None, alias="booksProvider"),
    search: Optional[str] = Query(None, alias="q"),
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db),
):
    """GET /api/clients → listClients(filter?)"""
    from core.config import settings
    mock_clients = [
        Client(
            id="cli-seed-101",
            legalName="Sharma & Sons Logistics Pvt Ltd",
            pan="AABCS1429B",
            gstin="27AABCS1429B1Z5",
            entityType="PRIVATE_LIMITED",
            state="MH",
            nextDue="2026-07-20T00:00:00Z",
            complianceStatus="DUE_SOON",
            booksProvider="ZOHO_BOOKS",
        ),
        Client(
            id="cli-seed-102",
            legalName="Apex Polymers India LLP",
            pan="AAXFA8821C",
            gstin="27AAXFA8821C1Z8",
            entityType="LLP",
            state="MH",
            nextDue="2026-07-24T00:00:00Z",
            complianceStatus="ON_TRACK",
            booksProvider="TALLY",
        ),
    ]
    if not db_pool:
        if settings.strict_no_mock:
            raise HTTPException(status_code=503, detail="Database connection required under STRICT_NO_MOCK=true")
        return mock_clients
        
    try:
        # Build query dynamically
        query = "SELECT * FROM clients WHERE firm_id = $1"
        args = [firm.firm_id]
        idx = 2

        if entity_type:
            query += f" AND entity_type = ${idx}"
            args.append(entity_type)
            idx += 1
        if status:
            query += f" AND compliance_status = ${idx}"
            args.append(status)
            idx += 1
        if books_provider:
            query += f" AND books_provider = ${idx}"
            args.append(books_provider)
            idx += 1
        if search:
            query += f" AND (legal_name ILIKE ${idx} OR pan ILIKE ${idx} OR gstin ILIKE ${idx})"
            args.append(f"%{search}%")
            idx += 1

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [
                Client(
                    id=row["id"],
                    legalName=row["legal_name"],
                    pan=row["pan"] or "",
                    gstin=row["gstin"] or "",
                    entityType=row["entity_type"] or "",
                    state=row["state"] or "",
                    booksProvider=_books_provider(row["books_provider"]),
                    nextDue=row["next_due"].isoformat() if row["next_due"] else "",
                    complianceStatus=row["compliance_status"]
                )
                for row in rows
            ]
    except Exception as e:
        if settings.strict_no_mock:
            raise
        return mock_clients

@router.get("/search")
async def search_everything(
    q: str = Query(...),
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db),
):
    """GET /api/clients/search → searchEverything(q)"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    query = q.lower()
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM clients WHERE firm_id = $1 AND (legal_name ILIKE $2 OR pan ILIKE $2 OR gstin ILIKE $2)",
            firm.firm_id, f"%{query}%"
        )
        matched_clients = [
            Client(
                id=row["id"],
                legalName=row["legal_name"],
                pan=row["pan"] or "",
                gstin=row["gstin"] or "",
                entityType=row["entity_type"] or "",
                state=row["state"] or "",
                booksProvider=_books_provider(row["books_provider"]),
                nextDue=row["next_due"].isoformat() if row["next_due"] else "",
                complianceStatus=row["compliance_status"]
            )
            for row in rows
        ]
        return {
            "clients": matched_clients,
            "decisions": [],
            "documents": [],
        }

@router.get("/{client_id}", response_model=Client)
async def get_client(
    client_id: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db),
):
    """GET /api/clients/{id}"""
    from core.config import settings
    mock_client = Client(
        id=client_id,
        legalName="Sharma & Sons Logistics Pvt Ltd",
        pan="AABCS1429B",
        gstin="27AABCS1429B1Z5",
        entityType="PRIVATE_LIMITED",
        state="MH",
        nextDue="2026-07-20T00:00:00Z",
        complianceStatus="DUE_SOON",
        booksProvider="ZOHO_BOOKS",
    )
    if not db_pool:
        if settings.strict_no_mock:
            raise HTTPException(status_code=503, detail="Database connection required under STRICT_NO_MOCK=true")
        return mock_client
        
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM clients WHERE id = $1 AND firm_id = $2", client_id, firm.firm_id)
            if not row:
                raise HTTPException(status_code=404, detail="Client not found")
                
            return Client(
                id=row["id"],
                legalName=row["legal_name"],
                pan=row["pan"] or "",
                gstin=row["gstin"] or "",
                entityType=row["entity_type"] or "",
                state=row["state"] or "",
                booksProvider=_books_provider(row["books_provider"]),
                nextDue=row["next_due"].isoformat() if row["next_due"] else "",
                complianceStatus=row["compliance_status"]
            )
    except HTTPException:
        raise
    except Exception as e:
        if settings.strict_no_mock:
            raise
        return mock_client

@router.get("/{client_id}/profile")
async def get_client_profile(
    client_id: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db),
):
    """GET /api/clients/{id}/profile"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    async with db_pool.acquire() as conn:
        client_row = await conn.fetchrow("SELECT * FROM clients WHERE id = $1 AND firm_id = $2", client_id, firm.firm_id)
        if not client_row:
            raise HTTPException(status_code=404, detail="Client not found")
            
        docs = await conn.fetch(
            "SELECT id, file_url, doc_kind, status, uploaded_at FROM documents WHERE client_id = $1 AND firm_id = $2 ORDER BY uploaded_at DESC LIMIT 5",
            client_id, firm.firm_id
        )
        
        decs = await conn.fetch(
            "SELECT id, flag, status, amount, created_at FROM decisions WHERE client_id = $1 AND firm_id = $2 ORDER BY created_at DESC LIMIT 5",
            client_id, firm.firm_id
        )
        
        return {
            "client": Client(
                id=client_row["id"],
                legalName=client_row["legal_name"],
                pan=client_row["pan"] or "",
                gstin=client_row["gstin"] or "",
                entityType=client_row["entity_type"] or "",
                state=client_row["state"] or "",
                booksProvider=_books_provider(client_row["books_provider"]),
                nextDue=client_row["next_due"].isoformat() if client_row["next_due"] else "",
                complianceStatus=client_row["compliance_status"]
            ).model_dump(),
            "recentDocuments": [
                {
                    "id": d["id"],
                    "fileUrl": d["file_url"],
                    "docKind": d["doc_kind"],
                    "status": d["status"],
                    "uploadedAt": d["uploaded_at"].isoformat() + "Z"
                } for d in docs
            ],
            "recentDecisions": [
                {
                    "id": d["id"],
                    "task": d["flag"] or "Decision",
                    "status": d["status"],
                    "amount": d["amount"],
                    "createdAt": d["created_at"].isoformat() + "Z"
                } for d in decs
            ]
        }
