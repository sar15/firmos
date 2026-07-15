"""Tenant-bound AES-GCM credential envelopes with rotation metadata."""
import json, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from core.security import _get_key, StoredCredentialError


def seal_credentials(firm_id: str, installation_id: str, values: dict, key_version: str,
                     key: bytes | None = None) -> bytes:
    nonce = os.urandom(12)
    aad = f"{firm_id}:{installation_id}:{key_version}".encode()
    return nonce + AESGCM(key or _get_key()).encrypt(nonce, json.dumps(values, sort_keys=True).encode(), aad)


def open_credentials(firm_id: str, installation_id: str, envelope: bytes, key_version: str,
                     key: bytes | None = None) -> dict:
    try:
        aad = f"{firm_id}:{installation_id}:{key_version}".encode()
        return json.loads(AESGCM(key or _get_key()).decrypt(envelope[:12], envelope[12:], aad))
    except Exception as exc:
        raise StoredCredentialError("Connector credential is unavailable; reconnect the installation") from exc


async def load_credentials(conn, firm_id: str, installation_id: str) -> dict:
    row = await conn.fetchrow(
        """SELECT c.ciphertext,c.key_version FROM connector_credentials c
           JOIN connector_installations i ON i.id=c.installation_id
           WHERE c.installation_id=$1 AND i.firm_id=$2 AND c.revoked_at IS NULL""",
        installation_id, firm_id,
    )
    if not row: raise StoredCredentialError("Connector credential is missing or revoked")
    return open_credentials(firm_id, installation_id, row["ciphertext"], row["key_version"])


async def rotate_credentials(conn, *, firm_id: str, installation_id: str,
                             new_key_version: str, old_key: bytes | None = None,
                             new_key: bytes | None = None) -> None:
    row = await conn.fetchrow(
        """SELECT c.ciphertext,c.key_version FROM connector_credentials c
           JOIN connector_installations i ON i.id=c.installation_id
           WHERE c.installation_id=$1 AND i.firm_id=$2 AND c.revoked_at IS NULL FOR UPDATE""",
        installation_id, firm_id,
    )
    if not row:
        raise StoredCredentialError("Connector credential is missing or revoked")
    values = open_credentials(
        firm_id, installation_id, row["ciphertext"], row["key_version"], old_key,
    )
    envelope = seal_credentials(firm_id, installation_id, values, new_key_version, new_key)
    await conn.execute(
        """UPDATE connector_credentials SET ciphertext=$1,key_version=$2,
           rotated_at=NOW(),updated_at=NOW() WHERE installation_id=$3""",
        envelope, new_key_version, installation_id,
    )


async def revoke_credentials(conn, *, firm_id: str, installation_id: str) -> bool:
    result = await conn.execute(
        """UPDATE connector_credentials c SET revoked_at=NOW(),updated_at=NOW()
           FROM connector_installations i WHERE c.installation_id=i.id
           AND c.installation_id=$1 AND i.firm_id=$2 AND c.revoked_at IS NULL""",
        installation_id, firm_id,
    )
    return result.endswith(" 1")
