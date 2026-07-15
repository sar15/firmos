"""Tests for WS-6 Dashboard and Client Profile."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.config import settings

client = TestClient(app)

def test_stream_endpoint():
    """Test the GET /api/stream endpoint."""
    settings.firmos_auth_mode = "dev"
    
    class MockConnection:
        async def fetch(self, *args, **kwargs):
            return []
        async def fetchrow(self, *args, **kwargs):
            return None
        async def execute(self, *args, **kwargs):
            pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass

    class MockPool:
        def acquire(self): return MockConnection()

    from api.deps import get_db
    app.dependency_overrides[get_db] = lambda: MockPool()
    
    resp = client.get("/api/stream")
    assert resp.status_code == 200
    data = resp.json()
    assert "groups" in data
    assert isinstance(data["groups"], list)

    app.dependency_overrides.clear()

def test_client_profile_endpoint():
    """Test the GET /api/clients/{id}/profile endpoint."""
    settings.firmos_auth_mode = "dev"
    
    class MockConnection:
        async def fetch(self, query, *args, **kwargs):
            return []
        async def fetchrow(self, query, *args, **kwargs):
            return {
                "id": "c-1",
                "legal_name": "Test Client",
                "pan": "ABCDE1234F",
                "gstin": "",
                "entity_type": "PRIVATE_LIMITED",
                "state": "MH",
                "books_provider": "ZOHO_BOOKS",
                "next_due": None,
                "compliance_status": "ON_TRACK"
            }
        async def execute(self, *args, **kwargs):
            pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass

    class MockPool:
        def acquire(self): return MockConnection()

    from api.deps import get_db
    app.dependency_overrides[get_db] = lambda: MockPool()
    
    resp = client.get("/api/clients/c-1/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert "client" in data
    assert data["client"]["legalName"] == "Test Client"
    assert "recentDocuments" in data
    assert "recentDecisions" in data
    
    app.dependency_overrides.clear()
