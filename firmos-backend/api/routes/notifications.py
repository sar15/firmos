"""Notification reads and deliberately disabled WhatsApp ingestion."""

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_firm, FirmContext
from models.schemas import AppNotification

router = APIRouter(tags=["notifications"])

from api.deps import get_db

@router.get("/api/notifications", response_model=list[AppNotification])
async def list_notifications(
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    """GET /api/notifications → listNotifications()"""
    if db_pool:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM notifications WHERE firm_id = $1 ORDER BY created_at DESC",
                firm.firm_id
            )
            if rows:
                return [
                    AppNotification(
                        id=row["id"],
                        group=row["group"],
                        title=row["title"],
                        clientName=row["client_name"] or "",
                        timestamp=row["timestamp"] or "",
                        isRead=row["is_read"],
                        actionUrl=row["action_url"] or "",
                        urgency=row["urgency"] or "royal"
                    )
                    for row in rows
                ]
    
    return []


@router.post("/api/notifications/{notif_id}/read")
async def mark_read(
    notif_id: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    """POST /api/notifications/{id}/read → markRead(id)"""
    if db_pool:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE notifications SET is_read = TRUE WHERE id = $1 AND firm_id = $2",
                notif_id, firm.firm_id
            )
            if result == "UPDATE 1":
                return {"ok": True}

    raise HTTPException(status_code=503, detail="Notification store unavailable")


@router.post("/api/notifications/read-all")
async def mark_all_read(
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    """POST /api/notifications/read-all → markAllRead()"""
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE notifications SET is_read = TRUE WHERE firm_id = $1",
                firm.firm_id
            )
            return {"ok": True}

    raise HTTPException(status_code=503, detail="Notification store unavailable")


# --- WhatsApp Webhook ---

@router.get("/api/webhook/whatsapp")
async def whatsapp_verify():
    raise HTTPException(status_code=503, detail={"code": "CAPABILITY_DISABLED", "capability": "whatsapp.inbound"})


@router.post("/api/webhook/whatsapp")
async def whatsapp_inbound():
    raise HTTPException(status_code=503, detail={"code": "CAPABILITY_DISABLED", "capability": "whatsapp.inbound"})
