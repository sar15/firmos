"""Health and complete snapshot ingestion for the supported Tally desktop agent."""
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_db
from api.routes.tally_agent_auth import DeviceContext, require_device
from connectors.tally.ingest import ingest_snapshot
from connectors.tally.ingest import voucher_total

router = APIRouter()


class Heartbeat(BaseModel):
    agent_version: str = Field(max_length=50)
    tally_version: str = Field(default="", max_length=100)
    license_mode: str = Field(default="", max_length=50)
    protocols: list[str] = Field(default_factory=lambda: ["XML"], max_length=4)
    last_read_at: int | None = Field(default=None, ge=0)
    last_write_at: int | None = Field(default=None, ge=0)
    local_queue_depth: int = Field(default=0, ge=0)
    disk_available_bytes: int | None = Field(default=None, ge=0)
    last_error_code: str = Field(default="", max_length=100)


class WriteAccess(BaseModel):
    enabled: bool


class Ledger(BaseModel):
    guid: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    parent_group: str = Field(default="", max_length=255)
    opening_paise: int = 0
    closing_paise: int = 0
    is_revenue: bool = False
    active: bool = True
    gstin: str = Field(default="", max_length=50)
    tax_type: str = Field(default="", max_length=100)


class Entry(BaseModel):
    ledger_name: str = Field(min_length=1, max_length=255)
    amount_paise: int


class GstDetail(BaseModel):
    ledger_name: str = Field(min_length=1, max_length=255)
    tax_type: str = Field(min_length=1, max_length=50)
    amount_paise: int


class Voucher(BaseModel):
    guid: str = Field(min_length=1, max_length=255)
    remote_id: str = Field(default="", max_length=255)
    voucher_number: str = Field(default="", max_length=100)
    date: str = Field(pattern=r"^\d{8}$")
    voucher_type: str = Field(min_length=1, max_length=100)
    party_name: str = Field(default="", max_length=255)
    narration: str = Field(default="", max_length=4000)
    reference: str = Field(default="", max_length=255)
    entries: list[Entry] = Field(default_factory=list, max_length=500)
    altered: bool = False
    cancelled: bool = False
    master_id: str = Field(default="", max_length=100)
    alteration_id: str = Field(default="", max_length=100)
    status: str = Field(default="ACTIVE", pattern="^(ACTIVE|ALTERED|CANCELLED)$")
    gst_details: list[GstDetail] = Field(default_factory=list, max_length=20)


class Period(BaseModel):
    from_date: str = Field(pattern=r"^\d{8}$")
    to_date: str = Field(pattern=r"^\d{8}$")


class Snapshot(BaseModel):
    company_guid: str = Field(min_length=1, max_length=255)
    period: Period
    completeness: str = Field(pattern="^(COMPLETE|PARTIAL)$")
    ledgers: list[Ledger] = Field(default_factory=list, max_length=20000)
    vouchers: list[Voucher] = Field(default_factory=list, max_length=20000)


@router.post("/heartbeat")
async def heartbeat(
    body: Heartbeat, device: DeviceContext=Depends(require_device), db_pool=Depends(get_db),
):
    protocols = sorted(set(body.protocols) | {"XML"})
    async with db_pool.acquire() as conn:
        await conn.execute(
            """UPDATE tally_devices SET agent_version=$1,tally_version=$2,license_mode=$3,
               protocols=$4::text[],last_seen_at=NOW(),status='ACTIVE',
               last_read_at=to_timestamp($5::double precision),
               last_write_at=to_timestamp($6::double precision),
               local_queue_depth=$7,disk_available_bytes=$8,last_error_code=NULLIF($9,'')
               WHERE id=$10::uuid""",
            body.agent_version, body.tally_version, body.license_mode, protocols,
            body.last_read_at, body.last_write_at, body.local_queue_depth,
            body.disk_available_bytes, body.last_error_code, device.id,
        )
        await conn.execute(
            """UPDATE connector_installations SET last_probe_at=NOW(),last_success_at=NOW(),
               status='AVAILABLE',updated_at=NOW() WHERE id=$1::uuid""", device.installation_id,
        )
    return {"status": "HEALTHY", "poll_seconds": 60, "write_scope": ["purchase_voucher.create"]}


@router.post("/write-access")
async def set_write_access(
    body: WriteAccess, device: DeviceContext=Depends(require_device), db_pool=Depends(get_db),
):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE tally_devices SET write_enabled=$1 WHERE id=$2::uuid", body.enabled, device.id,
        )
    return {"write_enabled": body.enabled}


@router.post("/snapshot")
async def push_snapshot(
    body: Snapshot, device: DeviceContext=Depends(require_device), db_pool=Depends(get_db),
    idempotency_key: str=Header(alias="X-Idempotency-Key", min_length=8, max_length=255),
):
    if body.company_guid != device.company_guid:
        raise HTTPException(status_code=409, detail="Snapshot company does not match paired company")
    payload = body.model_dump()
    payload_hash = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    total_paise = sum(voucher_total(item.get("entries", [])) for item in payload["vouchers"])
    async with db_pool.acquire() as conn, conn.transaction():
        prior = await conn.fetchrow(
            """SELECT ledgers_count,vouchers_count,payload_hash FROM tally_sync_logs
               WHERE firm_id=$1 AND idempotency_key=$2""",
            device.firm_id, idempotency_key,
        )
        if prior:
            if prior["payload_hash"] and prior["payload_hash"] != payload_hash:
                raise HTTPException(status_code=409, detail="Sync key payload hash mismatch")
            return {"status": "DUPLICATE", "ledgers": prior["ledgers_count"], "vouchers": prior["vouchers_count"]}
        ledgers, vouchers = await ingest_snapshot(conn, device, payload)
        await conn.execute(
            """INSERT INTO tally_sync_logs(firm_id,client_id,installation_id,company_name,
               company_guid,idempotency_key,ledgers_count,vouchers_count,status,completeness,
               payload_hash,total_paise)
               VALUES($1,$2,$3::uuid,$4,$5,$6,$7,$8,'SUCCESS',$9,$10,$11)""",
            device.firm_id, device.client_id, device.installation_id, device.company_name,
            device.company_guid, idempotency_key, ledgers, vouchers, body.completeness,
            payload_hash, total_paise,
        )
        await conn.execute(
            """INSERT INTO connector_sync_jobs(firm_id,installation_id,capability_key,client_id,
               period,status,completeness,expected_count,processed_count,correlation_id,
               started_at,finished_at,expected_total_paise,processed_total_paise)
               VALUES($1,$2::uuid,'tally.read.vouchers',$3,$4,'SUCCEEDED',$5,$6,$6,$7,NOW(),NOW(),$8,$8)""",
            device.firm_id, device.installation_id, device.client_id,
            f"{body.period.from_date}:{body.period.to_date}", body.completeness,
            ledgers + vouchers, str(uuid.uuid4()), total_paise,
        )
        await conn.execute(
            "UPDATE connector_installations SET last_success_at=NOW(),last_probe_at=NOW() WHERE id=$1::uuid",
            device.installation_id,
        )
    return {"status": "SYNCED", "ledgers": ledgers, "vouchers": vouchers}
