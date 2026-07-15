"""Read-only Zoho sales access probe; prints no financial or credential data."""
import asyncio
import json

import httpx

from connectors.zoho_books.auth import refresh_access_token
from connectors.zoho_books.client import ZohoClient
from core.config import get_settings


async def main() -> None:
    settings=get_settings()
    if not settings.zoho_refresh_token or not settings.zoho_organization_id:
        raise RuntimeError("Zoho legacy credentials are incomplete")
    token=await refresh_access_token(settings.zoho_refresh_token)
    async with httpx.AsyncClient(timeout=30) as http:
        client=ZohoClient(token["access_token"],None,settings.zoho_organization_id,
                          api_domain=token["api_domain"],http=http)
        organization=await client.get(f"/organizations/{settings.zoho_organization_id}")
        page=await client.get("/invoices",params={"page":1,"per_page":1})
        invoices=page.get("invoices",[])
        detail=await client.get(f"/invoices/{invoices[0]['invoice_id']}") if invoices else {}
    print(json.dumps({"organization_read":bool(organization.get("organization")),
                      "invoice_list_read":True,"invoice_count_sample":len(invoices),
                      "invoice_detail_read":bool(detail.get("invoice"))}))


if __name__=="__main__":
    asyncio.run(main())
