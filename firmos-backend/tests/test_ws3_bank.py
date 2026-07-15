"""Tests for WS-3 Bank Statement Ingestion and Recon."""

import pytest
from fastapi.testclient import TestClient
import io

from api.main import app
from core.config import settings

client = TestClient(app)

def test_bank_statement_upload_and_recon():
    settings.firmos_auth_mode = "dev"
    
    # Mock db_pool
    class MockConnection:
        async def fetch(self, query, *args, **kwargs):
            if "bank_transactions" in query:
                return [
                    {
                        "id": "txn-1",
                        "txn_date": "2024-06-15T00:00:00Z",
                        "description": "Payment from Customer",
                        "amount": 5000000,
                        "txn_type": "CREDIT"
                    }
                ]
            return []
            
        async def execute(self, *args, **kwargs):
            return "INSERT 1"
            
        async def executemany(self, *args, **kwargs):
            return "INSERT 0 1"
            
        async def fetchrow(self, query, *args, **kwargs):
            return None
            
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass

    class MockPool:
        def acquire(self): return MockConnection()

    from api.deps import get_db
    app.dependency_overrides[get_db] = lambda: MockPool()

    # 1. Test upload
    csv_content = b"Date,Description,Amount,Type,Balance\n2024-06-15,Payment from Customer,50000,CREDIT,100000\n"
    file_like = io.BytesIO(csv_content)
    file_like.name = "statement.csv"
    
    resp = client.post(
        "/api/bank-statements/upload",
        data={"client_id": "c-1"},
        files={"file": ("statement.csv", file_like, "text/csv")}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["transactionsCount"] == 1
    
    # 2. Test recon
    class MockConnectionRecon:
        async def fetch(self, query, *args, **kwargs):
            import datetime
            if "bank_transactions" in query:
                return [
                    {
                        "id": "txn-1",
                        "txn_date": datetime.date(2024, 6, 15),
                        "description": "Payment from Customer",
                        "amount": 5000000,
                        "txn_type": "CREDIT"
                    }
                ]
            return []
            
        async def execute(self, *args, **kwargs):
            return "INSERT 1"
            
        async def fetchrow(self, query, *args, **kwargs):
            # No Zoho/GSP connection in test — returns None
            return None
            
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass

    class MockPoolRecon:
        def acquire(self): return MockConnectionRecon()

    app.dependency_overrides[get_db] = lambda: MockPoolRecon()
    
    resp = client.get("/api/reconciliation/c-1?mode=BANK_STATEMENT&period=062024")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONNECTOR_AUTH_REQUIRED"

    app.dependency_overrides.clear()
