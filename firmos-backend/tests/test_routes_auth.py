"""Route auth-mode regressions kept separate from the seam test suite."""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_unauthenticated_is_rejected():
    from api.deps import get_current_firm
    previous = app.dependency_overrides.pop(get_current_firm, None)
    try:
        response = client.get("/api/clients")
    finally:
        if previous:
            app.dependency_overrides[get_current_firm] = previous
    assert response.status_code == 401


def test_get_zoho_organization_choice():
    response = client.get(
        "/api/connectors/c1/organization-choice/fc4a88df-d3c3-4ee1-8e81-1718e7d3ba33"
    )
    assert response.status_code != 500
