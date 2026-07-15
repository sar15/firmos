"""Installation-bound Zoho credentials with PostgreSQL refresh single-flight."""
from datetime import datetime, timedelta, timezone
import json

from connectors.platform.credentials import open_credentials, seal_credentials
from connectors.zoho_books.auth import refresh_access_token
from connectors.zoho_books.client import ZohoClient
from core.config import settings
from core.security import StoredCredentialError


class ZohoCredentialService:
    def __init__(self, pool, installation_id: str):
        self.pool, self.installation_id = pool, str(installation_id)

    async def _row(self, conn, *, lock: bool = False):
        suffix = " FOR UPDATE OF c" if lock else ""
        return await conn.fetchrow(
            """SELECT i.firm_id,i.configuration,i.status,c.ciphertext,c.key_version,
                      c.data_center,c.api_domain,c.scopes,c.expires_at
               FROM connector_installations i JOIN connector_credentials c ON c.installation_id=i.id
               WHERE i.id=$1::uuid AND i.provider='ZOHO_BOOKS' AND c.revoked_at IS NULL""" + suffix,
            self.installation_id,
        )

    async def load(self) -> tuple[object, dict]:
        async with self.pool.acquire() as conn:
            row = await self._row(conn)
        if not row:
            raise StoredCredentialError("Zoho installation is missing or disconnected")
        values = open_credentials(row["firm_id"], self.installation_id, row["ciphertext"], row["key_version"])
        return row, values

    async def access_token(self) -> str:
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", self.installation_id)
            row = await self._row(conn, lock=True)
            if not row:
                raise StoredCredentialError("Zoho installation is missing or disconnected")
            values = open_credentials(row["firm_id"], self.installation_id, row["ciphertext"], row["key_version"])
            now = datetime.now(timezone.utc)
            if row["expires_at"] and row["expires_at"] > now + timedelta(seconds=60):
                return values["access_token"]
            tokens = await refresh_access_token(values["refresh_token"], row["data_center"])
            values["access_token"] = tokens["access_token"]
            envelope = seal_credentials(
                row["firm_id"], self.installation_id, values, settings.credential_key_version,
            )
            await conn.execute(
                """UPDATE connector_credentials SET ciphertext=$1,key_version=$2,
                   api_domain=COALESCE($3,api_domain),expires_at=$4,updated_at=NOW()
                   WHERE installation_id=$5::uuid""",
                envelope, settings.credential_key_version, tokens.get("api_domain"),
                now + timedelta(seconds=int(tokens["expires_in"])), self.installation_id,
            )
            return values["access_token"]

    async def client(self) -> ZohoClient:
        row, values = await self.load()
        configuration = row["configuration"]
        if isinstance(configuration, str):
            configuration = json.loads(configuration)
        organization_id = str(configuration.get("organization_id") or "")
        if not organization_id:
            raise StoredCredentialError("Zoho organization mapping is missing")
        token = await self.access_token()
        return ZohoClient(
            token, None, organization_id, api_domain=row["api_domain"], refresh=self.access_token,
        )


async def save_installation_credentials(
    conn, *, installation_id: str, firm_id: str, values: dict, data_center: str,
    api_domain: str, scopes: list[str], expires_at: datetime,
) -> None:
    envelope = seal_credentials(firm_id, installation_id, values, settings.credential_key_version)
    await conn.execute(
        """INSERT INTO connector_credentials
           (installation_id,ciphertext,data_center,api_domain,scopes,issued_at,expires_at,key_version)
           VALUES($1::uuid,$2,$3,$4,$5::text[],NOW(),$6,$7)
           ON CONFLICT(installation_id) DO UPDATE SET ciphertext=EXCLUDED.ciphertext,
           data_center=EXCLUDED.data_center,api_domain=EXCLUDED.api_domain,scopes=EXCLUDED.scopes,
           issued_at=NOW(),expires_at=EXCLUDED.expires_at,key_version=EXCLUDED.key_version,
           credential_version=connector_credentials.credential_version+1,
           revoked_at=NULL,updated_at=NOW()""",
        installation_id, envelope, data_center, api_domain, scopes, expires_at,
        settings.credential_key_version,
    )
