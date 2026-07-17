"""Tests for FastAPI routes — all 5 seams."""
import os
import base64
import time

import pytest
from fastapi.testclient import TestClient
from jose import jwt

# Set env vars before importing app
TEST_ENC_KEY = base64.b64encode(os.urandom(32)).decode()
TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-bytes-long"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["SUPABASE_JWT_SECRET"] = TEST_JWT_SECRET
os.environ["TOKEN_ENC_KEY"] = TEST_ENC_KEY
from api.main import app
from core.security import encrypt_token
client = TestClient(app)
FIRM_ID = "11111111-1111-1111-1111-111111111111"
USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
class MockConnection:
    async def fetch(self, *args, **kwargs):
        if "SELECT * FROM clients" in args[0]:
            return [{"id": "c-1", "legal_name": "Acme", "entity_type": "PRIVATE_LIMITED", "pan": "", "gstin": "", "state": "", "books_provider": None, "next_due": None, "compliance_status": "ON_TRACK"}]
        if "FROM notifications" in args[0]:
            return [{
                "id": "notif-1", "group": "NEEDS_YOU", "title": "Review required",
                "client_name": "Acme", "timestamp": "now", "is_read": False,
                "action_url": "/decisions/dec-1", "urgency": "amber",
            }]
        return []
    async def fetchrow(self, *args, **kwargs):
        query = args[0]
        if "oauth_connection_attempts" in query:
            return {"id": "dummy", "organizations": '[{"organization_id": "org-1", "name": "Acme Books"}]'}
        if "connections WHERE" in query:
            return {"external_account_id": "ext-1", "access_token_enc": encrypt_token("dummy"), "refresh_token_enc": encrypt_token("dummy")}
        if "INSERT INTO documents" in query or "UPDATE documents" in query or "RETURNING" in query:
            import datetime
            return {"id": "d-1", "doc_kind": "VENDOR_BILL", "status": "PENDING_REVIEW", "file_type": "image", "client_id": "c-1", "client_name": "Acme", "firm_id": FIRM_ID, "fields": "[]", "validation_errors": "[]", "file_url": "foo", "vendor_name": "Test Vendor", "total": 1000000, "line_items": "[]", "uploaded_at": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)}
        if "FROM documents" in query:
            import datetime
            doc_id = args[1] if len(args) > 1 else "d-1"
            return {"id": doc_id, "doc_kind": "VENDOR_BILL", "status": "PENDING_REVIEW", "file_type": "image", "client_id": "c-1", "client_name": "Acme", "firm_id": FIRM_ID, "fields": '[{"key": "vendorName", "label": "Vendor", "value": "Old", "confidence": 0.5, "level": "LOW"}]', "validation_errors": "[]", "file_url": "foo", "confidence_score": 0.9, "raw_text": "", "vendor_name": "Test Vendor", "total": 1000000, "line_items": "[]", "uploaded_at": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)}
        return {"id": "c-1", "legal_name": "Acme", "entity_type": "PRIVATE_LIMITED", "pan": "", "gstin": "", "state": "", "books_provider": "NONE", "next_due": None, "compliance_status": "ON_TRACK", "file_url": "foo", "doc_kind": "VENDOR_BILL", "status": "PENDING_REVIEW", "uploaded_at": "2024-01-01T00:00:00Z", "client_name": "Acme", "client_id": "c-1", "vendor_name": "Test Vendor", "total": 1000000, "line_items": "[]"}
    async def execute(self, *args, **kwargs):
        return "UPDATE 1"
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc, tb): pass

class MockPool:
    def acquire(self): return MockConnection()

from api.deps import get_db
app.dependency_overrides[get_db] = lambda: MockPool()

class MockExtractor:
    async def extract(self, file_bytes: bytes, mime_type: str):
        from extraction.result import ExtractionResult

        return ExtractionResult.from_fields({
            "vendor_name": "Test Vendor",
            "vendor_gstin": "27AAACA1234A1Z1",
            "invoice_number": "INV-123",
            "invoice_date": "2024-06-15",
            "taxable_amount_paise": 100000,
            "cgst_paise": 9000,
            "sgst_paise": 9000,
            "igst_paise": 0,
            "total_paise": 118000,
            "line_items": [
                {
                    "desc": "Software License",
                    "hsn": "9983",
                    "qty": 1,
                    "rate_paise": 100000,
                    "amount_paise": 100000
                }
            ],
            "confidence": 0.95
        }, "test", 0.95)

def mock_get_extractor():
    return MockExtractor()

import extraction.base
extraction.base.get_extractor = mock_get_extractor

def _auth_header() -> dict:
    """Create a valid JWT auth header."""
    token = jwt.encode(
        {"sub": USER_ID, "app_metadata": {"firm_id": FIRM_ID}, "exp": int(time.time()) + 3600},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}

# ---- Health ----
def test_health(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abcdef1234567890")
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["commit"] == "abcdef123456"


# ---- Clients ----

def test_list_clients():
    resp = client.get("/api/clients", headers=_auth_header())
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "legalName" in data[0]
    assert data[0]["booksProvider"] == "NONE"


def test_list_clients_filter():
    resp = client.get("/api/clients?entityType=PRIVATE_LIMITED", headers=_auth_header())
    assert resp.status_code == 200
    data = resp.json()
    for c in data:
        assert c["entityType"] == "PRIVATE_LIMITED"


def test_search_everything():
    resp = client.get("/api/clients/search?q=Acme", headers=_auth_header())
    assert resp.status_code == 200
    data = resp.json()
    assert "clients" in data
    assert data["clients"][0]["booksProvider"] == "NONE"
    assert "decisions" in data
    assert "documents" in data


# ---- Documents ----

def test_list_documents():
    resp = client.get("/api/documents", headers=_auth_header())
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_upload_and_get_document():
    # Upload
    resp = client.post(
        "/api/documents/upload",
        headers=_auth_header(),
        files={"file": ("test.jpg", b"fake-image-data", "image/jpeg")},
        data={"client_id": "cl-1", "client_name": "Test Corp"},
    )
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["docKind"] == "VENDOR_BILL"
    assert doc["status"] == "PENDING_REVIEW"
    assert doc["fileType"] == "image"
    doc_id = doc["id"]

    # Get
    resp = client.get(f"/api/documents/{doc_id}", headers=_auth_header())
    assert resp.status_code == 200
    assert resp.json()["id"] == doc_id


def test_update_field():
    # Upload first
    resp = client.post(
        "/api/documents/upload",
        headers=_auth_header(),
        files={"file": ("test.pdf", b"fake-pdf", "application/pdf")},
        data={"client_id": "cl-1"},
    )
    doc_id = resp.json()["id"]

    # Update a field
    resp = client.put(
        f"/api/documents/{doc_id}/fields/vendorName?value=Updated+Vendor",
        headers=_auth_header(),
    )
    assert resp.status_code == 200
    updated = resp.json()
    vendor_field = next(f for f in updated["fields"] if f["key"] == "vendorName")
    assert vendor_field["value"] == "Updated Vendor"
    assert vendor_field["confidence"] == 1.0
    assert vendor_field["level"] == "HIGH"


def test_reject_document():
    resp = client.post(
        "/api/documents/upload",
        headers=_auth_header(),
        files={"file": ("test.jpg", b"data", "image/jpeg")},
        data={"client_id": "cl-1"},
    )
    doc_id = resp.json()["id"]

    resp = client.post(f"/api/documents/{doc_id}/reject", headers=_auth_header())
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"


def test_needs_info():
    resp = client.post(
        "/api/documents/upload",
        headers=_auth_header(),
        files={"file": ("test.jpg", b"data", "image/jpeg")},
        data={"client_id": "cl-1"},
    )
    doc_id = resp.json()["id"]

    resp = client.post(f"/api/documents/{doc_id}/needs-info", headers=_auth_header())
    assert resp.status_code == 200
    assert resp.json()["status"] == "NEEDS_INFO"


# ---- Connectors ----

def test_list_connectors():
    resp = client.get("/api/connectors", headers=_auth_header())
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "title" in data[0]  # Category shape
    assert "items" in data[0]


# ---- Reconciliation ----

def test_get_reconciliation():
    resp = client.get("/api/reconciliation/cl-1?mode=GSTR2B_VS_PURCHASE&period=062026", headers=_auth_header())
    assert resp.status_code == 200
    data = resp.json()
    assert "matches" in data
    assert "summary" in data
    summary = data["summary"]
    assert "autoMatched" in summary
    assert "suggested" in summary
    assert "unmatched" in summary
@pytest.mark.asyncio
async def test_bank_reconciliation_handles_unreadable_zoho_tokens(monkeypatch):
    from api.routes.reconciliation import _build_bank_target_from_zoho
    async def unreadable(*_args):
        raise ValueError("bad token")

    monkeypatch.setattr("connectors.zoho_books.legacy_credentials.legacy_zoho_client", unreadable)
    from core.errors import AppError
    with pytest.raises(AppError) as error:
        await _build_bank_target_from_zoho(object(), FIRM_ID, "062026", None)
    assert error.value.code == "ZOHO_BANK_READ_FAILED"


async def test_bank_reconciliation_binds_real_dates():
    from datetime import date

    from api.routes.reconciliation import _build_bank_source

    class Connection:
        args = None

        async def fetch(self, *args):
            self.args = args
            return []

    connection = Connection()
    assert await _build_bank_source(connection, FIRM_ID, "client-1", "062026") == []
    assert connection.args[3:] == (date(2026, 6, 1), date(2026, 6, 30))


def test_accept_match():
    resp = client.post("/api/reconciliation/matches/rm-1/accept", headers=_auth_header(), json={
        "client_id": "cl-1", "period": "062026", "mode": "GSTR2B_VS_PURCHASE", "source_id": "pr-1", "target_id": "2b-1",
    })
    assert resp.status_code == 200


def test_bulk_accept():
    resp = client.post("/api/reconciliation/bulk-accept?mode=GSTR2B_VS_PURCHASE&client_id=cl-1&period=062026", headers=_auth_header())
    assert resp.status_code == 200


# ---- Notifications ----

def test_list_notifications():
    resp = client.get("/api/notifications", headers=_auth_header())
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "urgency" in data[0]
    assert data[0]["urgency"] in ("red", "amber", "royal")


def test_mark_read():
    resp = client.post("/api/notifications/notif-1/read", headers=_auth_header())
    assert resp.status_code == 200


def test_mark_all_read():
    resp = client.post("/api/notifications/read-all", headers=_auth_header())
    assert resp.status_code == 200
