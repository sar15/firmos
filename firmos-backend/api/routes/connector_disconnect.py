"""Connector credential revocation and local disconnect routes."""
import logging

from fastapi import APIRouter, Depends, HTTPException

from api.deps import FirmContext, get_current_firm, get_db

router = APIRouter(prefix="/api/connectors", tags=["connectors"])
log = logging.getLogger(__name__)


@router.post("/{connector_id}/disconnect")
async def disconnect_connector(
    connector_id: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    """Remove local connector credentials; Zoho token revocation is best effort."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    try:
        async with db_pool.acquire() as conn:
            if connector_id == "c1":
                installation_ids = await conn.fetch(
                    """SELECT id FROM connector_installations
                       WHERE firm_id=$1 AND provider='ZOHO_BOOKS' AND status!='DISCONNECTED'""",
                    firm.firm_id,
                )
                row = await conn.fetchrow(
                    "SELECT refresh_token_enc FROM connections WHERE firm_id = $1 AND connector_id = $2",
                    firm.firm_id, connector_id,
                )
                if row and row["refresh_token_enc"]:
                    from connectors.zoho_books.auth import revoke_token
                    from core.security import decrypt_token

                    try:
                        await revoke_token(decrypt_token(row["refresh_token_enc"]))
                    except Exception:
                        log.warning("zoho_token_revoke_failed")
            await conn.execute("DELETE FROM connections WHERE firm_id = $1 AND connector_id = $2", firm.firm_id, connector_id)
        if connector_id == "c1":
            from connectors.zoho_books.connector import ZohoBooksV1Connector
            for installation in installation_ids:
                await ZohoBooksV1Connector(db_pool, str(installation["id"])).disconnect()
    except Exception as exc:
        log.error("connector_disconnect_failed")
        raise HTTPException(status_code=503, detail="Connector could not be disconnected; retry later") from exc
    return {"status": "DISCONNECTED", "connector_id": connector_id}
