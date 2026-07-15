"""Tests for WS-4 Decision Cockpit."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.config import settings

client = TestClient(app)

def test_decision_context_and_draft():
    settings.firmos_auth_mode = "dev"
    
    # Mock db_pool
    class MockConnection:
        async def fetchrow(self, query, *args, **kwargs):
            if "context_data" in query and "decisions WHERE id" in query:
                return {
                    "context_data": '{"issue": "TDS rate mismatch"}',
                    "evidence": '["invoice.pdf"]',
                    "draft_response": "Initial draft."
                }
            return None
            
        async def execute(self, *args, **kwargs):
            return "UPDATE 1"
            
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass

    class MockPool:
        def acquire(self): return MockConnection()

    from api.deps import get_db
    app.dependency_overrides[get_db] = lambda: MockPool()

    # Test GET context
    resp = client.get("/api/decisions/d-1/context")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contextData"]["issue"] == "TDS rate mismatch"
    assert data["evidence"] == ["invoice.pdf"]
    
    # Test POST draft
    resp = client.post("/api/decisions/d-1/draft", json={"instructions": "Be polite."})
    assert resp.status_code == 200
    data = resp.json()
    assert "Based on the firmOS computation engine" in data["draftResponse"]

    app.dependency_overrides.clear()
