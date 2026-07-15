"""Truthful installation health aggregation."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Health:
    state: str
    blockers: tuple[str, ...]


def evaluate_health(*, credential_ok: bool, scopes_ok: bool, identity_ok: bool,
                    sync_fresh: bool, worker_ok: bool, write_certified: bool) -> Health:
    checks = {"CREDENTIALS": credential_ok, "SCOPES": scopes_ok, "IDENTITY": identity_ok,
              "SYNC_STALE": sync_fresh, "WORKER": worker_ok, "WRITE_CERTIFICATION": write_certified}
    blockers = tuple(name for name, ok in checks.items() if not ok)
    return Health("AVAILABLE" if not blockers else "DEGRADED", blockers)
