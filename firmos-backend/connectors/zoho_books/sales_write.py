"""Certified Zoho sales write with ambiguous-result recovery and read-back."""
import httpx

from connectors.platform.types import ConnectorResult, ResultStatus
from connectors.zoho_books.errors import ZohoError
from connectors.zoho_books.mappers import map_invoice
from connectors.zoho_books.sales_invoice import build_sales_invoice, compare_sales_invoice
from core.finance_actions import compute_payload_hash


async def recover(connector, payload: dict) -> ConnectorResult:
    try:
        client = await connector._client()
        params = {"invoice_number": payload["invoice_number"]}
        candidates = (await client.get("/invoices", params=params)).get("invoices", [])
        if len(candidates) == 1:
            found = await connector.get_object("sales_invoice", str(candidates[0]["invoice_id"]))
            if found.status is ResultStatus.SUCCESS and found.data:
                mismatches = compare_sales_invoice(payload, found.data, client.organization_id)
                if not mismatches:
                    return found
                return ConnectorResult(ResultStatus.NEEDS_REVIEW, found.data,
                                       reason_code="ZOHO_SALES_CANDIDATE_MISMATCH",
                                       details={"mismatches": mismatches})
        status = ResultStatus.AMBIGUOUS_RESULT if not candidates else ResultStatus.NEEDS_REVIEW
        return ConnectorResult(status, reason_code="ZOHO_AMBIGUOUS_SALES_CREATE",
                               details={"candidate_count": len(candidates)})
    except (ZohoError, httpx.TransportError):
        return ConnectorResult(ResultStatus.AMBIGUOUS_RESULT, reason_code="ZOHO_AMBIGUOUS_SALES_CREATE")


async def execute(connector, approved_action) -> ConnectorResult:
    if compute_payload_hash(approved_action.payload) != approved_action.payload_hash:
        return ConnectorResult(ResultStatus.INVALID_PAYLOAD, reason_code="APPROVED_PAYLOAD_HASH_MISMATCH")
    try:
        prepared = build_sales_invoice(approved_action.payload)
    except ValueError:
        return ConnectorResult(ResultStatus.INVALID_PAYLOAD, reason_code="ZOHO_SALES_INVOICE_INVALID")
    existing = await recover(connector, prepared.payload)
    if existing.status in {ResultStatus.SUCCESS, ResultStatus.NEEDS_REVIEW}:
        return existing
    if existing.details.get("candidate_count") != 0:
        return existing
    try:
        client = await connector._client()
        created = (await client.post("/invoices", bill_json=prepared.payload)).get("invoice", {})
        if not created.get("invoice_id"):
            return ConnectorResult(ResultStatus.AMBIGUOUS_RESULT, reason_code="ZOHO_SALES_CREATE_MISSING_ID")
        return ConnectorResult(ResultStatus.SUCCESS, map_invoice(created, client.organization_id),
                               details={"request_hash": prepared.request_hash})
    except ZohoError as exc:
        return await recover(connector, prepared.payload) if exc.status is ResultStatus.PROVIDER_UNAVAILABLE else exc.result()
    except httpx.TransportError:
        return await recover(connector, prepared.payload)


async def verify(connector, provider_object, approved_payload: dict) -> ConnectorResult:
    readback = await connector.get_object("sales_invoice", provider_object.provider_id)
    if readback.status is not ResultStatus.SUCCESS or not readback.data:
        return ConnectorResult(readback.status, reason_code=readback.reason_code)
    mismatches = compare_sales_invoice(approved_payload, readback.data, approved_payload["organization_id"])
    status = ResultStatus.NEEDS_REVIEW if mismatches else ResultStatus.SUCCESS
    return ConnectorResult(status, readback.data.values,
                           details={"mismatches": mismatches, "provider_version": readback.data.provider_version})
