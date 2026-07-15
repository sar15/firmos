"""Certified Zoho Books V1 connector: complete reads and verified bill create."""
from datetime import datetime, timedelta, timezone
import json

import httpx

from connectors.platform.base import Connector
from connectors.platform.credentials import revoke_credentials
from connectors.platform.registry import registry
from connectors.platform.types import ApprovedAction, CanonicalObject, ConnectorResult, Cursor, ExecutionAttempt, ResultStatus, Scope
from connectors.zoho_books.auth import revoke_token
from connectors.zoho_books.credentials import ZohoCredentialService
from connectors.zoho_books.errors import ZohoError
from connectors.zoho_books.mappers import compare_bill, map_bill, map_invoice
from connectors.zoho_books.paginator import fetch_page
from connectors.zoho_books.purchase_bill import build_purchase_bill
from connectors.zoho_books.sales_invoice import build_sales_invoice
from core.finance_actions import compute_payload_hash

READ_RESOURCES = {
    "contacts": ("/contacts", "contacts", "contact"),
    "accounts": ("/chartofaccounts", "chartofaccounts", "account"),
    "items": ("/items", "items", "item"),
    "taxes": ("/settings/taxes", "taxes", "tax"),
}
CAPABILITIES = {
    "zoho.read.organizations", "zoho.read.contacts", "zoho.read.accounts",
    "zoho.read.items", "zoho.read.taxes", "zoho.read.purchase_bills",
    "zoho.read.sales_invoices", "zoho.read.object", "zoho.write.purchase_bill.create",
    "zoho.verify.purchase_bill", "zoho.write.sales_invoice.create", "zoho.verify.sales_invoice",
}
REQUIRED_SCOPES = {
    "zoho.read.organizations": "ZohoBooks.settings.READ",
    "zoho.read.contacts": "ZohoBooks.contacts.READ",
    "zoho.read.accounts": "ZohoBooks.settings.READ",
    "zoho.read.items": "ZohoBooks.settings.READ",
    "zoho.read.taxes": "ZohoBooks.settings.READ",
    "zoho.read.purchase_bills": "ZohoBooks.bills.READ",
    "zoho.read.sales_invoices": "ZohoBooks.invoices.READ",
    "zoho.write.purchase_bill.create": "ZohoBooks.bills.CREATE",
    "zoho.verify.purchase_bill": "ZohoBooks.bills.READ",
    "zoho.write.sales_invoice.create": "ZohoBooks.invoices.CREATE",
    "zoho.verify.sales_invoice": "ZohoBooks.invoices.READ",
}


def capabilities_for_scopes(scopes) -> set[str]:
    """Return only capabilities the current OAuth grant can really perform."""
    granted = set(scopes or [])
    available = {
        key for key in CAPABILITIES
        if key != "zoho.read.object" and REQUIRED_SCOPES.get(key) in granted
    }
    if {"ZohoBooks.bills.READ", "ZohoBooks.invoices.READ"}.issubset(granted):
        available.add("zoho.read.object")
    return available


class ZohoBooksV1Connector(Connector):
    def __init__(self, pool, installation_id: str):
        self.pool = pool
        self.installation_id = str(installation_id)
        self.credentials = ZohoCredentialService(pool, self.installation_id)

    async def _client(self):
        row, _ = await self.credentials.load()
        configuration = row["configuration"]
        if isinstance(configuration, str):
            configuration = json.loads(configuration)
        async with self.pool.acquire() as conn:
            budget = await conn.fetchrow(
                """INSERT INTO connector_rate_budgets(installation_id,organization_id,requests_used)
                   VALUES($1::uuid,$2,1) ON CONFLICT(installation_id) DO UPDATE SET
                   window_started_at=CASE WHEN connector_rate_budgets.window_started_at<NOW()-interval '1 hour'
                     THEN NOW() ELSE connector_rate_budgets.window_started_at END,
                   requests_used=CASE WHEN connector_rate_budgets.window_started_at<NOW()-interval '1 hour'
                     THEN 1 ELSE connector_rate_budgets.requests_used+1 END,
                   blocked_until=CASE WHEN connector_rate_budgets.blocked_until<NOW()
                     THEN NULL ELSE connector_rate_budgets.blocked_until END,updated_at=NOW()
                   RETURNING blocked_until""",
                self.installation_id, str(configuration.get("organization_id") or ""),
            )
        if budget["blocked_until"] and budget["blocked_until"] > datetime.now(timezone.utc):
            raise ZohoError(ResultStatus.RATE_LIMITED, "ZOHO_RATE_BUDGET_BLOCKED", "Zoho rate limit is cooling down", 60)
        return await self.credentials.client()

    async def _blocked(self, seconds: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE connector_rate_budgets SET blocked_until=$1,updated_at=NOW() WHERE installation_id=$2::uuid",
                datetime.now(timezone.utc) + timedelta(seconds=seconds), self.installation_id,
            )

    async def _run(self, operation):
        try:
            return await operation(await self._client())
        except ZohoError as exc:
            if exc.status is ResultStatus.RATE_LIMITED:
                await self._blocked(exc.retry_after_seconds or 60)
            return exc.result()
        except httpx.TransportError:
            return ConnectorResult(ResultStatus.PROVIDER_UNAVAILABLE, reason_code="ZOHO_CONNECTION_FAILED")

    async def probe(self) -> ConnectorResult[dict]:
        async def call(client):
            response = await client.get(f"/organizations/{client.organization_id}")
            return ConnectorResult(ResultStatus.SUCCESS, {"organization": response.get("organization", {})})
        return await self._run(call)

    async def get_capabilities(self) -> ConnectorResult[list[str]]:
        row, _ = await self.credentials.load()
        return ConnectorResult(ResultStatus.SUCCESS, sorted(capabilities_for_scopes(row["scopes"])))

    async def list_masters(self, resource: str, cursor: Cursor) -> ConnectorResult[list[CanonicalObject]]:
        if resource not in READ_RESOURCES:
            return ConnectorResult(ResultStatus.UNSUPPORTED, reason_code="ZOHO_MASTER_UNSUPPORTED")
        path, key, object_type = READ_RESOURCES[resource]
        async def call(client):
            page = await fetch_page(client, path, key, cursor)
            objects = [CanonicalObject(object_type, str(row.get(f"{object_type}_id") or row.get("account_id") or ""), row) for row in page.data or []]
            return ConnectorResult(page.status, objects, page.next_cursor, page.reason_code)
        return await self._run(call)

    async def list_transactions(self, resource: str, scope: Scope, cursor: Cursor) -> ConnectorResult[list[CanonicalObject]]:
        if resource not in {"purchase_bills", "sales_invoices"}:
            return ConnectorResult(ResultStatus.UNSUPPORTED, reason_code="ZOHO_TRANSACTION_UNSUPPORTED")
        try:
            start, end = str(scope.period or "").split(":", 1)
        except ValueError:
            return ConnectorResult(ResultStatus.INVALID_PAYLOAD, reason_code="ZOHO_PERIOD_REQUIRED")
        path, key = ("/bills", "bills") if resource == "purchase_bills" else ("/invoices", "invoices")
        async def call(client):
            page = await fetch_page(client, path, key, cursor, {"date_start": start, "date_end": end})
            mapper = map_bill if resource == "purchase_bills" else map_invoice
            return ConnectorResult(page.status, [mapper(row, client.organization_id) for row in page.data or []], page.next_cursor)
        return await self._run(call)

    async def get_object(self, object_type: str, provider_id: str) -> ConnectorResult[CanonicalObject]:
        if object_type not in {"purchase_bill", "sales_invoice"}:
            return ConnectorResult(ResultStatus.UNSUPPORTED, reason_code="ZOHO_OBJECT_UNSUPPORTED")
        path = "/bills" if object_type == "purchase_bill" else "/invoices"
        key = "bill" if object_type == "purchase_bill" else "invoice"
        mapper = map_bill if object_type == "purchase_bill" else map_invoice
        async def call(client):
            payload = (await client.get(f"{path}/{provider_id}")).get(key, {})
            return ConnectorResult(ResultStatus.SUCCESS, mapper(payload, client.organization_id))
        return await self._run(call)

    async def prepare_write(self, operation: str, canonical_payload: dict) -> ConnectorResult[dict]:
        if operation == "zoho.write.sales_invoice.create":
            try:
                request = build_sales_invoice(canonical_payload)
                return ConnectorResult(ResultStatus.SUCCESS, {"provider_payload": request.payload, "request_hash": request.request_hash})
            except ValueError:
                return ConnectorResult(ResultStatus.INVALID_PAYLOAD, reason_code="ZOHO_SALES_INVOICE_INVALID")
        if operation != "zoho.write.purchase_bill.create":
            return ConnectorResult(ResultStatus.UNSUPPORTED, reason_code="ZOHO_WRITE_UNCERTIFIED")
        try:
            request = build_purchase_bill(canonical_payload)
            return ConnectorResult(ResultStatus.SUCCESS, {"provider_payload": request.payload, "request_hash": request.request_hash})
        except ValueError:
            return ConnectorResult(ResultStatus.INVALID_PAYLOAD, reason_code="ZOHO_BILL_INVALID")

    async def execute_write(self, approved_action: ApprovedAction, attempt: ExecutionAttempt) -> ConnectorResult[CanonicalObject]:
        if approved_action.operation == "zoho.write.sales_invoice.create":
            from connectors.zoho_books.sales_write import execute
            return await execute(self, approved_action)
        if approved_action.operation != "zoho.write.purchase_bill.create":
            return ConnectorResult(ResultStatus.UNSUPPORTED, reason_code="ZOHO_WRITE_UNCERTIFIED")
        if compute_payload_hash(approved_action.payload) != approved_action.payload_hash:
            return ConnectorResult(ResultStatus.INVALID_PAYLOAD, reason_code="APPROVED_PAYLOAD_HASH_MISMATCH")
        prepared = await self.prepare_write(approved_action.operation, approved_action.payload)
        if prepared.status is not ResultStatus.SUCCESS:
            return prepared
        existing = await self._recover_ambiguous(prepared.data["provider_payload"])
        if existing.status in {ResultStatus.SUCCESS, ResultStatus.NEEDS_REVIEW}:
            return existing
        if existing.details.get("candidate_count") != 0:
            return existing
        try:
            client = await self._client()
            created = (await client.post("/bills", bill_json=prepared.data["provider_payload"])).get("bill", {})
            if not created.get("bill_id"):
                return ConnectorResult(ResultStatus.AMBIGUOUS_RESULT, reason_code="ZOHO_CREATE_MISSING_ID")
            return ConnectorResult(ResultStatus.SUCCESS, map_bill(created, client.organization_id), details={"request_hash": prepared.data["request_hash"]})
        except ZohoError as exc:
            if exc.status is ResultStatus.PROVIDER_UNAVAILABLE:
                return await self._recover_ambiguous(prepared.data["provider_payload"])
            return exc.result()
        except httpx.TransportError:
            return await self._recover_ambiguous(prepared.data["provider_payload"])

    async def _recover_ambiguous(self, payload: dict) -> ConnectorResult[CanonicalObject]:
        try:
            client = await self._client()
            params = {"reference_number": payload.get("reference_number")} if payload.get("reference_number") else {"bill_number": payload.get("bill_number")}
            candidates = (await client.get("/bills", params=params)).get("bills", [])
            if len(candidates) == 1:
                recovered = await self.get_object("purchase_bill", str(candidates[0]["bill_id"]))
                if recovered.status is ResultStatus.SUCCESS and recovered.data:
                    mismatches = compare_bill(payload, recovered.data, client.organization_id)
                    if not mismatches:
                        return recovered
                    return ConnectorResult(
                        ResultStatus.NEEDS_REVIEW, recovered.data,
                        reason_code="ZOHO_AMBIGUOUS_CANDIDATE_MISMATCH",
                        details={"mismatches": mismatches},
                    )
            status = ResultStatus.AMBIGUOUS_RESULT if not candidates else ResultStatus.NEEDS_REVIEW
            return ConnectorResult(status, reason_code="ZOHO_AMBIGUOUS_CREATE", details={"candidate_count": len(candidates)})
        except (ZohoError, httpx.TransportError):
            return ConnectorResult(ResultStatus.AMBIGUOUS_RESULT, reason_code="ZOHO_AMBIGUOUS_CREATE")

    async def verify_write(self, provider_object: CanonicalObject, approved_payload: dict) -> ConnectorResult[dict]:
        if provider_object.object_type == "sales_invoice":
            from connectors.zoho_books.sales_write import verify
            return await verify(self, provider_object, approved_payload)
        readback = await self.get_object("purchase_bill", provider_object.provider_id)
        if readback.status is not ResultStatus.SUCCESS or not readback.data:
            return ConnectorResult(readback.status, reason_code=readback.reason_code)
        build_purchase_bill(approved_payload)
        mismatches = compare_bill(approved_payload, readback.data, approved_payload["organization_id"])
        status = ResultStatus.NEEDS_REVIEW if mismatches else ResultStatus.SUCCESS
        return ConnectorResult(status, readback.data.values, details={"mismatches": mismatches, "provider_version": readback.data.provider_version})

    async def reconcile_changes(self, cursor: Cursor) -> ConnectorResult[list[CanonicalObject]]:
        return ConnectorResult(ResultStatus.UNSUPPORTED, reason_code="ZOHO_USE_RESOURCE_SYNC")

    async def disconnect(self) -> ConnectorResult[None]:
        row, values = await self.credentials.load()
        try:
            await revoke_token(values["refresh_token"], row["data_center"])
        except Exception:
            pass
        async with self.pool.acquire() as conn, conn.transaction():
            await revoke_credentials(conn, firm_id=row["firm_id"], installation_id=self.installation_id)
            await conn.execute("UPDATE connector_installations SET status='DISCONNECTED',updated_at=NOW() WHERE id=$1::uuid", self.installation_id)
            await conn.execute(
                """UPDATE connector_sync_jobs SET status='FAILED',mapping_blockers='[\"INSTALLATION_DISCONNECTED\"]'::jsonb,
                   finished_at=NOW() WHERE installation_id=$1::uuid AND status='QUEUED'""",
                self.installation_id,
            )
        return ConnectorResult(ResultStatus.SUCCESS)


_pool = None


def register_zoho_v1(pool) -> None:
    global _pool
    _pool = pool
    try:
        registry.register("ZOHO_BOOKS", "v1", {"zoho.write.purchase_bill.create", "zoho.write.sales_invoice.create"}, lambda installation_id: ZohoBooksV1Connector(_pool, installation_id))
    except ValueError:
        pass
