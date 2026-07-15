"""Fail-closed controls for provider writes.

The global setting can never be bypassed by a narrower override. Overrides are
kill switches only: a matching disabled row blocks the action immediately.
"""
from collections.abc import Iterable, Mapping
from typing import Any

from core.config import Settings, get_settings


def write_block_reason(
    provider: str,
    *,
    firm_id: str = "",
    client_id: str = "",
    installation_id: str = "",
    capability_key: str = "",
    overrides: Iterable[Mapping[str, Any]] = (),
    config: Settings | None = None,
) -> str | None:
    """Return the first fail-closed reason, or ``None`` when writes may proceed."""
    settings = config or get_settings()
    if not settings.provider_writes_enabled:
        return "PROVIDER_WRITES_DISABLED"
    provider_enabled = {
        "ZOHO_BOOKS": settings.zoho_writes_enabled,
        "TALLY_PRIME": settings.tally_writes_enabled,
    }.get(provider, False)
    if not provider_enabled:
        return "PROVIDER_WRITE_DISABLED"
    for override in overrides:
        if _matches(override, provider, firm_id, client_id, installation_id, capability_key):
            if not bool(override.get("is_enabled", override.get("enabled", False))):
                return "CAPABILITY_DISABLED"
    return None


async def scoped_write_block_reason(
    conn: Any,
    provider: str,
    *,
    firm_id: str,
    client_id: str,
    capability_key: str,
) -> str | None:
    """Apply database kill switches after the non-bypassable environment switches."""
    reason = write_block_reason(provider, firm_id=firm_id, client_id=client_id, capability_key=capability_key)
    if reason or conn is None:
        return reason
    try:
        rows = await conn.fetch(
            """SELECT firm_id, client_id, installation_id, provider, capability_key, is_enabled
               FROM capability_overrides WHERE firm_id IS NULL OR firm_id=$1""",
            firm_id,
        )
    except Exception:
        return "CAPABILITY_OVERRIDE_UNAVAILABLE"
    return write_block_reason(
        provider,
        firm_id=firm_id,
        client_id=client_id,
        capability_key=capability_key,
        overrides=(dict(row) for row in rows),
    )


def _matches(
    override: Mapping[str, Any],
    provider: str,
    firm_id: str,
    client_id: str,
    installation_id: str,
    capability_key: str,
) -> bool:
    fields = {
        "provider": provider,
        "firm_id": firm_id,
        "client_id": client_id,
        "installation_id": installation_id,
        "capability_key": capability_key,
    }
    return all(not override.get(key) or override[key] == value for key, value in fields.items())
