"""Live, rollback-only proof for signed Tally devices and cross-firm RLS."""
import asyncio
import uuid

import asyncpg

from core.config import settings


async def verify() -> None:
    conn = await asyncpg.connect(settings.database_url)
    transaction = conn.transaction()
    await transaction.start()
    try:
        enabled = await conn.fetchval(
            "SELECT relrowsecurity FROM pg_class WHERE oid='tally_devices'::regclass",
        )
        if not enabled:
            raise AssertionError("tally_devices RLS is disabled")
        policies = set(await conn.fetchval(
            "SELECT array_agg(policyname) FROM pg_policies WHERE tablename='tally_devices'",
        ) or [])
        if "tally_devices_firm" not in policies:
            raise AssertionError("firm isolation policy is missing")
        direct_access = await conn.fetchval(
            "SELECT has_table_privilege('authenticated','tally_devices','SELECT')",
        )
        if direct_access:
            raise AssertionError("authenticated role has direct signed-device table access")

        nonce_rls = await conn.fetchval(
            "SELECT relrowsecurity FROM pg_class WHERE oid='tally_device_nonces'::regclass",
        )
        if not nonce_rls:
            raise AssertionError("tally_device_nonces RLS is disabled")
        nonce_policies = set(await conn.fetchval(
            "SELECT array_agg(policyname) FROM pg_policies "
            "WHERE tablename='tally_device_nonces'",
        ) or [])
        if "tally_device_nonces_firm" not in nonce_policies:
            raise AssertionError("nonce firm-isolation policy is missing")

        firm_a, firm_b = f"rls-a-{uuid.uuid4()}", f"rls-b-{uuid.uuid4()}"
        install_a, install_b = uuid.uuid4(), uuid.uuid4()
        creator = uuid.uuid4()
        for firm, installation in ((firm_a, install_a), (firm_b, install_b)):
            await conn.execute(
                """INSERT INTO connector_installations(id,firm_id,provider,environment,display_name,
                   status,implementation_version,created_by) VALUES($1,$2,'TALLY_PRIME','local',
                   'RLS proof','AVAILABLE','v1',$3)""", installation, firm, creator,
            )
            device_id = await conn.fetchval(
                """INSERT INTO tally_devices(firm_id,installation_id,public_key,display_name,
                   company_name,company_guid) VALUES($1,$2,$3,$4,'RLS proof',$5)
                   RETURNING id""",
                firm, installation, "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                firm, uuid.uuid4().hex,
            )
            await conn.execute(
                "INSERT INTO tally_device_nonces(device_id,nonce,requested_at) VALUES($1,$2,$3)",
                device_id, uuid.uuid4().hex, 1,
            )
        duplicate = await conn.fetchval(
            "INSERT INTO tally_device_nonces(device_id,nonce,requested_at) "
            "SELECT device_id,nonce,requested_at FROM tally_device_nonces LIMIT 1 "
            "ON CONFLICT DO NOTHING RETURNING nonce",
        )
        if duplicate is not None:
            raise AssertionError("duplicate device nonce was accepted")

        await conn.execute("GRANT SELECT ON tally_devices TO authenticated")
        await conn.execute("SET LOCAL ROLE authenticated")
        await conn.execute("SELECT set_config('request.jwt.claim.firm_id',$1,true)", firm_a)
        visible = list(await conn.fetchval(
            "SELECT array_agg(display_name ORDER BY display_name) FROM tally_devices",
        ) or [])
        if visible != [firm_a]:
            raise AssertionError(f"cross-firm RLS failed: {visible}")
        visible_nonces = await conn.fetchval("SELECT count(*) FROM tally_device_nonces")
        if visible_nonces != 1:
            raise AssertionError(f"nonce cross-firm RLS failed: {visible_nonces}")
        print("Tally database proof passed: signed schema, nonce replay/RLS, device RLS")
    finally:
        await transaction.rollback()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(verify())
