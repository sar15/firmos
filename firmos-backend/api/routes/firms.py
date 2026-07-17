"""Firm membership routes for explicit tenant selection."""

from fastapi import APIRouter, Depends

from api.deps import FirmContext, get_current_firm, get_db

router = APIRouter(prefix="/api/firms", tags=["firms"])


@router.get("")
async def list_firms(
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT m.firm_id,m.role,COALESCE(f.name,m.firm_id) AS name
               FROM firm_memberships m
               LEFT JOIN firms f ON f.id::text=m.firm_id
               WHERE m.user_id=$1::uuid AND m.status='ACTIVE'
               ORDER BY f.name NULLS LAST,m.created_at""",
            firm.user_id,
        )
    return {
        "currentFirmId": firm.firm_id,
        "firms": [
            {"id": str(row["firm_id"]), "name": row["name"], "role": row["role"]}
            for row in rows
        ],
    }
