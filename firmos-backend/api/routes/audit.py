from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from api.deps import get_current_firm, FirmContext, get_db

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("")
async def list_audit_logs(
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    if not db_pool:
        return []
        
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, action, actor, details, created_at FROM audit_log WHERE firm_id = $1 ORDER BY created_at DESC LIMIT 100",
            firm.firm_id
        )
        
        results = []
        for row in rows:
            results.append({
                "id": str(row["id"]),
                "action": row["action"],
                "actor": row["actor"],
                "details": row["details"] if row["details"] else {},
                "createdAt": row["created_at"].isoformat() + "Z"
            })
            
        return results
