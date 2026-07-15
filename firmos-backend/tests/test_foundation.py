"""Tests for Phase 0 foundation: crypto round-trip, JWT auth, env validation."""

import base64
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from jose import jwt


# Generate a test encryption key (32 bytes, base64-encoded)
TEST_ENC_KEY = base64.b64encode(os.urandom(32)).decode()
TEST_JWT_SECRET = "test-jwt-secret-for-supabase"
TEST_FIRM_ID = "11111111-1111-1111-1111-111111111111"
TEST_FIRM_ID_OTHER = "22222222-2222-2222-2222-222222222222"
TEST_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set required env vars so Settings doesn't crash."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("TOKEN_ENC_KEY", TEST_ENC_KEY)


# ---- Crypto round-trip ----

def test_encrypt_decrypt_round_trip():
    """Encrypt a token, decrypt it, get the same string back."""
    from core.security import encrypt_token, decrypt_token

    original = "ya29.a0ARrdaM_some_oauth_token_here"
    encrypted = encrypt_token(original)

    assert isinstance(encrypted, bytes)
    assert encrypted != original.encode()  # actually encrypted, not plaintext
    assert len(encrypted) > 12  # at least nonce + some ciphertext

    decrypted = decrypt_token(encrypted)
    assert decrypted == original


def test_encrypt_different_nonces():
    """Two encryptions of the same plaintext produce different ciphertext (random nonce)."""
    from core.security import encrypt_token

    token = "refresh_token_abc123"
    enc1 = encrypt_token(token)
    enc2 = encrypt_token(token)
    assert enc1 != enc2  # different nonces


def test_decrypt_tampered_fails():
    """Tampered ciphertext raises an error."""
    from core.security import StoredCredentialError, decrypt_token, encrypt_token

    encrypted = encrypt_token("some_token")
    tampered = encrypted[:-1] + bytes([encrypted[-1] ^ 0xFF])

    with pytest.raises(StoredCredentialError):
        decrypt_token(tampered)


@pytest.mark.asyncio
async def test_stored_credential_error_returns_503():
    from api.main import stored_credential_error
    from core.security import StoredCredentialError
    from starlette.requests import Request

    response = await stored_credential_error(Request(scope={"type": "http"}), StoredCredentialError())
    assert response.status_code == 503
    assert b"Reconnect the connector" in response.body


def test_encrypt_empty_string():
    """Edge case: empty string round-trips."""
    from core.security import encrypt_token, decrypt_token

    encrypted = encrypt_token("")
    assert decrypt_token(encrypted) == ""


# ---- JWT decode ----

def _make_jwt(payload: dict) -> str:
    """Helper to create a test JWT using the ACTUAL settings secret."""
    from core.config import settings
    claims = {"iss": "https://test.supabase.co/auth/v1", "aud": "authenticated", **payload}
    return jwt.encode(claims, settings.supabase_jwt_secret, algorithm="HS256")


def test_jwt_decode_valid():
    """Valid JWT with firm_id decodes correctly."""
    from core.security import decode_supabase_jwt

    token = _make_jwt({
        "sub": TEST_USER_ID,
        "firm_id": TEST_FIRM_ID,
        "exp": int(time.time()) + 3600,
    })
    payload = decode_supabase_jwt(token)
    assert payload["sub"] == TEST_USER_ID
    assert payload["firm_id"] == TEST_FIRM_ID


def test_jwt_decode_expired():
    """Expired JWT raises ValueError."""
    from core.security import decode_supabase_jwt

    token = _make_jwt({
        "sub": TEST_USER_ID,
        "firm_id": TEST_FIRM_ID,
        "exp": int(time.time()) - 100,
    })
    with pytest.raises(ValueError, match="Invalid JWT"):
        decode_supabase_jwt(token)


def test_jwt_decode_wrong_secret():
    """JWT signed with wrong secret raises ValueError."""
    from core.security import decode_supabase_jwt

    token = jwt.encode(
        {"sub": TEST_USER_ID, "exp": int(time.time()) + 3600},
        "wrong-secret",
        algorithm="HS256",
    )
    with pytest.raises(ValueError, match="Invalid JWT"):
        decode_supabase_jwt(token)


# ---- Auth dependency ----

@pytest.mark.asyncio
async def test_get_current_firm_requires_bearer_token():
    from api.deps import get_current_firm
    from fastapi import HTTPException
    from starlette.requests import Request

    request = Request(scope={"type": "http", "headers": []})
    with pytest.raises(HTTPException) as error:
        await get_current_firm(request)
    assert error.value.status_code == 401


# ---- Env validation ----

def test_settings_loads_from_env():
    """Settings object loads correctly from env vars."""
    from core.config import Settings

    s = Settings()  # type: ignore[call-arg]
    assert s.database_url == "postgresql://test:test@localhost:5432/test"
    assert s.supabase_jwt_secret == TEST_JWT_SECRET
    assert s.token_enc_key == TEST_ENC_KEY


def test_get_settings_is_cached():
    """Application settings are constructed once after test environment setup."""
    from core.config import get_settings

    assert get_settings() is get_settings()


def test_config_import_defers_required_setting_validation(tmp_path):
    """Configuration import is safe before the process has production secrets."""
    env = os.environ.copy()
    for name in ("DATABASE_URL", "SUPABASE_JWT_SECRET", "TOKEN_ENC_KEY"):
        env.pop(name, None)
    env["PYTHONPATH"] = str(Path(__file__).parents[1])

    result = subprocess.run(
        [sys.executable, "-c", "import core.config"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_settings_missing_required_crashes(monkeypatch):
    """Missing required env var raises ValidationError."""
    from pydantic import ValidationError
    from core.config import Settings

    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


# ---- Pydantic model shapes ----

def test_extracted_document_shape():
    """ExtractedDocument accepts the exact shape from documents.mock.ts."""
    from models.schemas import ExtractedDocument

    doc = ExtractedDocument(
        id="doc-101",
        clientId="c-1",
        clientName="Acme Corp",
        fileUrl="/samples/vendor-bill-1.jpg",
        fileType="image",
        docKind="VENDOR_BILL",
        status="PENDING_REVIEW",
        vendorName="Shree Traders",
        fields=[{
            "key": "vendorName",
            "label": "Vendor Name",
            "value": "Shree Traders",
            "confidence": 0.95,
            "level": "HIGH",
            "bbox": {"page": 1, "x": 10, "y": 10, "w": 40, "h": 10},
        }],
        lineItems=[{"desc": "Office Supplies", "hsn": "8471", "qty": 10, "rate": 1000, "amount": 10000}],
        total=1845000,
        uploadedAt="2026-06-27T10:00:00Z",
    )
    assert doc.docKind == "VENDOR_BILL"
    assert doc.total == 1845000  # paise, not rupees


def test_connector_rich_schema():
    """Connector model uses the rich ConnectorSchema (per Q1 decision)."""
    from models.schemas import Connector

    c = Connector(
        id="c1",
        name="Zoho Books",
        category="FEATURED",
        description="Sync purchase & sales registers",
        status="CONNECTED",
        authMethod="OAUTH",
        lastSyncedAt="2026-06-27T09:18:00Z",
    )
    assert c.status == "CONNECTED"
    assert c.authMethod == "OAUTH"


def test_notification_urgency_design_tokens():
    """Notification urgency uses design tokens (red/amber/royal), not severity levels."""
    from models.schemas import AppNotification

    n = AppNotification(
        id="notif-1",
        group="NEEDS_YOU",
        title="GST Notice",
        clientName="Acme",
        timestamp="2 hours ago",
        isRead=False,
        actionUrl="/decisions/dec-2",
        urgency="royal",
    )
    assert n.urgency == "royal"
