"""Deployment readiness must fail rather than report a preview as production-ready."""
from datetime import datetime, timezone

import pytest

from api.routes.readiness import _checks, live, version


@pytest.mark.asyncio
async def test_readiness_reports_jwt_but_fails_without_database():
    checks = await _checks(None, "firm-1")
    assert {check["id"] for check in checks} == {"auth", "private_storage", "database"}
    assert next(check for check in checks if check["id"] == "auth")["ready"]
    assert not next(check for check in checks if check["id"] == "database")["ready"]


@pytest.mark.asyncio
async def test_liveness_and_version_are_explicit():
    assert (await live())["status"] == "live"
    assert (await version())["version"] == "0.1.0"


class ReadinessConnection:
    def __init__(self):
        self.heartbeat_call = None

    async def fetchval(self, query, *args):
        if "MAX(seen_at)" in query:
            self.heartbeat_call = (query, args)
            return datetime.now(timezone.utc)
        if "COUNT(*)" in query:
            return 10
        return True


class ReadinessAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_args):
        return None


class ReadinessPool:
    def __init__(self):
        self.connection = ReadinessConnection()

    def acquire(self):
        return ReadinessAcquire(self.connection)


@pytest.mark.asyncio
async def test_deployment_readiness_requires_automation_worker_heartbeat():
    pool = ReadinessPool()

    checks = await _checks(pool, "__deployment__")

    assert next(check for check in checks if check["id"] == "worker")["ready"]
    query, args = pool.connection.heartbeat_call
    assert "firm_id=$1 AND worker_kind=$2" in query
    assert args == ("__deployment__", "AUTOMATION_WORKER")
