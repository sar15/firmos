"""Finance actions are durable, hash-bound, enqueue-only HTTP work."""
import json
import pytest
from core.finance_actions import FinanceActionEngine, FinanceActionError, PayloadHashMismatchError, compute_payload_hash


class FakeConnection:
    def __init__(self): self.actions, self.outbox, self.jobs = {}, [], []
    async def __aenter__(self): return self
    async def __aexit__(self, *_): return None

    async def fetchrow(self, query, *args):
        if "INSERT INTO finance_actions" in query:
            action = {"id": args[0], "firm_id": args[1], "client_id": args[2], "provider": args[3],
                      "operation": args[4], "idempotency_key": args[5], "payload": json.loads(args[6]),
                      "payload_hash": args[7], "status": "AWAITING_APPROVAL", "correlation_id": args[13]}
            existing = next((item for item in self.actions.values() if item["firm_id"] == args[1] and item["idempotency_key"] == args[5]), None)
            if existing: return existing
            self.actions[action["id"]] = action; return action
        if query.startswith("SELECT * FROM finance_actions"):
            action = self.actions.get(args[0]); return action if action and action["firm_id"] == args[1] else None
        if "UPDATE finance_actions SET status='APPROVED'" in query:
            action = self.actions.get(args[3])
            if not action or action["firm_id"] != args[4] or action["status"] != "AWAITING_APPROVAL" or action["payload_hash"] != args[1]: return None
            action.update(status="APPROVED", approved_by=args[0], approved_payload_hash=args[1], correlation_id=args[2] or action["correlation_id"])
            return action
        if "UPDATE finance_actions SET status='QUEUED'" in query:
            action = self.actions.get(args[0])
            if not action or action["firm_id"] != args[1] or action["status"] != "APPROVED": return None
            action["status"] = "QUEUED"
            return action
        raise AssertionError(query)

    async def execute(self, query, *args):
        if "INSERT INTO outbox_events" in query: self.outbox.append(args)
        elif "INSERT INTO automation_jobs" in query: self.jobs.append(args)
        else: raise AssertionError(query)


class FakePool:
    def __init__(self): self.connection = FakeConnection()
    def acquire(self): return self.connection


@pytest.mark.asyncio
async def test_payload_hash_binding_and_atomic_enqueue():
    pool, payload = FakePool(), {"vendor": "Acme", "amount_paise": 42000}
    engine = FinanceActionEngine(pool)
    action = await engine.propose_action("firm-1", "client-1", "ZOHO_BOOKS", "zoho.write.bill.create", payload, "key-1")
    expected = compute_payload_hash(payload)
    assert action["status"] == "AWAITING_APPROVAL" and action["payload_hash"] == expected
    with pytest.raises(PayloadHashMismatchError):
        await engine.approve_action(action["id"], "firm-1", "user-1", "0" * 64)
    approved = await engine.approve_action(action["id"], "firm-1", "user-1", expected, "correlation-1")
    assert approved["status"] == "QUEUED"
    assert len(pool.connection.outbox) == len(pool.connection.jobs) == 1
    with pytest.raises(FinanceActionError):
        await engine.approve_action(action["id"], "firm-1", "user-1", expected)


@pytest.mark.asyncio
async def test_api_service_cannot_execute_provider_write():
    engine = FinanceActionEngine(FakePool())
    with pytest.raises(FinanceActionError, match="automation worker"):
        await engine.execute_action("action", "firm")


def test_database_is_required():
    with pytest.raises(ValueError):
        FinanceActionEngine(None)
