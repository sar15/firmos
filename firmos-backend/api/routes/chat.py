from fastapi import APIRouter, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

from api.deps import get_current_firm, FirmContext, get_db

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatMessagePayload(BaseModel):
    client_id: str
    period: str
    text: str


def _inr(paise: int) -> str:
    return f"₹{paise / 100:,.2f}"

@router.get("/session/{client_id}")
async def get_chat_session(
    client_id: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    if not db_pool:
        return {"timeline": []}
        
    async with db_pool.acquire() as conn:
        # 1. Fetch chat messages
        chat_rows = await conn.fetch(
            """
            SELECT id, role, text, created_at 
            FROM chat_messages 
            WHERE firm_id = $1 AND client_id = $2 
            ORDER BY created_at ASC 
            LIMIT 100
            """,
            firm.firm_id, client_id
        )
        
        # 2. Show only audit entries that explicitly belong to this client.
        audit_rows = await conn.fetch(
            """
            SELECT id, action, actor, details, created_at 
            FROM audit_log 
            WHERE firm_id = $1 AND details->>'client_id' = $2
            ORDER BY created_at ASC 
            LIMIT 100
            """,
            firm.firm_id, client_id,
        )
        
        timeline = []
        for row in chat_rows:
            timeline.append({
                "type": "message",
                "id": str(row["id"]),
                "role": row["role"],
                "text": row["text"],
                "createdAt": row["created_at"].isoformat() + "Z"
            })
            
        for row in audit_rows:
            # We map audit entries to step cards in the UI
            timeline.append({
                "type": "audit_entry",
                "id": str(row["id"]),
                "action": row["action"],
                "actor": row["actor"],
                "details": row["details"] if row["details"] else {},
                "createdAt": row["created_at"].isoformat() + "Z"
            })
            
        # Sort combined timeline chronologically
        timeline.sort(key=lambda x: x["createdAt"])
        
        return {"timeline": timeline}

@router.post("/session")
async def post_chat_message(
    payload: ChatMessagePayload,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    if not db_pool:
        return {"ok": False}
        
    async with db_pool.acquire() as conn:
        # Save user message
        await conn.execute(
            """
            INSERT INTO chat_messages (firm_id, client_id, role, text)
            VALUES ($1, $2, $3, $4)
            """,
            firm.firm_id, payload.client_id, "user", payload.text
        )
        
        sales = await conn.fetchrow(
            "SELECT COUNT(*) AS count, COALESCE(SUM(total_paise), 0) AS total FROM sales_register WHERE firm_id=$1 AND client_id=$2 AND period=$3",
            firm.firm_id, payload.client_id, payload.period,
        )
        purchases = await conn.fetchrow(
            "SELECT COUNT(*) AS count, COALESCE(SUM(total_paise), 0) AS total FROM purchase_register WHERE firm_id=$1 AND client_id=$2 AND period=$3",
            firm.firm_id, payload.client_id, payload.period,
        )
        evidence = await conn.fetchrow(
            "SELECT uploaded_at FROM gstr2b_uploads WHERE firm_id=$1 AND client_id=$2 AND period=$3",
            firm.firm_id, payload.client_id, payload.period,
        )
        sales_count, sales_total = int(sales["count"]), int(sales["total"])
        purchase_count, purchase_total = int(purchases["count"]), int(purchases["total"])
        text_lower = payload.text.lower()
        agent_reply = (
            f"For {payload.period}, the live register context has {sales_count} sales entries ({_inr(sales_total)}) "
            f"and {purchase_count} purchase entries ({_inr(purchase_total)}). "
            "Use a typed action proposal to write to Zoho Books or Tally Prime."
        )

        if "sales" in text_lower:
            agent_reply = f"Sales register for {payload.period}: {sales_count} entries totaling {_inr(sales_total)}. Sync Zoho Registers if this looks incomplete."
        elif "purchase" in text_lower or "exception" in text_lower:
            agent_reply = f"Purchase register for {payload.period}: {purchase_count} entries totaling {_inr(purchase_total)}. Open Reconciliation to inspect evidence-backed exceptions."
        elif "bill" in text_lower or "invoice" in text_lower or "post" in text_lower:
            agent_reply = "I need the selected invoice and accounting fields before I can create a reviewable action proposal."
        elif "gst" in text_lower or "3b" in text_lower:
            evidence_status = "is uploaded" if evidence else "has not been uploaded"
            agent_reply = f"GSTR-2B evidence {evidence_status} for {payload.period}. Open the manual GST pack to review sales, purchases, mismatches, and the CA checklist. Portal submission stays manual."
        elif "overdue" in text_lower:
            agent_reply = "Open the client context for live register totals and pending actions; firmOS does not claim overdue filings without current evidence."

        # Save agent reply
        await conn.execute(
            """
            INSERT INTO chat_messages (firm_id, client_id, role, text)
            VALUES ($1, $2, $3, $4)
            """,
            firm.firm_id, payload.client_id, "agent", agent_reply
        )

    return {"ok": True, "reply": agent_reply}
