"""Reusable reference connector and behavioral contract assertions."""
from connectors.platform.base import Connector
from connectors.platform.types import *


class ReferenceConnector(Connector):
    def __init__(self, scenario: str = "success", **_): self.scenario, self.seen = scenario, set()
    async def probe(self): return ConnectorResult(ResultStatus.AUTH_EXPIRED if self.scenario == "auth_expiry" else ResultStatus.SUCCESS, {})
    async def get_capabilities(self): return ConnectorResult(ResultStatus.SUCCESS, ["reference.write"])
    async def list_masters(self, resource, cursor): return self._page(resource, cursor)
    async def list_transactions(self, resource, scope, cursor): return self._page(resource, cursor)
    async def get_object(self, object_type, provider_id):
        status = ResultStatus.NO_DATA if self.scenario == "no_data" else ResultStatus.SUCCESS
        return ConnectorResult(status, CanonicalObject(object_type, provider_id, {"total_paise": 100}) if status is ResultStatus.SUCCESS else None)
    async def prepare_write(self, operation, canonical_payload): return ConnectorResult(ResultStatus.SUCCESS, canonical_payload)
    async def execute_write(self, approved_action, attempt):
        if self.scenario == "rate_limit": return ConnectorResult(ResultStatus.RATE_LIMITED, retry_after_seconds=30)
        if self.scenario == "timeout": return ConnectorResult(ResultStatus.PROVIDER_UNAVAILABLE, reason_code="TIMEOUT")
        if self.scenario == "ambiguous": return ConnectorResult(ResultStatus.AMBIGUOUS_RESULT)
        return ConnectorResult(ResultStatus.SUCCESS, CanonicalObject("purchase_bill", "ref-1", approved_action.payload))
    async def verify_write(self, provider_object, approved_payload):
        return ConnectorResult(ResultStatus.NEEDS_REVIEW if self.scenario == "mismatch" else ResultStatus.SUCCESS, {})
    async def reconcile_changes(self, cursor): return self._page("changes", cursor)
    async def disconnect(self): return ConnectorResult(ResultStatus.SUCCESS)

    def _page(self, resource, cursor):
        if self.scenario == "no_data": return ConnectorResult(ResultStatus.NO_DATA, [])
        if cursor.value is None:
            status = ResultStatus.PARTIAL if self.scenario in {"partial", "pagination"} else ResultStatus.SUCCESS
            next_cursor = Cursor("2") if status is ResultStatus.PARTIAL else None
            return ConnectorResult(status, [CanonicalObject(resource, "1", {})], next_cursor)
        return ConnectorResult(ResultStatus.SUCCESS, [CanonicalObject(resource, "2", {})])

    async def accept_event(self, event_id: str) -> ResultStatus:
        if event_id in self.seen: return ResultStatus.NO_DATA
        self.seen.add(event_id); return ResultStatus.SUCCESS
