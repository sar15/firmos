"""ZohoBooksPlugin implementing AccountingPlugin capability runtime.

# ponytail: Legacy read facade only; certified writes are worker-only.
"""
from typing import Any, Dict, List
from connectors.zoho_books.client import ZohoClient
from connectors.zoho_books.sync import list_accounts, list_items, list_bills_by_period


def _required_list(payload: dict, key: str) -> list:
    value = payload.get(key)
    if not isinstance(value, list):
        raise RuntimeError(f"Zoho response is missing required list: {key}")
    return value


class ZohoBooksPlugin:
    """Capability-declared plugin runtime for Zoho Books."""

    def __init__(self, client: ZohoClient):
        self.client = client

    async def capabilities(self) -> List[str]:
        return [
            "zoho.read.organizations",
            "zoho.read.contacts",
            "zoho.read.accounts",
            "zoho.read.items",
            "zoho.read.taxes",
            "zoho.read.purchase_bills",
            "zoho.read.sales_invoices",
            "zoho.read.object",
        ]

    async def read(self, operation: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if operation == "zoho.read.chart_of_accounts":
            res = await list_accounts(self.client)
            return {"accounts": _required_list(res, "chartofaccounts")}
        elif operation == "zoho.read.items.list":
            res = await list_items(self.client)
            return {"items": _required_list(res, "items")}
        elif operation == "zoho.read.taxes":
            res = await self.client.get("/settings/taxes")
            return {"taxes": _required_list(res, "taxes")}
        elif operation == "zoho.read.bills.list":
            start_date = input_data.get("start_date", "")
            end_date = input_data.get("end_date", "")
            res = await list_bills_by_period(self.client, start_date, end_date)
            return {"bills": _required_list(res, "bills")}
        elif operation == "zoho.read.contacts.search":
            search_text = input_data.get("query", "")
            res = await self.client.get("/contacts", params={"search_text": search_text})
            return {"contacts": _required_list(res, "contacts")}
        elif operation == "zoho.read.bank_transaction.match_candidates":
            transaction_id = str(input_data.get("bank_transaction_id", ""))
            if not transaction_id:
                raise ValueError("bank_transaction_id is required")
            res = await self.client.get(f"/banktransactions/uncategorized/{transaction_id}/match")
            return {"matching_transactions": _required_list(res, "matching_transactions")}
        raise ValueError(f"Unsupported read operation: {operation}")

    async def execute(self, operation: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        raise ValueError("Zoho writes execute only through the approved finance worker")

    async def health(self) -> Dict[str, Any]:
        try:
            await list_accounts(self.client)
            return {"status": "healthy", "details": "Zoho Books API connected"}
        except Exception as exc:
            return {"status": "error", "details": str(exc)}
