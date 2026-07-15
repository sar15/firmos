"""Deterministic logical-work idempotency keys."""
import hashlib


def idempotency_key(*, firm_id: str, client_id: str, installation_id: str,
                    operation: str, source_identity: str, source_version: str,
                    approved_payload_hash: str) -> str:
    parts = (firm_id, client_id, installation_id, operation, source_identity, source_version, approved_payload_hash)
    if not all(parts): raise ValueError("Every idempotency key component is required")
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
