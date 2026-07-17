"""One-time pairing and dedicated device authentication for the Tally agent."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from api.deps import FirmContext, get_current_firm, get_db
from connectors.tally.versions import agent_version_supported
from core.device_signing import validate_public_key, verify_device_signature

router = APIRouter()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class DeviceContext:
    id: str
    firm_id: str
    client_id: str
    installation_id: str
    company_name: str
    company_guid: str


class PairingCodeRequest(BaseModel):
    client_id: str


class PairRequest(BaseModel):
    pairing_code: str = Field(min_length=20, max_length=200)
    device_name: str = Field(min_length=2, max_length=255)
    company_name: str = Field(min_length=1, max_length=255)
    company_guid: str = Field(min_length=1, max_length=255)
    agent_version: str = Field(max_length=50)
    tally_version: str = Field(default="", max_length=100)
    license_mode: str = Field(default="", max_length=50)
    protocols: list[str] = Field(default_factory=lambda: ["XML"], max_length=4)
    public_key: str = Field(min_length=40, max_length=100)


@router.get("/devices")
async def list_devices(
    client_id: str | None = None, firm: FirmContext=Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    """Return device health without ever exposing token digests."""
    firm.require("connector.manage")
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT d.id,i.client_id,d.display_name,d.company_name,d.company_guid,d.status,
               d.agent_version,d.tally_version,d.license_mode,d.protocols,d.last_seen_at,
               (d.status='ACTIVE' AND d.last_seen_at>NOW()-interval '15 minutes') AS healthy
               FROM tally_devices d JOIN connector_installations i ON i.id=d.installation_id
               WHERE d.firm_id=$1 AND ($2::text IS NULL OR i.client_id=$2)
               ORDER BY d.created_at DESC""", firm.firm_id, client_id,
        )
    return {"devices": [dict(row) for row in rows]}


async def require_device(
    request: Request, db_pool=Depends(get_db),
    device_id: str | None=Header(default=None, alias="X-FirmOS-Device", max_length=36),
    firm_id: str | None=Header(default=None, alias="X-FirmOS-Firm", max_length=255),
    timestamp: str | None=Header(default=None, alias="X-FirmOS-Timestamp", max_length=20),
    nonce: str | None=Header(default=None, alias="X-FirmOS-Nonce", max_length=100),
    claimed_digest: str | None=Header(default=None, alias="X-FirmOS-Body-SHA256", max_length=64),
    signature: str | None=Header(default=None, alias="X-FirmOS-Signature", max_length=100),
) -> DeviceContext:
    headers = (device_id, firm_id, timestamp, nonce, claimed_digest, signature)
    if not db_pool or not all(headers):
        raise HTTPException(status_code=401, detail={"code": "DEVICE_SIGNATURE_REQUIRED"})
    try:
        device_id = str(uuid.UUID(device_id))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail={"code": "DEVICE_ID_INVALID"}) from exc
    async with db_pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow(
            """SELECT d.id,d.firm_id,i.client_id,d.installation_id,d.company_name,d.company_guid,
               d.public_key,d.agent_version
               FROM tally_devices d JOIN connector_installations i ON i.id=d.installation_id
               WHERE d.id=$1::uuid AND d.status='ACTIVE' AND i.status='AVAILABLE'""", device_id,
        )
        if not row or row["firm_id"] != firm_id:
            raise HTTPException(status_code=401, detail={"code": "DEVICE_BINDING_INVALID"})
        if not agent_version_supported(str(row["agent_version"] or "")):
            raise HTTPException(status_code=426, detail={"code": "AGENT_UPDATE_REQUIRED"})
        try:
            verify_device_signature(
                public_key=row["public_key"], signature=signature, method=request.method,
                path=request.url.path, timestamp=timestamp, nonce=nonce,
                claimed_digest=claimed_digest, body=await request.body(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=401, detail={"code": str(exc)}) from exc
        # Nonces only protect the short signed-request window. Pruning here is
        # index-backed and keeps the replay table bounded without a scheduler.
        await conn.execute("DELETE FROM tally_device_nonces WHERE received_at < NOW() - interval '10 minutes'")
        inserted = await conn.fetchval(
            """INSERT INTO tally_device_nonces(device_id,nonce,requested_at)
               VALUES($1::uuid,$2,$3::bigint) ON CONFLICT DO NOTHING RETURNING nonce""",
            device_id, nonce, timestamp,
        )
        if not inserted:
            raise HTTPException(status_code=409, detail={"code": "DEVICE_NONCE_REPLAY"})
        return DeviceContext(*(str(row[key]) for key in (
            "id", "firm_id", "client_id", "installation_id", "company_name", "company_guid",
        )))


@router.post("/disconnect")
async def disconnect_device(
    device: DeviceContext=Depends(require_device), db_pool=Depends(get_db),
):
    async with db_pool.acquire() as conn, conn.transaction():
        await conn.execute("UPDATE tally_devices SET status='REVOKED' WHERE id=$1::uuid", device.id)
        await conn.execute(
            """UPDATE connector_installations SET status='DISCONNECTED',updated_at=NOW()
               WHERE id=$1::uuid""", device.installation_id,
        )
    return {"status": "DISCONNECTED"}


@router.post("/pairing-code")
async def create_pairing_code(
    request: PairingCodeRequest, firm: FirmContext=Depends(get_current_firm), db_pool=Depends(get_db),
):
    firm.require("connector.manage")
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    code, installation_id = secrets.token_urlsafe(24), str(uuid.uuid4())
    async with db_pool.acquire() as conn, conn.transaction():
        client = await conn.fetchval(
            "SELECT id FROM clients WHERE id=$1 AND firm_id=$2", request.client_id, firm.firm_id,
        )
        if not client:
            raise HTTPException(status_code=404, detail="FirmOS client not found")
        installation = await conn.fetchrow(
            """INSERT INTO connector_installations(id,firm_id,client_id,provider,environment,
               display_name,status,implementation_version,created_by)
               VALUES($1::uuid,$2,$3,'TALLY_PRIME','production','TallyPrime',
               'CONFIGURATION_REQUIRED','v1',$4::uuid)
               ON CONFLICT(firm_id,client_id,provider,environment) DO UPDATE SET updated_at=NOW()
               RETURNING id""",
            installation_id, firm.firm_id, request.client_id, firm.user_id,
        )
        installation_id = str(installation["id"])
        await conn.execute(
            """INSERT INTO tally_pairing_codes(firm_id,user_id,client_id,installation_id,
               code_digest,expires_at) VALUES($1,$2,$3,$4::uuid,$5,$6)""",
            firm.firm_id, firm.user_id, request.client_id, installation_id, digest(code),
            datetime.now(timezone.utc) + timedelta(minutes=15),
        )
    return {"pairing_code": code, "expires_in_seconds": 900, "installation_id": installation_id}


@router.post("/pair")
async def pair_device(request: PairRequest, db_pool=Depends(get_db)):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    try:
        validate_public_key(request.public_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": str(exc)}) from exc
    async with db_pool.acquire() as conn, conn.transaction():
        attempt = await conn.fetchrow(
            """SELECT * FROM tally_pairing_codes WHERE code_digest=$1 AND consumed_at IS NULL
               AND expires_at>NOW() FOR UPDATE""", digest(request.pairing_code),
        )
        if not attempt:
            raise HTTPException(status_code=400, detail="Pairing code is invalid, expired, or already used")
        await conn.execute(
            "UPDATE tally_devices SET status='REVOKED' WHERE installation_id=$1", attempt["installation_id"],
        )
        device = await conn.fetchrow(
            """INSERT INTO tally_devices(firm_id,installation_id,public_key,display_name,
               company_name,company_guid,agent_version,tally_version,license_mode,protocols,last_seen_at)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::text[],NOW()) RETURNING id""",
            attempt["firm_id"], attempt["installation_id"], request.public_key, request.device_name,
            request.company_name, request.company_guid, request.agent_version,
            request.tally_version, request.license_mode, sorted(set(request.protocols) | {"XML"}),
        )
        configuration = json.dumps({
            "device_id": str(device["id"]), "company_name": request.company_name,
            "company_guid": request.company_guid, "protocols": sorted(set(request.protocols) | {"XML"}),
        })
        await conn.execute(
            """UPDATE connector_installations SET status='AVAILABLE',display_name=$1,
               configuration=$2::jsonb,last_probe_at=NOW(),last_success_at=NOW(),updated_at=NOW()
               WHERE id=$3""", request.company_name, configuration, attempt["installation_id"],
        )
        await conn.execute(
            """INSERT INTO connector_mappings(firm_id,client_id,installation_id,mapping_type,
               internal_id,provider_id,normalized_name,source,confidence,approved_by,approved_at)
               VALUES($1,$2,$3,'company',$2,$4,$5,'MANUAL',1,$6::uuid,NOW())
               ON CONFLICT(installation_id,mapping_type,internal_id) WHERE active DO UPDATE SET
               provider_id=EXCLUDED.provider_id,normalized_name=EXCLUDED.normalized_name,
               approved_by=EXCLUDED.approved_by,approved_at=NOW()""",
            attempt["firm_id"], attempt["client_id"], attempt["installation_id"],
            request.company_guid, request.company_name, attempt["user_id"],
        )
        await conn.execute(
            "UPDATE tally_pairing_codes SET consumed_at=NOW() WHERE id=$1", attempt["id"],
        )
    return {"device_id": str(device["id"]), "firm_id": attempt["firm_id"], "status": "PAIRED"}
