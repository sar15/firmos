"""Stable provider-object snapshots and read-back verification records."""
import hashlib, json


def snapshot_hash(values: dict) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def upsert_snapshot(conn, *, firm_id: str, installation_id: str, object_type: str,
                          provider_id: str, values: dict, provider_version: str | None = None,
                          status: str = "ACTIVE", void: bool = False) -> tuple[str, str]:
    digest = snapshot_hash(values)
    prior = await conn.fetchrow(
        """SELECT id,snapshot_hash,void,deleted FROM provider_objects
           WHERE firm_id=$1 AND installation_id=$2 AND object_type=$3 AND provider_id=$4""",
        firm_id, installation_id, object_type, provider_id,
    )
    change = "CREATED" if not prior else (
        "VOIDED" if void and not prior["void"] else
        "RESTORED" if prior["deleted"] else
        "EDITED" if prior["snapshot_hash"] != digest else "UNCHANGED"
    )
    row = await conn.fetchrow(
        """INSERT INTO provider_objects(firm_id,installation_id,object_type,provider_id,
           snapshot_hash,snapshot,provider_version,status,void,last_seen_at)
           VALUES($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,NOW())
           ON CONFLICT(firm_id,installation_id,object_type,provider_id) DO UPDATE SET
           snapshot_hash=EXCLUDED.snapshot_hash,snapshot=EXCLUDED.snapshot,
           provider_version=EXCLUDED.provider_version,
           status=EXCLUDED.status,void=EXCLUDED.void,active=NOT EXCLUDED.void,
           deleted=false,last_seen_at=NOW() RETURNING id""",
        firm_id, installation_id, object_type, provider_id, digest, json.dumps(values),
        provider_version, status, void,
    )
    return str(row["id"]), change


async def mark_disappeared(conn, *, firm_id: str, installation_id: str,
                           object_type: str, seen_provider_ids: list[str]) -> int:
    result = await conn.execute(
        """UPDATE provider_objects SET deleted=true,active=false,status='DISAPPEARED'
           WHERE firm_id=$1 AND installation_id=$2 AND object_type=$3
           AND NOT(provider_id=ANY($4::text[])) AND deleted=false""",
        firm_id, installation_id, object_type, seen_provider_ids,
    )
    return int(result.rsplit(" ", 1)[-1])


async def record_verification(conn, *, firm_id: str, installation_id: str, action_id: str,
                              object_type: str, provider_id: str, values: dict,
                              mismatches: dict, correlation_id: str, provider_version: str | None = None) -> str:
    object_id, _ = await upsert_snapshot(
        conn, firm_id=firm_id, installation_id=installation_id, object_type=object_type,
        provider_id=provider_id, values=values, provider_version=provider_version,
    )
    await conn.execute("UPDATE provider_objects SET last_verified_at=NOW() WHERE id=$1", object_id)
    status = "MISMATCH" if mismatches else "MATCHED"
    row = await conn.fetchrow(
        """INSERT INTO verification_results(firm_id,action_id,provider_object_id,status,verified_fields,mismatches,provider_version,correlation_id)
           VALUES($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7,$8) RETURNING id""",
        firm_id, action_id, object_id, status, json.dumps(values), json.dumps(mismatches), provider_version, correlation_id,
    )
    return str(row["id"])
