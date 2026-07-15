"""Connector discovery and guarded installation routes."""
import copy

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import FirmContext, get_current_firm, get_db
from api.routes.connector_catalog import CONNECTOR_CATALOG
from api.routes.connector_zoho_oauth import (
    OrganizationChoice,
    get_zoho_organization_choice,
    oauth_state_digest as _oauth_state_digest,
    organization_choices as _organization_choices,
    resolve_zoho_redirect_uri as _resolve_zoho_redirect_uri,
    router as zoho_oauth_router,
    select_zoho_organization,
    start_zoho_oauth,
    zoho_callback,
)
from core.config import settings

router = APIRouter(prefix="/api/connectors", tags=["connectors"])
router.include_router(zoho_oauth_router)


@router.get("")
async def list_connectors(
    firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db),
):
    catalog = copy.deepcopy(CONNECTOR_CATALOG)
    if db_pool:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT CASE provider WHEN 'ZOHO_BOOKS' THEN 'c1' WHEN 'TALLY_PRIME' THEN 'c5' END connector_id,
                          updated_at FROM connector_installations
                   WHERE firm_id=$1 AND status IN ('AVAILABLE','DEGRADED')""", firm.firm_id,
            )
        connected = {row["connector_id"]: row["updated_at"] for row in rows if row["connector_id"]}
        for category in catalog:
            for item in category["items"]:
                if item["id"] in connected:
                    item["status"] = "CONNECTED"
                    item["lastSyncedAt"] = connected[item["id"]].isoformat() + "Z"
    return catalog


@router.post("/{connector_id}/connect")
async def connect_connector(
    connector_id: str, request: Request,
    firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db),
):
    if connector_id == "c1":
        configured = settings.zoho_client_id and not settings.zoho_client_id.startswith("your_")
        if not configured:
            raise HTTPException(status_code=409, detail="Zoho Books OAuth is not configured for this deployment")
        if not db_pool:
            raise HTTPException(status_code=503, detail="Database not connected")
        return await start_zoho_oauth(request, firm, db_pool)
    if connector_id == "c5":
        raise HTTPException(status_code=409, detail="TallyPrime connects with a one-time FirmOS Tally Agent pairing code")
    if connector_id == "c2":
        raise HTTPException(status_code=409, detail="GSTR-2B is uploaded manually from the GST portal")
    raise HTTPException(status_code=501, detail="This connector is not available yet")
