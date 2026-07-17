"""Persisted OAuth refresh for legacy ``connections``-table readers."""

from connectors.zoho_books.auth import refresh_access_token
from connectors.zoho_books.client import ZohoClient
from core.security import StoredCredentialError, decrypt_token, encrypt_token


async def legacy_zoho_client(pool, firm_id: str) -> ZohoClient | None:
    """Return a client whose 401 refresh is saved for the next request too."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT access_token_enc,refresh_token_enc,external_account_id FROM connections
               WHERE firm_id=$1 AND connector_id='c1'""",
            firm_id,
        )
    if not row or not row["access_token_enc"] or not row["refresh_token_enc"] or not row["external_account_id"]:
        return None
    access_token = decrypt_token(row["access_token_enc"])

    async def refresh() -> str:
        async with pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                """SELECT access_token_enc,refresh_token_enc FROM connections
                   WHERE firm_id=$1 AND connector_id='c1' FOR UPDATE""",
                firm_id,
            )
            if not current or not current["access_token_enc"] or not current["refresh_token_enc"]:
                raise StoredCredentialError("Zoho Books is disconnected; reconnect it to continue")
            stored_access = decrypt_token(current["access_token_enc"])
            if stored_access != access_token:
                return stored_access
            tokens = await refresh_access_token(decrypt_token(current["refresh_token_enc"]))
            await conn.execute(
                """UPDATE connections SET access_token_enc=$1,updated_at=NOW()
                   WHERE firm_id=$2 AND connector_id='c1'""",
                encrypt_token(tokens["access_token"]), firm_id,
            )
            return tokens["access_token"]

    return ZohoClient(access_token, None, str(row["external_account_id"]), refresh=refresh)
