"""Ed25519 request verification shared by local-device endpoints."""
from base64 import b64decode
from datetime import datetime, timezone
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


MAX_CLOCK_SKEW_SECONDS = 300


def body_digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def signing_message(method: str, path: str, timestamp: str, nonce: str, digest: str) -> bytes:
    return "\n".join((method.upper(), path, timestamp, nonce, digest)).encode()


def validate_public_key(value: str) -> None:
    try:
        Ed25519PublicKey.from_public_bytes(b64decode(value, validate=True))
    except (ValueError, TypeError) as exc:
        raise ValueError("DEVICE_PUBLIC_KEY_INVALID") from exc


def verify_device_signature(
    *, public_key: str, signature: str, method: str, path: str,
    timestamp: str, nonce: str, claimed_digest: str, body: bytes,
    now: datetime | None = None,
) -> None:
    """Raise ValueError for stale, tampered, or malformed signed requests."""
    try:
        try:
            requested_at = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
        except (ValueError, OverflowError) as exc:
            raise ValueError("DEVICE_TIMESTAMP_INVALID") from exc
        current = now or datetime.now(timezone.utc)
        if abs((current - requested_at).total_seconds()) > MAX_CLOCK_SKEW_SECONDS:
            raise ValueError("DEVICE_TIMESTAMP_EXPIRED")
        actual_digest = body_digest(body)
        if claimed_digest != actual_digest:
            raise ValueError("DEVICE_BODY_TAMPERED")
        key_bytes = b64decode(public_key, validate=True)
        signature_bytes = b64decode(signature, validate=True)
        Ed25519PublicKey.from_public_bytes(key_bytes).verify(
            signature_bytes,
            signing_message(method, path, timestamp, nonce, actual_digest),
        )
    except ValueError:
        raise
    except (InvalidSignature, TypeError) as exc:
        raise ValueError("DEVICE_SIGNATURE_INVALID") from exc
