"""Supported desktop-agent API surface."""
from fastapi import APIRouter

from api.routes import tally_agent_actions, tally_agent_auth, tally_agent_sync

router = APIRouter(prefix="/api/tally-agent", tags=["tally-agent"])
router.include_router(tally_agent_auth.router)
router.include_router(tally_agent_sync.router)
router.include_router(tally_agent_actions.router)
