import asyncio
import os
import sys

from dotenv import load_dotenv

# Load env before importing settings
load_dotenv()

from core.config import settings
from connectors.gst_filing.whitebooks.client import WhiteBooksGspClient
from connectors.gst_filing.types import PurchaseRow

async def run_live_test():
    print("=== GSTN Sandbox Live Round-Trip Test ===")

    # 1. Initialize Client
    gstin = settings.test_gstin or "33AAGCB1286Q1ZB"
    username = settings.gst_username
    print("\n1. Initializing WhiteBooks client")
    client = WhiteBooksGspClient(gstin=gstin, username=username)

    # 2. OTP Request & Authenticate
    print("\n2. Requesting OTP & Authenticating...")
    try:
        await client.authenticate(username, otp="575757")
        print("Authentication completed")
    except Exception:
        print("Authentication failed")
        return

    # 3. Fetch GSTR-2B
    period = "062026"
    print(f"\n3. Fetching GSTR-2B for period {period}...")
    try:
        gstr2b = await client.fetch_2b(gstin, period)
        print(f"GSTR-2B Entries Count: {len(gstr2b.entries)}")
    except Exception:
        print("Fetch GSTR-2B failed")
        return

    # 4. Reconcile 2B
    print("\n4. Reconciling against a sample purchase ledger...")
    sample_purchases = [
        PurchaseRow(
            invoice_number="INV-001",
            supplier_gstin="27ABCDE1234F1Z5",
            supplier_name="Sample Vendor",
            invoice_date="01-06-2026",
            taxable_value_paise=100000,
            total_gst_paise=18000
        )
    ]
    try:
        recon_report = await client.reconcile_2b(gstin, period, sample_purchases)
        print(f"Recon Report: Matched: {recon_report.matched_count}, Mismatched: {recon_report.mismatched_count}")
    except Exception:
        print("Reconciliation failed")
        return

    print("\n5. Manual GSTR-3B portal submission is intentionally skipped.")

if __name__ == "__main__":
    asyncio.run(run_live_test())
