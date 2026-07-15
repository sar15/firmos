"""Shared deterministic settings for backend tests."""

import base64

import pytest


TEST_SETTINGS = {
    "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
    "SUPABASE_JWT_SECRET": "test-jwt-secret-for-supabase",
    "SUPABASE_URL": "https://test.supabase.co",
    "TOKEN_ENC_KEY": base64.b64encode(b"0" * 32).decode(),
    "FIRMOS_AUTH_MODE": "jwt",
    "FIRMOS_ENVIRONMENT": "test",
    "STRICT_NO_MOCK": "true",
    "PROVIDER_WRITES_ENABLED": "true",
    "ZOHO_WRITES_ENABLED": "true",
    "TALLY_WRITES_ENABLED": "true",
    "ALLOWED_ORIGINS": "http://localhost:3000",
}

OPTIONAL_SECRET_SETTINGS = (
    "SUPABASE_SERVICE_KEY", "SENTRY_DSN", "GEMINI_API_KEY", "SARVAM_API_KEY",
    "ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN", "GSP_API_KEY", "GSP_API_SECRET",
    "WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN",
)


@pytest.fixture(autouse=True)
def configured_settings(monkeypatch):
    """Set valid settings before each test and discard the cached instance after it."""
    for name in OPTIONAL_SECRET_SETTINGS:
        monkeypatch.delenv(name, raising=False)
    for name, value in TEST_SETTINGS.items():
        monkeypatch.setenv(name, value)

    from core.config import settings
    from api.deps import FirmContext, get_current_firm
    from api.main import app

    async def test_identity():
        return FirmContext("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "11111111-1111-1111-1111-111111111111", "OWNER")

    settings.clear()
    previous = app.dependency_overrides.get(get_current_firm)
    app.dependency_overrides[get_current_firm] = test_identity
    yield
    if previous is None:
        app.dependency_overrides.pop(get_current_firm, None)
    else:
        app.dependency_overrides[get_current_firm] = previous
    settings.clear()
