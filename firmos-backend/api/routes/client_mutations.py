"""Firm-local client mutations; connector writes are intentionally excluded."""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import FirmContext, get_current_firm, get_db
from models.schemas import Client


router = APIRouter(prefix="/api/clients", tags=["clients"])


class ClientCreate(BaseModel):
    legalName: str
    pan: str
    gstin: Optional[str] = ""
    entityType: Optional[str] = ""
    state: Optional[str] = ""
    booksProvider: Optional[str] = ""


def _client_response(client_id: str, data: ClientCreate) -> Client:
    return Client(
        id=client_id, legalName=data.legalName, pan=data.pan, gstin=data.gstin or "",
        entityType=data.entityType or "", state=data.state or "", booksProvider=data.booksProvider or "",
        nextDue=datetime.date.today().isoformat(), complianceStatus="ON_TRACK",
    )


@router.post("", response_model=Client)
async def create_client(
    client_data: ClientCreate, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)
):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    client_id = f"cl-{uuid.uuid4().hex[:8]}"
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO clients (
                id, firm_id, legal_name, pan, gstin, entity_type, state, books_provider, compliance_status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'ON_TRACK')""",
            client_id, firm.firm_id, client_data.legalName, client_data.pan, client_data.gstin,
            client_data.entityType, client_data.state, client_data.booksProvider,
        )
    return _client_response(client_id, client_data)


@router.put("/{client_id}", response_model=Client)
async def update_client(
    client_id: str, client_data: ClientCreate, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)
):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    async with db_pool.acquire() as conn:
        if not await conn.fetchrow("SELECT id FROM clients WHERE id = $1 AND firm_id = $2", client_id, firm.firm_id):
            raise HTTPException(status_code=404, detail="Client not found")
        await conn.execute(
            """UPDATE clients SET
                legal_name = $1, pan = $2, gstin = $3, entity_type = $4, state = $5, books_provider = $6
            WHERE id = $7 AND firm_id = $8""",
            client_data.legalName, client_data.pan, client_data.gstin, client_data.entityType,
            client_data.state, client_data.booksProvider, client_id, firm.firm_id,
        )
    return _client_response(client_id, client_data)


@router.delete("/{client_id}")
async def delete_client(
    client_id: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)
):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    async with db_pool.acquire() as conn:
        if not await conn.fetchrow("SELECT id FROM clients WHERE id = $1 AND firm_id = $2", client_id, firm.firm_id):
            raise HTTPException(status_code=404, detail="Client not found")
        await conn.execute("DELETE FROM clients WHERE id = $1 AND firm_id = $2", client_id, firm.firm_id)
    return {"ok": True}
