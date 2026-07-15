"""Separate durable financial worker; API processes never import this module."""
import asyncio
import uuid

from connectors.platform.provider_objects import record_verification
from connectors.platform.registry import ConnectorNotRegistered, registry
from connectors.platform.types import ApprovedAction, ExecutionAttempt, ResultStatus
from connectors.zoho_books.connector import register_zoho_v1
from connectors.zoho_books.sync_worker import run_sync_job
from core.feature_flags import scoped_write_block_reason

MAX_ATTEMPTS = 5
RETRYABLE = {ResultStatus.RATE_LIMITED, ResultStatus.PROVIDER_UNAVAILABLE}


class Worker:
    def __init__(self, pool, worker_id: str | None = None):
        self.pool, self.worker_id = pool, worker_id or str(uuid.uuid4())
        register_zoho_v1(pool)

    async def claim(self) -> dict | None:
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """SELECT j.* FROM automation_jobs j WHERE j.status='QUEUED' AND j.available_at<=NOW()
                   AND NOT EXISTS(SELECT 1 FROM finance_actions a
                     WHERE a.id::text=j.aggregate_id AND a.provider='TALLY_PRIME')
                   AND (j.lease_expires_at IS NULL OR j.lease_expires_at<NOW())
                   ORDER BY j.created_at FOR UPDATE OF j SKIP LOCKED LIMIT 1"""
            )
            if not row:
                return None
            await conn.execute(
                """UPDATE automation_jobs SET status='CLAIMED',lease_owner=$1,
                   lease_expires_at=NOW()+interval '60 seconds',attempt_count=attempt_count+1,
                   updated_at=NOW() WHERE id=$2""", self.worker_id, row["id"],
            )
            await conn.execute(
                "UPDATE finance_actions SET status='CLAIMED' WHERE id=$1 AND status='QUEUED'",
                row["aggregate_id"],
            )
            await conn.execute(
                """INSERT INTO automation_attempts(job_id,attempt_number,status)
                   VALUES($1,$2,'CLAIMED')""", row["id"], row["attempt_count"] + 1,
            )
        claimed = dict(row)
        claimed["attempt_count"] += 1
        return claimed

    async def run_finance_action(self, job: dict) -> None:
        async with self.pool.acquire() as conn:
            action = await conn.fetchrow("SELECT * FROM finance_actions WHERE id=$1", job["aggregate_id"])
            if not action:
                return await self._finish(job, "FAILED", "ACTION_NOT_FOUND")
            await self._heartbeat(conn, action["firm_id"])
            precondition = await self._write_precondition(conn, action)
            if precondition:
                return await self._finish(job, "FAILED", precondition)
            reason = await scoped_write_block_reason(
                conn, action["provider"], firm_id=action["firm_id"], client_id=action["client_id"],
                capability_key=action["operation"],
            )
            if reason:
                return await self._finish(job, "FAILED", reason)
            await conn.execute(
                "UPDATE finance_actions SET status='EXECUTING',attempt_number=attempt_number+1 WHERE id=$1",
                action["id"],
            )
        try:
            connector = registry.create(
                action["provider"], "v1", action["operation"], installation_id=action["installation_id"],
            )
            approved = ApprovedAction(
                str(action["id"]), action["operation"], action["payload"],
                action["payload_hash"], job["correlation_id"],
            )
            result = await connector.execute_write(
                approved, ExecutionAttempt(job["attempt_count"], action["idempotency_key"]),
            )
            if result.status is not ResultStatus.SUCCESS or not result.data:
                return await self._result_failure(job, action, result.status, result.reason_code)
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE finance_actions SET status='PROVIDER_ACCEPTED',external_reference_id=$1 WHERE id=$2",
                    result.data.provider_id, action["id"],
                )
                await conn.execute("UPDATE finance_actions SET status='VERIFYING' WHERE id=$1", action["id"])
            verified = await connector.verify_write(result.data, action["payload"])
            if verified.status is not ResultStatus.SUCCESS:
                if verified.data:
                    async with self.pool.acquire() as conn, conn.transaction():
                        await record_verification(
                            conn, firm_id=action["firm_id"], installation_id=action["installation_id"],
                            action_id=str(action["id"]), object_type=result.data.object_type,
                            provider_id=result.data.provider_id, values=verified.data,
                            mismatches=verified.details.get("mismatches", {}),
                            correlation_id=job["correlation_id"],
                            provider_version=verified.details.get("provider_version"),
                        )
                return await self._finish(job, "NEEDS_REVIEW", "READBACK_MISMATCH")
            async with self.pool.acquire() as conn, conn.transaction():
                verification_id = await record_verification(
                    conn, firm_id=action["firm_id"], installation_id=action["installation_id"],
                    action_id=str(action["id"]), object_type=result.data.object_type,
                    provider_id=result.data.provider_id, values=verified.data or result.data.values, mismatches={},
                    correlation_id=job["correlation_id"],
                    provider_version=verified.details.get("provider_version") or result.data.provider_version,
                )
                from core.purchase_invoices.projection import project_verified_purchase
                if action["operation"] == "zoho.write.purchase_bill.create":
                    await project_verified_purchase(conn, str(action["id"]), verification_id)
                if action["operation"] == "zoho.write.sales_invoice.create":
                    from core.sales_invoices.projection import project_verified_sale
                    await project_verified_sale(conn, str(action["id"]), verification_id)
                await conn.execute("UPDATE finance_actions SET status='SUCCEEDED' WHERE id=$1", action["id"])
                await self._complete_attempt(conn, job, "SUCCEEDED", None)
        except ConnectorNotRegistered:
            await self._finish(job, "FAILED", "CONNECTOR_IMPLEMENTATION_UNAVAILABLE")
        except Exception:
            await self._finish(job, "RETRY_SCHEDULED", "UNEXPECTED_CONNECTOR_FAILURE")

    async def _write_precondition(self, conn, action) -> str | None:
        installation = await conn.fetchval(
            """SELECT 1 FROM connector_installations i JOIN connector_credentials c
               ON c.installation_id=i.id AND c.revoked_at IS NULL
               WHERE i.id=$1 AND i.firm_id=$2 AND i.client_id=$3 AND i.status='AVAILABLE'
               AND i.provider='ZOHO_BOOKS'
               AND $4=ANY(c.scopes)""",
            action["installation_id"], action["firm_id"], action["client_id"],
            "ZohoBooks.invoices.CREATE" if action["operation"] == "zoho.write.sales_invoice.create" else "ZohoBooks.bills.CREATE",
        )
        if not installation:
            return "INSTALLATION_UNAVAILABLE"
        certified = await conn.fetchval(
            """SELECT 1 FROM capability_certifications WHERE firm_id=$1 AND capability_key=$2
               AND provider=$3 AND provider_version=$4 AND installation_id=$5
               AND certification_level=5""",
            action["firm_id"], action["operation"], action["provider"],
            "v3" if action["provider"] == "ZOHO_BOOKS" else "unknown",
            action["installation_id"],
        )
        if not certified:
            return "CERTIFICATION_L5_REQUIRED"
        mapping_types = set(await conn.fetchval(
            """SELECT COALESCE(array_agg(DISTINCT mapping_type),'{}') FROM connector_mappings
               WHERE installation_id=$1 AND active AND approved_at IS NOT NULL""",
            action["installation_id"],
        ) or [])
        if action["provider"] == "ZOHO_BOOKS" and not {"organization", "contact", "ledger", "tax"}.issubset(mapping_types):
            return "MAPPINGS_REQUIRED"
        prior = await conn.fetchval(
            "SELECT 1 FROM verification_results WHERE action_id=$1 LIMIT 1", action["id"],
        )
        return "ACTION_ALREADY_REACHED_PROVIDER" if prior else None

    async def _result_failure(self, job, action, status, code):
        if status is ResultStatus.AUTH_EXPIRED:
            return await self._finish(job, "AUTH_EXPIRED", code or status.value)
        state = "RETRY_SCHEDULED" if status in RETRYABLE else "NEEDS_REVIEW"
        await self._finish(job, state, code or status.value)

    async def _finish(self, job, action_status, code):
        exhausted = action_status == "RETRY_SCHEDULED" and job["attempt_count"] >= MAX_ATTEMPTS
        if action_status == "RETRY_SCHEDULED" and job["attempt_count"] >= MAX_ATTEMPTS:
            action_status = "DEAD_LETTER"
        async with self.pool.acquire() as conn, conn.transaction():
            if exhausted:
                await conn.execute(
                    "UPDATE finance_actions SET status='FAILED' WHERE id=$1", job["aggregate_id"],
                )
            await conn.execute(
                "UPDATE finance_actions SET status=$1 WHERE id=$2", action_status, job["aggregate_id"],
            )
            job_status = action_status
            delay = min(300, 2 ** job["attempt_count"])
            await conn.execute(
                """UPDATE automation_jobs SET status=$1,lease_owner=NULL,lease_expires_at=NULL,
                   available_at=CASE WHEN $1='RETRY_SCHEDULED' THEN NOW()+($3*interval '1 second') ELSE available_at END,
                   updated_at=NOW() WHERE id=$2""", job_status, job["id"], delay,
            )
            await self._complete_attempt(conn, job, job_status, code)
            if job_status == "DEAD_LETTER":
                await conn.execute(
                    """INSERT INTO dead_letters(job_id,reason_code,safe_message) VALUES($1,$2,$3)
                       ON CONFLICT(job_id) DO NOTHING""", job["id"], code, "Connector execution needs operator review",
                )

    async def _complete_attempt(self, conn, job, status, code):
        await conn.execute(
            """UPDATE automation_attempts SET status=$1,error_code=$2,finished_at=NOW()
               WHERE job_id=$3 AND attempt_number=$4""", status, code, job["id"], job["attempt_count"],
        )
        if status == "SUCCEEDED":
            await conn.execute(
                "UPDATE automation_jobs SET status='SUCCEEDED',lease_owner=NULL,lease_expires_at=NULL,updated_at=NOW() WHERE id=$1",
                job["id"],
            )

    async def _heartbeat(self, conn, firm_id):
        await conn.execute(
            """INSERT INTO worker_heartbeats(firm_id,worker_kind,worker_id,seen_at)
               VALUES($1,'FINANCE_ACTION',$2,NOW()) ON CONFLICT(firm_id,worker_kind,worker_id)
               DO UPDATE SET seen_at=NOW()""", firm_id, self.worker_id,
        )

    async def run_once(self) -> bool:
        job = await self.claim()
        if not job:
            return await run_sync_job(self.pool, self.worker_id)
        if job["kind"] == "FINANCE_ACTION":
            await self.run_finance_action(job)
        return True


async def serve(pool):
    worker = Worker(pool)
    while True:
        if not await worker.run_once():
            await asyncio.sleep(1)


async def main():
    from core.database import Database
    await Database.connect()
    try:
        await serve(Database.pool)
    finally:
        await Database.close()


if __name__ == "__main__":
    asyncio.run(main())
