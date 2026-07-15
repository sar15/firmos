"""AES-256-GCM token encryption + JWT decode."""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from jose import jwt, JWTError

from core.config import get_settings, settings


class StoredCredentialError(ValueError):
    """A connector credential cannot be read with the current encryption key."""


def _get_key() -> bytes:
    """Decode the base64 TOKEN_ENC_KEY into raw 32 bytes."""
    raw = base64.b64decode(settings.token_enc_key)
    if len(raw) != 32:
        raise ValueError(f"TOKEN_ENC_KEY must decode to 32 bytes, got {len(raw)}")
    return raw


def encrypt_token(plaintext: str) -> bytes:
    """Encrypt a token string -> nonce || ciphertext (bytes). Store as bytea."""
    key = _get_key()
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ciphertext


def decrypt_token(data: bytes) -> str:
    """Decrypt nonce || ciphertext -> original token string."""
    try:
        key = _get_key()
        nonce, ciphertext = data[:12], data[12:]
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except (InvalidTag, TypeError, UnicodeDecodeError, ValueError) as exc:
        raise StoredCredentialError("Stored connector credentials cannot be decrypted; reconnect the connector") from exc


def decode_supabase_jwt(token: str) -> dict:
    """Verify signature, issuer, audience, expiry, and subject."""
    config = get_settings()
    issuer = config.supabase_jwt_issuer or f"{config.supabase_url.rstrip('/')}/auth/v1"
    if not config.supabase_url and not config.supabase_jwt_issuer:
        raise ValueError("JWT issuer is not configured")
    try:
        payload = jwt.decode(
            token,
            config.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=config.supabase_jwt_audience,
            issuer=issuer,
            options={"require_exp": True, "require_sub": True},
        )
    except JWTError as exc:
        raise ValueError(f"Invalid JWT: {exc}") from exc
    return payload
