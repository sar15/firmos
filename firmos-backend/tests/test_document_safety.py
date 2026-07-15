"""Safety invariants for evidence upload and extraction failure paths."""
import base64

from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app
from core.config import settings
from extraction.result import ExtractionResult, ExtractionStatus


class RecordingConnection:
    def __init__(self):
        self.executed: list[str] = []

    async def fetchrow(self, *_args):
        if "FROM clients" in _args[0]:
            return {"id": "client-1", "legal_name": "Safety Test", "gstin": "", "state": ""}
        if "INSERT INTO document_ingestion_runs" in _args[0]:
            return {"id": "11111111-1111-1111-1111-111111111111"}
        return None

    async def execute(self, query, *_args):
        self.executed.append(query)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class RecordingPool:
    def __init__(self):
        self.connection = RecordingConnection()

    def acquire(self):
        return self.connection


def _upload(client: TestClient):
    jpeg = base64.b64decode(
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
        "2wBDAf//////////////////////////////////////////////////////////////////////////////////////"
        "wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9oADAMBAAIAAwAAABD/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/EF//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/EF//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/EF//2Q=="
    )
    return client.post(
        "/api/documents/upload",
        files={"file": ("invoice.jpg", jpeg, "image/jpeg")},
        data={"client_id": "client-1", "client_name": "Safety Test"},
    )


def _override_pool(pool: RecordingPool):
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: pool
    return previous


def _restore_pool(previous):
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def test_production_storage_outage_creates_no_document(monkeypatch):
    monkeypatch.setenv("FIRMOS_ENVIRONMENT", "production")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    settings.clear()
    pool = RecordingPool()
    previous = _override_pool(pool)
    try:
        response = _upload(TestClient(app))
    finally:
        _restore_pool(previous)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "PRIVATE_STORAGE_UNAVAILABLE"
    assert not any("INSERT INTO documents" in query for query in pool.connection.executed)


def test_extraction_failure_persists_run_without_document(monkeypatch, tmp_path):
    class FailedExtractor:
        async def extract(self, *_args):
            return ExtractionResult.failure(
                ExtractionStatus.PROVIDER_ERROR, "API_KEY_MISSING", "Extraction is not configured.", "gemini"
            )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FIRMOS_ENVIRONMENT", "test")
    monkeypatch.setattr("extraction.base.get_extractor", lambda: FailedExtractor())
    settings.clear()
    pool = RecordingPool()
    previous = _override_pool(pool)
    try:
        response = _upload(TestClient(app))
    finally:
        _restore_pool(previous)
    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "API_KEY_MISSING"
    assert any("INSERT INTO extraction_runs" in query for query in pool.connection.executed)
    assert not any("INSERT INTO documents" in query for query in pool.connection.executed)
