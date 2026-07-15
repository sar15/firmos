"""Truthful liveness, readiness, and setup diagnostics."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from api.deps import FirmContext, get_current_firm, get_db
from core.config import get_settings

router = APIRouter(prefix="/api/setup", tags=["setup"])
deployment_router = APIRouter(tags=["deployment"])
API_VERSION = "0.1.0"


def _storage_ready() -> bool:
    settings = get_settings()
    return settings.local_storage_allowed or bool(settings.supabase_url and settings.supabase_service_key)


async def _checks(db_pool, firm_id: str) -> list[dict]:
    settings = get_settings()
    checks = [
        {"id": "auth", "ready": settings.firmos_auth_mode == "jwt", "detail": "JWT authentication is required for deployment readiness."},
        {"id": "private_storage", "ready": _storage_ready(), "detail": "Private object storage must be configured."},
    ]
    if not db_pool:
        return checks + [{"id": "database", "ready": False, "detail": "Database pool is unavailable."}]
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            required_tables = [
                "extraction_runs", "decision_review_versions", "capability_overrides", "worker_heartbeats",
                "firm_memberships", "automation_jobs", "outbox_events", "connector_installations",
                "provider_objects", "verification_results",
            ]
            tables = await conn.fetchval(
                """SELECT COUNT(*) FROM unnest($1::text[]) AS name
                   WHERE to_regclass('public.' || name) IS NOT NULL""",
                required_tables,
            )
            queue_ready = await conn.fetchval("SELECT to_regclass('public.automation_jobs') IS NOT NULL")
            heartbeat_query = "SELECT MAX(seen_at) FROM worker_heartbeats"
            heartbeat = await conn.fetchval(heartbeat_query) if firm_id == "__deployment__" else await conn.fetchval(
                heartbeat_query + " WHERE firm_id=$1", firm_id,
            )
    except Exception:
        return checks + [{"id": "database", "ready": False, "detail": "Database or required schema is unavailable."}]
    worker_ready = bool(heartbeat and heartbeat >= datetime.now(timezone.utc) - timedelta(minutes=5))
    return checks + [
        {"id": "database", "ready": True, "detail": "Database reachable."},
        {"id": "migrations", "ready": tables == len(required_tables), "detail": "Required trust-spine migrations must be applied."},
        {"id": "queue", "ready": bool(queue_ready), "detail": "Postgres automation queue must be reachable."},
        {"id": "worker", "ready": worker_ready, "detail": "A worker heartbeat from the last five minutes is required."},
    ]


@deployment_router.get("/live")
async def live():
    """Process liveness only; no dependencies are consulted."""
    return {"status": "live", "version": API_VERSION}


@deployment_router.get("/ready")
async def ready(db_pool=Depends(get_db)):
    """Deployment readiness; any missing safety dependency returns 503."""
    checks = await _checks(db_pool, firm_id="__deployment__")
    is_ready = all(check["ready"] for check in checks)
    return JSONResponse(status_code=200 if is_ready else 503, content={"ready": is_ready, "checks": checks})


@deployment_router.get("/version")
async def version():
    return {"version": API_VERSION, "environment": get_settings().firmos_environment}


@router.get("/readiness")
async def readiness(firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    """Return the same factual readiness checks for a signed-in firm."""
    checks = await _checks(db_pool, firm.firm_id)
    return {"production_ready": all(check["ready"] for check in checks), "checks": checks}
