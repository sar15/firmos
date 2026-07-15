"""Deployment readiness must fail rather than report a preview as production-ready."""
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
