"""Unit tests for ZohoBooksPlugin & ZohoBillCreate vertical slice.

# ponytail: Self-checking runnable tests verifying integer paise validation, strict decimal string formatting, and declared capabilities.
"""
import pytest
from connectors.zoho_books import ZohoBooksPlugin, ZohoBillCreate


class DummyZohoClient:
    async def get(self, path: str, **kwargs) -> dict:
        if path == "/settings/taxes":
            return {"taxes": [{"tax_id": "tax-18", "tax_name": "GST 18%"}]}
        if path == "/items":
            return {"items": [{"item_id": "item-1", "name": "Consulting", "status": "active"}]}
        return {}

    async def post(self, path: str, **kwargs) -> dict:
        bill_json = kwargs.get("bill_json", {})
        if path == "/invoices":
            return {"code": 0, "message": "success", "invoice": {"invoice_id": "ZOHO-INVOICE-12345", "invoice_number": bill_json.get("invoice_number")}}
        return {"code": 0, "message": "success", "bill": {"bill_id": "ZOHO-BILL-12345", "bill_number": bill_json.get("bill_number")}}


def test_zoho_bill_create_model_validation():
    payload = {
        "vendor_id": "contact-1",
        "bill_number": "BILL-2026-001",
        "date": "2026-06-30",
        "line_items": [
            {"account_id": "acc-1", "rate_paise": 4000000, "quantity": 1, "description": "Legal services"}
        ],
    }

    model = ZohoBillCreate.from_dict(payload)
    zoho_json = model.to_zoho_json()

    assert zoho_json["vendor_id"] == "contact-1"
    assert zoho_json["bill_number"] == "BILL-2026-001"
    assert zoho_json["line_items"][0]["rate"] == "40000.00"

    # missing vendor_id raises error
    with pytest.raises(ValueError):
        ZohoBillCreate.from_dict({"bill_number": "B-1", "date": "2026-06-30", "line_items": []})


@pytest.mark.asyncio
async def test_zoho_plugin_capabilities_and_execution():
    plugin = ZohoBooksPlugin(DummyZohoClient())
    caps = await plugin.capabilities()
    assert "zoho.write.purchase_bill.create" not in caps
    assert "zoho.read.purchase_bills" in caps
    assert "zoho.read.taxes" in caps
    assert "zoho.write.invoice.create" not in caps
    assert (await plugin.read("zoho.read.taxes", {}))["taxes"][0]["tax_id"] == "tax-18"

    payload = {
        "vendor_id": "contact-1",
        "bill_number": "BILL-2026-001",
        "date": "2026-06-30",
        "line_items": [
            {"account_id": "acc-1", "rate_paise": 1000000, "quantity": 2}
        ],
    }

    with pytest.raises(ValueError):
        await plugin.execute("zoho.write.purchase_bill.create", payload)
