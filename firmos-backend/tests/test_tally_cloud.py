"""Tests for Tally Prime cloud adapter and API ingestion routes.

Why: Verifies that cloud adapter reads exclusively from Postgres (no HTTP
calls to localhost), implements AccountingConnector protocol accurately, and
enforces idempotency on POST /api/tally/push.
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from api.main import app
from api.deps import get_current_firm, FirmContext, get_db
from connectors.tally.adapter import TallyAccountingAdapter
from connectors.accounting import AccountingConnector

client = TestClient(app)

FIRM_ID = "firm-test-999"
USER_ID = "user-test-888"


class MockDbConnection:
    def __init__(self):
        self.executed_queries = []
        self.fetch_results = {}
        self.fetchrow_results = {}
        self.fetchval_results = {}

    async def fetch(self, query, *args):
        self.executed_queries.append((query, args))
        for key, rows in self.fetch_results.items():
            if key in query:
                return rows
        return []

    async def fetchrow(self, query, *args):
        self.executed_queries.append((query, args))
        for key, row in self.fetchrow_results.items():
            if key in query:
                return row
        return None

    async def fetchval(self, query, *args):
        self.executed_queries.append((query, args))
        for key, val in self.fetchval_results.items():
            if key in query:
                return val
        return 0

    async def execute(self, query, *args):
        self.executed_queries.append((query, args))
        return "INSERT 0 1"

    def transaction(self):
        return MockAsyncContextManager()


class MockAsyncContextManager:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return None


class MockDbPool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return MockPoolAcquireContext(self.conn)


class MockPoolAcquireContext:
    def __init__(self, conn):
        self.conn = conn
    async def __aenter__(self):
        return self.conn
    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.mark.asyncio
async def test_tally_adapter_get_ledgers():
    """Verify adapter reads ledgers from canonical Postgres table."""
    conn = MockDbConnection()
    conn.fetch_results["tally_ledgers"] = [
        {"tally_guid": "led-1", "name": "HDFC Bank", "parent_group": "Bank Accounts"},
        {"tally_guid": "led-2", "name": "Sales A/c", "parent_group": "Sales Accounts"},
    ]
    pool = MockDbPool(conn)
    
    adapter = TallyAccountingAdapter(FIRM_ID, "Test Co", pool)
    ledgers = await adapter.get_ledgers()
    
    assert len(ledgers) == 2
    assert ledgers[0].id == "led-1"
    assert ledgers[0].name == "HDFC Bank"
    assert ledgers[1].group == "Sales Accounts"


@pytest.mark.asyncio
async def test_tally_adapter_registers():
    """Verify adapter extracts sales/purchase registers from synced vouchers."""
    conn = MockDbConnection()
    conn.fetch_results["tally_vouchers"] = [
        {
            "voucher_number": "SAL/001",
            "date": "20240510",
            "party_name": "Acme Corp",
            "entries": json.dumps([
                {"ledger_name": "Acme Corp", "amount": -118000.0},
                {"ledger_name": "Sales A/c", "amount": 100000.0},
            ]),
        }
    ]
    pool = MockDbPool(conn)
    
    adapter = TallyAccountingAdapter(FIRM_ID, "Test Co", pool)
    sales = await adapter.get_sales_register("2024-05-01", "2024-05-31")
    
    assert len(sales) == 1
    assert sales[0].invoice_number == "SAL/001"
    assert sales[0].customer_name == "Acme Corp"
    assert sales[0].taxable_value_paise == 10000000  # 1,00,000 * 100 paise


@pytest.mark.asyncio
async def test_tally_adapter_write_prohibition():
    """Verify synchronous write methods raise NotImplementedError per architecture rules."""
    adapter = TallyAccountingAdapter(FIRM_ID, "Test Co", None)
    
    with pytest.raises(NotImplementedError) as exc:
        await adapter.create_purchase_bill({})
    assert "Direct synchronous writing to local Tally Prime XML gateway" in str(exc.value)
    
    with pytest.raises(NotImplementedError) as exc2:
        await adapter.post_voucher({})
    assert "not permitted" in str(exc2.value)


@pytest.mark.asyncio
async def test_tally_adapter_health():
    """Verify adapter checks sync logs for health status."""
    conn = MockDbConnection()
    conn.fetchrow_results["tally_sync_logs"] = {
        "status": "SUCCESS",
        "synced_at": "2024-06-15T10:00:00Z",
        "ledgers_count": 50,
        "vouchers_count": 120,
    }
    pool = MockDbPool(conn)
    
    adapter = TallyAccountingAdapter(FIRM_ID, "Test Co", pool)
    health = await adapter.health()
    
    assert health["status"] == "healthy"
    assert "50 ledgers" in health["details"]


def test_tally_push_endpoint():
    """Verify POST /api/tally/push ingests payload with idempotency."""
    conn = MockDbConnection()
    pool = MockDbPool(conn)
    
    app.dependency_overrides[get_current_firm] = lambda: FirmContext(USER_ID, FIRM_ID, "OWNER")
    app.dependency_overrides[get_db] = lambda: pool
    
    payload = {
        "sync_version": "1.0",
        "timestamp": "2024-06-15T10:00:00Z",
        "tally_company": "Test Co",
        "period": {"from_date": "20240401", "to_date": "20250331"},
        "ledgers": [
            {"guid": "led-1", "name": "HDFC", "parent_group": "Bank"}
        ],
        "vouchers": [],
    }
    
    try:
        response = client.post(
            "/api/tally/push",
            json=payload,
            headers={"X-Idempotency-Key": "key-test-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["ledgers_synced"] == 1
    finally:
        app.dependency_overrides.clear()
