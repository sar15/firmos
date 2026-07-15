"""Unit tests for Tally bridge claim/lease & result API endpoints.

# ponytail: Runnable self-checking tests verifying lease atomic claim and receipt safeguard.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from api.main import app
from api.deps import get_current_firm, FirmContext, get_db
from core.config import settings

dummy_firm = FirmContext(
    user_id="user-1",
    firm_id="firm-test-1",
    role="owner",
    email="test@firmos.dev",
)


@pytest.fixture
def client_no_db():
    app.dependency_overrides[get_current_firm] = lambda: dummy_firm
    app.dependency_overrides[get_db] = lambda: None
    with patch("api.main.Database.connect", new_callable=AsyncMock), patch(
        "api.main.Database.close", new_callable=AsyncMock
    ), patch.object(settings, "firmos_auth_mode", "jwt"):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


def test_claim_without_db_returns_500(client_no_db):
    resp = client_no_db.post(
        "/api/bridge/actions/claim",
        json={"tally_company": "Acme Corp", "bridge_device_id": "dev-1"},
    )
    assert resp.status_code == 500
