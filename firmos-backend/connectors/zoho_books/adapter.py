"""Zoho Books adapter implementing AccountingConnector protocol.

ponytail: thin wrapper around ZohoClient, sync.py, and voucher.py.
"""
from typing import Any
from connectors.accounting import AccountingConnector, LedgerRow
from connectors.gst_filing.types import PurchaseRow, SalesRow
from connectors.zoho_books.client import ZohoClient
from connectors.zoho_books.sync import list_accounts, create_bill, list_invoices_by_period, list_bills_by_period
from connectors.zoho_books.voucher import post_voucher as zoho_post_voucher
from core.money import rupees_to_paise


class ZohoAccountingAdapter:
    """Interchangeable AccountingConnector adapter for Zoho Books."""

    def __init__(self, client: ZohoClient):
        self.client = client

    async def capabilities(self) -> list[str]:
        return ["ledgers", "bills", "vouchers", "registers"]

    async def get_ledgers(self) -> list[LedgerRow]:
        res = await list_accounts(self.client)
        accounts = res.get("chartofaccounts", [])
        return [
            LedgerRow(
                id=str(acc.get("account_id", "")),
                name=str(acc.get("account_name", "")),
                code=str(acc.get("account_code", "")),
                group=str(acc.get("account_type", "")),
            )
            for acc in accounts
        ]

    async def create_purchase_bill(self, bill_payload: dict) -> str:
        res = await create_bill(self.client, bill_payload)
        bill = res.get("bill", {})
        return str(bill.get("bill_id", ""))

    async def post_voucher(self, voucher_payload: dict) -> str:
        doc_kind = voucher_payload.get("doc_kind", "JOURNAL")
        ref_num = voucher_payload.get("reference_number", "")
        res = await zoho_post_voucher(self.client, doc_kind, voucher_payload, ref_num)
        for key in ("journal_id", "invoice_id", "bill_id", "payment_id", "customerpayment_id"):
            if key in res:
                return str(res[key])
        for obj_key in ("journal", "invoice", "bill", "vendorpayment", "customerpayment"):
            if obj_key in res and isinstance(res[obj_key], dict):
                for key in ("journal_id", "invoice_id", "bill_id", "payment_id", "customerpayment_id"):
                    if key in res[obj_key]:
                        return str(res[obj_key][key])
        return str(res.get("id", ""))

    async def get_sales_register(self, start_date: str, end_date: str) -> list[SalesRow]:
        res = await list_invoices_by_period(self.client, start_date, end_date)
        invoices = res.get("invoices", [])
        rows = []
        for inv in invoices:
            rows.append(
                SalesRow(
                    invoice_number=str(inv.get("invoice_number", "")),
                    invoice_date=str(inv.get("date", "")),
                    customer_gstin=str(inv.get("gstno", inv.get("gstin", ""))),
                    customer_name=str(inv.get("customer_name", "")),
                    taxable_value_paise=rupees_to_paise(inv.get("sub_total", 0)),
                    igst_paise=rupees_to_paise(inv.get("igst_total", 0)),
                    cgst_paise=rupees_to_paise(inv.get("cgst_total", 0)),
                    sgst_paise=rupees_to_paise(inv.get("sgst_total", 0)),
                    place_of_supply=str(inv.get("place_of_supply", "")),
                )
            )
        return rows

    async def get_purchase_register(self, start_date: str, end_date: str) -> list[PurchaseRow]:
        res = await list_bills_by_period(self.client, start_date, end_date)
        bills = res.get("bills", [])
        rows = []
        for b in bills:
            rows.append(
                PurchaseRow(
                    invoice_number=str(b.get("bill_number", b.get("reference_number", ""))),
                    invoice_date=str(b.get("date", "")),
                    supplier_gstin=str(b.get("gstno", b.get("vendor_gstin", ""))),
                    supplier_name=str(b.get("vendor_name", "")),
                    taxable_value_paise=rupees_to_paise(b.get("sub_total", 0)),
                    total_gst_paise=rupees_to_paise(b.get("tax_total", 0)),
                )
            )
        return rows

    async def health(self) -> dict:
        try:
            await list_accounts(self.client)
            return {"status": "healthy", "details": "Connected to Zoho Books"}
        except Exception as e:
            return {"status": "error", "details": str(e)}
