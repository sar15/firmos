"""Zoho Books sync operations — read bills/contacts, create vendor bills.

India DC: bills must include gst_treatment + source_of_supply for GST to calculate.
"""

import json

import httpx

from connectors.zoho_books.client import ZohoClient


class ZohoSyncError(Exception):
    pass


async def list_bills(client: ZohoClient, page: int = 1) -> dict:
    """Fetch vendor bills from Zoho Books."""
    try:
        return await client.get("/bills", params={"page": page, "per_page": 200})
    except httpx.HTTPStatusError as exc:
        raise ZohoSyncError(f"Failed to list bills: {exc.response.text}") from exc


async def get_bill(client: ZohoClient, bill_id: str) -> dict:
    """Get a single bill by ID."""
    try:
        return await client.get(f"/bills/{bill_id}")
    except httpx.HTTPStatusError as exc:
        raise ZohoSyncError(f"Failed to get bill {bill_id}: {exc.response.text}") from exc


async def get_invoice(client: ZohoClient, invoice_id: str) -> dict:
    """Get a single invoice, including its provider-calculated tax components."""
    try:
        return await client.get(f"/invoices/{invoice_id}")
    except httpx.HTTPStatusError as exc:
        raise ZohoSyncError(f"Failed to get invoice {invoice_id}: {exc.response.text}") from exc


async def create_bill(client: ZohoClient, bill_data: dict) -> dict:
    """Legacy direct writes are closed; use the approved worker action."""
    raise ZohoSyncError("Direct Zoho bill creation is disabled; queue an approved finance action")


async def create_contact(client: ZohoClient, contact_data: dict) -> dict:
    """Compatibility boundary: contact creation is not certified in V1."""
    raise ZohoSyncError("Zoho contact creation is not certified in V1")


async def list_contacts(client: ZohoClient, page: int = 1) -> dict:
    """Fetch contacts (vendors) from Zoho Books."""
    try:
        return await client.get("/contacts", params={"page": page, "per_page": 200})
    except httpx.HTTPStatusError as exc:
        raise ZohoSyncError(f"Failed to list contacts: {exc.response.text}") from exc


async def search_contacts(client: ZohoClient, name: str) -> dict:
    """Search for a contact by name."""
    try:
        return await client.get("/contacts", params={"contact_name_contains": name})
    except httpx.HTTPStatusError as exc:
        raise ZohoSyncError(f"Failed to search contacts: {exc.response.text}") from exc


async def list_accounts(client: ZohoClient) -> dict:
    """Fetch chart of accounts."""
    try:
        return await client.get("/chartofaccounts")
    except httpx.HTTPStatusError as exc:
        raise ZohoSyncError(f"Failed to list accounts: {exc.response.text}") from exc


async def list_items(client: ZohoClient) -> dict:
    """Fetch sellable items. Zoho invoices use item IDs, not account IDs."""
    try:
        return await client.get("/items", params={"per_page": 200})
    except httpx.HTTPStatusError as exc:
        raise ZohoSyncError(f"Failed to list items: {exc.response.text}") from exc


async def list_invoices(client: ZohoClient, page: int = 1) -> dict:
    """Fetch sales invoices from Zoho Books."""
    try:
        return await client.get("/invoices", params={"page": page, "per_page": 200})
    except httpx.HTTPStatusError as exc:
        raise ZohoSyncError(f"Failed to list invoices: {exc.response.text}") from exc


async def list_invoices_by_period(client: ZohoClient, date_start: str, date_end: str) -> dict:
    """Fetch sales invoices filtered by date range. Dates in YYYY-MM-DD."""
    try:
        return await client.get("/invoices", params={
            "date_start": date_start, "date_end": date_end, "per_page": 200,
        })
    except httpx.HTTPStatusError as exc:
        raise ZohoSyncError(f"Failed to list invoices by period: {exc.response.text}") from exc


async def list_bills_by_period(client: ZohoClient, date_start: str, date_end: str) -> dict:
    """Fetch vendor bills filtered by date range. Dates in YYYY-MM-DD."""
    try:
        return await client.get("/bills", params={
            "date_start": date_start, "date_end": date_end, "per_page": 200,
        })
    except httpx.HTTPStatusError as exc:
        raise ZohoSyncError(f"Failed to list bills by period: {exc.response.text}") from exc


async def _list_all_by_period(client: ZohoClient, path: str, key: str, date_start: str, date_end: str) -> list[dict]:
    """Read every page for a selected period; a register must not silently stop at 200 rows."""
    rows: list[dict] = []
    for page in range(1, 1001):
        response = await client.get(path, params={"date_start": date_start, "date_end": date_end, "page": page, "per_page": 200})
        page_rows = response.get(key, [])
        rows.extend(page_rows)
        if not page_rows or not response.get("page_context", {}).get("has_more_page", False):
            return rows
    raise ZohoSyncError("Zoho period sync exceeded 1,000 pages; narrow the period before retrying")


async def list_all_invoices_by_period(client: ZohoClient, date_start: str, date_end: str) -> list[dict]:
    return await _list_all_by_period(client, "/invoices", "invoices", date_start, date_end)


async def list_all_bills_by_period(client: ZohoClient, date_start: str, date_end: str) -> list[dict]:
    return await _list_all_by_period(client, "/bills", "bills", date_start, date_end)


async def list_bank_transactions(client: ZohoClient, account_id: str, date_start: str, date_end: str) -> dict:
    """Fetch bank transactions for a specific bank account. Dates in YYYY-MM-DD."""
    try:
        return await client.get("/banktransactions", params={
            "account_id": account_id, "date_start": date_start,
            "date_end": date_end, "per_page": 200,
        })
    except httpx.HTTPStatusError as exc:
        raise ZohoSyncError(f"Failed to list bank transactions: {exc.response.text}") from exc
