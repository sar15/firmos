import asyncio

import httpx
import pytest

from api.routes.connector_zoho_oauth import oauth_state_digest, resolve_zoho_redirect_uri
from connectors.platform.types import ApprovedAction, Cursor, ExecutionAttempt, ResultStatus
from connectors.zoho_books.client import MAX_RESPONSE_BYTES, ZohoClient
from connectors.zoho_books.connector import CAPABILITIES, ZohoBooksV1Connector
from connectors.zoho_books.errors import ZohoError, error_from_response
from connectors.zoho_books.mappers import compare_bill, map_bill
from connectors.zoho_books.paginator import fetch_page
from connectors.zoho_books.purchase_bill import build_purchase_bill
from core.finance_actions import compute_payload_hash


def bill_payload():
    return {
        "organization_id": "org-1", "vendor_id": "vendor-1", "bill_number": "B-7",
        "reference_number": "ref-7", "date": "2026-07-14", "currency_code": "INR",
        "line_items": [{"account_id": "expense-1", "rate_paise": 12345, "quantity": 2, "tax_id": "tax-1"}],
        "subtotal_paise": 24690, "tax_total_paise": 4444, "total_paise": 29134,
    }


@pytest.mark.parametrize(
    ("status", "expected"),
    [(400, ResultStatus.INVALID_PAYLOAD), (401, ResultStatus.AUTH_EXPIRED),
     (404, ResultStatus.NO_DATA), (429, ResultStatus.RATE_LIMITED),
     (500, ResultStatus.PROVIDER_UNAVAILABLE)],
)
def test_typed_provider_errors(status, expected):
    error = error_from_response(status, {"code": 57}, "9")
    assert error.status is expected
    assert error.correlation_id
    if status == 429:
        assert error.retry_after_seconds == 9


@pytest.mark.asyncio
async def test_client_refreshes_only_once_for_twenty_expired_requests():
    refreshes = 0

    async def handler(request):
        token = request.headers["Authorization"]
        status = 200 if token.endswith("fresh") else 401
        return httpx.Response(status, json={"code": 0, "ok": status == 200})

    async def refresh():
        nonlocal refreshes
        refreshes += 1
        await asyncio.sleep(0)
        return "fresh"

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = ZohoClient("expired", None, "org-1", http=http, refresh=refresh)
    results = await asyncio.gather(*(client.get("/contacts") for _ in range(20)))
    await http.aclose()
    assert all(result["ok"] for result in results)
    assert refreshes == 1


@pytest.mark.asyncio
async def test_client_rejects_invalid_or_oversized_json():
    for response in (
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1)),
    ):
        http = httpx.AsyncClient(transport=httpx.MockTransport(lambda _request, r=response: r))
        client = ZohoClient("token", None, "org-1", http=http)
        with pytest.raises(ZohoError) as caught:
            await client.get("/contacts")
        await http.aclose()
        assert caught.value.status is ResultStatus.PROVIDER_UNAVAILABLE


class PageClient:
    def __init__(self, total):
        self.total = total

    async def get(self, _path, params):
        page, size = params["page"], params["per_page"]
        start = (page - 1) * size
        rows = [{"contact_id": str(index)} for index in range(start, min(start + size, self.total))]
        return {"contacts": rows, "page_context": {"has_more_page": start + size < self.total}}


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 1, 200, 201, 500])
async def test_paginator_has_complete_resumable_counts(count):
    cursor, seen = Cursor(), []
    while True:
        page = await fetch_page(PageClient(count), "/contacts", "contacts", cursor)
        seen.extend(page.data or [])
        if page.status is not ResultStatus.PARTIAL:
            break
        cursor = page.next_cursor
    assert len(seen) == count
    assert len({row["contact_id"] for row in seen}) == count


def test_purchase_bill_is_immutable_hashed_and_readback_verified():
    request = build_purchase_bill(bill_payload())
    assert request.payload["line_items"][0]["rate"] == "123.45"
    assert request.request_hash == build_purchase_bill(bill_payload()).request_hash
    actual = map_bill({
        "bill_id": "provider-1", "vendor_id": "vendor-1", "bill_number": "B-7",
        "reference_number": "ref-7", "date": "2026-07-14", "currency_code": "INR",
        "sub_total": "246.90", "tax_total": "44.44", "total": "291.34",
        "line_items": [{"account_id": "expense-1", "rate": "123.45", "quantity": 2, "tax_id": "tax-1"}],
    }, "org-1")
    assert compare_bill(request.payload, actual, "org-1") == {}
    changed = map_bill({**actual.values, "bill_id": "provider-1", "vendor_id": "wrong"}, "org-1")
    assert "vendor_id" in compare_bill(request.payload, changed, "org-1")


def test_v1_exposes_no_uncertified_writes():
    writes = {capability for capability in CAPABILITIES if ".write." in capability}
    assert writes == {"zoho.write.purchase_bill.create", "zoho.write.sales_invoice.create"}


def test_oauth_state_and_redirect_ignore_request_headers(monkeypatch):
    monkeypatch.setattr("api.routes.connector_zoho_oauth.settings.zoho_redirect_uri", "https://firmos.example/api/connectors/callback/zoho")
    assert resolve_zoho_redirect_uri(None) == "https://firmos.example/api/connectors/callback/zoho"
    assert oauth_state_digest("state") != oauth_state_digest("State")


class BillFaultSimulator:
    organization_id = "org-1"

    def __init__(self, candidates, fail_post=False, search_error=False):
        self.candidates, self.fail_post, self.search_error = candidates, fail_post, search_error
        self.posts = 0

    async def get(self, path, **_kwargs):
        if path == "/bills":
            if self.search_error:
                raise httpx.ConnectError("offline")
            return {"bills": self.candidates}
        return {"bill": {
            "bill_id": path.rsplit("/", 1)[-1], "vendor_id": "vendor-1",
            "bill_number": "B-7", "reference_number": "ref-7", "date": "2026-07-14",
            "currency_code": "INR", "sub_total": "246.90", "tax_total": "44.44",
            "total": "291.34", "line_items": [{"account_id": "expense-1", "rate": "123.45",
            "quantity": 2, "tax_id": "tax-1"}],
        }}

    async def post(self, _path, **_kwargs):
        self.posts += 1
        if self.fail_post:
            raise ZohoError(ResultStatus.PROVIDER_UNAVAILABLE, "ZOHO_PROVIDER_UNAVAILABLE", "fault")
        return {"bill": {"bill_id": "created-1"}}


class PostRecoverySimulator(BillFaultSimulator):
    def __init__(self):
        super().__init__([], fail_post=True)
        self.searches = 0

    async def get(self, path, **kwargs):
        if path == "/bills":
            self.searches += 1
            return {"bills": [] if self.searches == 1 else [{"bill_id": "recovered-1"}]}
        return await super().get(path, **kwargs)


def simulated_connector(monkeypatch, client):
    connector = object.__new__(ZohoBooksV1Connector)

    async def get_client():
        return client

    monkeypatch.setattr(connector, "_client", get_client)
    return connector


def approved_bill():
    payload = bill_payload()
    return ApprovedAction("action-1", "zoho.write.purchase_bill.create", payload,
                          compute_payload_hash(payload), "correlation-1")


@pytest.mark.asyncio
async def test_simulator_prevents_duplicate_and_flags_multiple_candidates(monkeypatch):
    existing = BillFaultSimulator([{"bill_id": "existing-1"}])
    result = await simulated_connector(monkeypatch, existing).execute_write(
        approved_bill(), ExecutionAttempt(1, "logical-key"),
    )
    assert result.status is ResultStatus.SUCCESS
    assert result.data.provider_id == "existing-1"
    assert existing.posts == 0

    duplicates = BillFaultSimulator([{"bill_id": "one"}, {"bill_id": "two"}])
    result = await simulated_connector(monkeypatch, duplicates).execute_write(
        approved_bill(), ExecutionAttempt(1, "logical-key"),
    )
    assert result.status is ResultStatus.NEEDS_REVIEW
    assert duplicates.posts == 0


@pytest.mark.asyncio
async def test_simulator_never_writes_when_preflight_search_is_offline(monkeypatch):
    offline = BillFaultSimulator([], search_error=True)
    result = await simulated_connector(monkeypatch, offline).execute_write(
        approved_bill(), ExecutionAttempt(1, "logical-key"),
    )
    assert result.status is ResultStatus.AMBIGUOUS_RESULT
    assert offline.posts == 0


@pytest.mark.asyncio
async def test_simulator_recovers_provider_accept_then_server_error(monkeypatch):
    simulator = PostRecoverySimulator()
    result = await simulated_connector(monkeypatch, simulator).execute_write(
        approved_bill(), ExecutionAttempt(1, "logical-key"),
    )
    assert result.status is ResultStatus.SUCCESS
    assert result.data.provider_id == "recovered-1"
    assert simulator.posts == 1
