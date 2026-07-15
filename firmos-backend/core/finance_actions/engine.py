"""Persistent finance-action proposal and approval service."""
import hashlib, json, uuid
from typing import Any


class FinanceActionError(Exception): pass
class PayloadHashMismatchError(FinanceActionError): pass


def compute_payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class FinanceActionEngine:
    """HTTP-safe service: it can propose and enqueue, never execute providers."""
    def __init__(self, db_pool: Any):
        if db_pool is None: raise ValueError("Finance actions require a PostgreSQL repository")
        self.db_pool = db_pool

    async def get_action(self, action_id: str, firm_id: str) -> dict | None:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM finance_actions WHERE id=$1 AND firm_id=$2", action_id, firm_id)
        return dict(row) if row else None

    async def propose_action(self, firm_id: str, client_id: str, provider: str, operation: str,
                             payload: dict, idempotency_key: str, proposed_by: str = "agent",
                             risk_level: str = "LOW", installation_id: str | None = None,
                             source_identity: str | None = None, source_version: str = "1",
                             correlation_id: str | None = None) -> dict:
        payload_hash, action_id = compute_payload_hash(payload), str(uuid.uuid4())
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO finance_actions(id,firm_id,client_id,provider,operation,idempotency_key,payload,
                   payload_hash,status,risk_level,proposed_by,installation_id,source_identity,source_version,correlation_id)
                   VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8,'AWAITING_APPROVAL',$9,$10,$11,$12,$13,$14)
                   ON CONFLICT(firm_id,idempotency_key) DO UPDATE SET updated_at=NOW() RETURNING *""",
                action_id, firm_id, client_id, provider, operation, idempotency_key, json.dumps(payload),
                payload_hash, risk_level, proposed_by, installation_id, source_identity, source_version, correlation_id,
            )
        return dict(row)

    async def approve_action(self, action_id: str, firm_id: str, approved_by: str,
                             approved_payload_hash: str, correlation_id: str = "") -> dict:
        action = await self.get_action(action_id, firm_id)
        if not action: raise FinanceActionError("Finance action was not found")
        if action["payload_hash"] != approved_payload_hash:
            raise PayloadHashMismatchError("Approved payload does not match the reviewed proposal")
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """UPDATE finance_actions SET status='APPROVED',approved_by=$1,approved_payload_hash=$2,
                   approved_at=NOW(),correlation_id=COALESCE(NULLIF($3,''),correlation_id),updated_at=NOW()
                   WHERE id=$4 AND firm_id=$5 AND status='AWAITING_APPROVAL' AND payload_hash=$2 RETURNING *""",
                approved_by, approved_payload_hash, correlation_id, action_id, firm_id,
            )
            if not row: raise FinanceActionError("Finance action is no longer awaiting approval")
            row = await conn.fetchrow(
                "UPDATE finance_actions SET status='QUEUED',updated_at=NOW() WHERE id=$1 AND firm_id=$2 RETURNING *",
                action_id, firm_id,
            )
            event = {"action_id": action_id}
            await conn.execute(
                """INSERT INTO outbox_events(firm_id,topic,aggregate_id,payload,correlation_id)
                   VALUES($1,'finance_action.queued',$2,$3::jsonb,$4)""",
                firm_id, action_id, json.dumps(event), row["correlation_id"] or correlation_id,
            )
            await conn.execute(
                """INSERT INTO automation_jobs(firm_id,kind,aggregate_id,payload,correlation_id)
                   VALUES($1,'FINANCE_ACTION',$2,$3::jsonb,$4) ON CONFLICT(kind,aggregate_id) DO NOTHING""",
                firm_id, action_id, json.dumps(event), row["correlation_id"] or correlation_id,
            )
        return dict(row)

    async def cancel_action(self, action_id: str, firm_id: str) -> dict:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """UPDATE finance_actions SET status='CANCELLED',updated_at=NOW()
                   WHERE id=$1 AND firm_id=$2 AND status IN ('AWAITING_APPROVAL','QUEUED','RETRY_SCHEDULED')
                   RETURNING *""", action_id, firm_id,
            )
            if not row:
                raise FinanceActionError("Only an unclaimed action can be cancelled")
            await conn.execute(
                """UPDATE automation_jobs SET status='CANCELLED',updated_at=NOW()
                   WHERE kind='FINANCE_ACTION' AND aggregate_id=$1 AND status='QUEUED'""", action_id,
            )
            await conn.execute(
                "UPDATE accounting_drafts SET status='CANCELLED',updated_at=NOW() WHERE action_id=$1", action_id,
            )
        return dict(row)

    async def execute_action(self, *_args, **_kwargs):
        raise FinanceActionError("Provider execution is restricted to the automation worker")
