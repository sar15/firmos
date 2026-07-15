"""Compatibility wrapper restricted to the certified purchase-bill operation."""
from connectors.zoho_books.sync import create_bill


async def post_voucher(client, doc_kind: str, voucher_data: dict, reference_number: str) -> dict:
    if doc_kind != "VENDOR_BILL":
        raise ValueError("Only vendor bills are certified for Zoho V1")
    existing = await client.get("/bills", params={"reference_number": reference_number})
    bills = existing.get("bills", [])
    if len(bills) == 1:
        return bills[0]
    if len(bills) > 1:
        raise ValueError("Multiple Zoho bills share this reference; review required")
    return await create_bill(client, voucher_data)
