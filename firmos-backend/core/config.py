"""Environment settings, validated when the application starts."""

from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Single source of truth for all env vars. Never use os.getenv elsewhere."""

    # Core
    database_url: str = Field(..., description="Supabase Postgres connection string")
    supabase_jwt_secret: str = Field(..., description="JWT secret from Supabase project settings")
    supabase_url: str = Field(default="", description="Supabase project URL")
    supabase_service_key: str = Field(default="", description="Supabase service role key")
    supabase_jwt_issuer: str = Field(default="", description="Expected JWT issuer; defaults to <SUPABASE_URL>/auth/v1")
    supabase_jwt_audience: str = Field(default="authenticated", description="Expected JWT audience")
    token_enc_key: str = Field(..., description="32-byte base64-encoded AES-256-GCM key")
    firmos_auth_mode: str = Field(default="dev", description="Auth mode: dev | jwt")
    firmos_environment: str = Field(default="production", description="Runtime: production | local | test")
    strict_no_mock: bool = Field(default=True, description="Raise immediately if any fallback or mock path is attempted")
    provider_writes_enabled: bool = Field(default=False, description="Global emergency switch for all provider writes")
    zoho_writes_enabled: bool = Field(default=False, description="Allow certified Zoho write actions")
    tally_writes_enabled: bool = Field(default=False, description="Allow certified Tally bridge write actions")
    credential_key_version: str = Field(default="v1", description="Active connector credential encryption key version")

    # Monitoring
    sentry_dsn: str = Field(default="", description="Sentry DSN (empty = disabled)")
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection")

    # Extraction
    gemini_api_key: str = Field(default="", description="Google AI Studio API key for Gemini")
    sarvam_api_key: str = Field(default="", description="Sarvam AI API key")
    gemini_project: str = Field(default="", description="GCP project for Vertex AI Gemini (legacy)")
    gemini_region: str = Field(default="asia-south1", description="Vertex AI region (legacy)")
    extractor_type: str = Field(default="sarvam", description="Extractor backend: sarvam | gemini | selfhosted")
    model_primary: str = Field(default="gemini-2.5-flash-lite", description="Primary (cheap) extraction model")
    model_escalate: str = Field(default="gemini-2.5-flash", description="Escalation model for low-confidence results")

    # Zoho Books (Phase 2)
    zoho_client_id: str = Field(default="", description="Zoho API Console client ID")
    zoho_client_secret: str = Field(default="", description="Zoho API Console client secret")
    zoho_redirect_uri: str = Field(default="", description="OAuth callback URL")
    zoho_organization_id: str = Field(default="", description="Zoho Books organization ID")
    zoho_refresh_token: str = Field(default="", description="Zoho OAuth refresh token (access_type=offline)")

    # GSP (Phase 1)
    gsp_api_key: str = Field(default="", description="GSP API key (client_id)")
    gsp_api_secret: str = Field(default="", description="GSP API secret (client_secret)")
    gsp_base_url: str = Field(default="https://apisandbox.whitebooks.in", description="GSP sandbox/prod base URL")
    gst_provider: str = Field(default="whitebooks", description="GSP provider: whitebooks")
    test_gstin: str = Field(default="", description="Test taxpayer GSTIN")
    gst_username: str = Field(default="", description="GST Portal username")
    whitebooks_email: str = Field(default="", description="WhiteBooks registered email")

    # WhatsApp (Phase 5)
    whatsapp_app_id: str = Field(default="", description="Meta app ID")
    whatsapp_app_secret: str = Field(default="", description="Meta app secret")
    whatsapp_verify_token: str = Field(default="", description="Webhook verify token")

    # App
    frontend_url: str = Field(default="http://localhost:3000", description="Public frontend URL used after OAuth callbacks")
    allowed_origins: str = Field(default="http://localhost:3000", description="CORS origins, comma-separated")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def local_storage_allowed(self) -> bool:
        return self.firmos_environment in {"local", "test"}


@lru_cache
def get_settings() -> Settings:
    """Return the validated settings for the current process."""
    return Settings()  # type: ignore[call-arg]


class _SettingsProxy:
    """Keep legacy imports lazy while callers migrate to ``get_settings``."""

    def __getattr__(self, name: str):
        value = getattr(get_settings(), name)
        # Store accessed fields so unittest.mock can restore patched values.
        object.__setattr__(self, name, value)
        return value

    def __setattr__(self, name: str, value: object) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        setattr(get_settings(), name, value)
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        object.__delattr__(self, name)

    def clear(self) -> None:
        """Discard cached legacy fields between isolated tests."""
        for name in tuple(self.__dict__):
            object.__delattr__(self, name)
        get_settings.cache_clear()


# Compatibility only: importing configuration must never validate production env.
settings = _SettingsProxy()
