"""Tests for the GSTR-3B endpoints and workflow logic (WS-2)."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.config import settings
from unittest.mock import patch, MagicMock

client = TestClient(app)

def test_gst_summary_endpoint():
    """Test the gst-summary route fetches from Zoho and Reconcile."""
    settings.firmos_auth_mode = "dev"
    
    # Mock db_pool
    class MockConnection:
        async def fetchrow(self, *args, **kwargs):
            return {
                "access_token_enc": "dummy_enc",
                "refresh_token_enc": "dummy_enc",
                "external_account_id": "org_123"
            }
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass

    class MockPool:
        def acquire(self): return MockConnection()

    # Need to override get_db properly
    from api.deps import get_db
    app.dependency_overrides[get_db] = lambda: MockPool()

    with patch("core.security.decrypt_token", return_value="dummy_token"):
        with patch("connectors.zoho_books.sync.list_invoices_by_period", return_value={"invoices": [{"tax_total": 500}]}):
            with patch("api.routes.reconciliation.get_reconciliation") as mock_recon:
                class MockSummary:
                    totalAutoMatched = 20000
                class MockReconRes:
                    summary = MockSummary()
                
                mock_recon.return_value = MockReconRes()
                
                resp = client.get("/api/connectors/zoho/gst-summary?client_id=c-1&period=112024")
                assert resp.status_code == 200
                data = resp.json()
                assert data["output_gst_paise"] == 50000
                assert data["itc_eligible_paise"] == 20000

    app.dependency_overrides.clear()


def test_gstr3b_table_generation():
    from engines.gst import generate_gstr3b_tables
    tables = generate_gstr3b_tables(
        output_taxable_paise=1000000,
        output_igst_paise=0,
        output_cgst_paise=90000,
        output_sgst_paise=90000,
        itc_igst_paise=0,
        itc_cgst_paise=50000,
        itc_sgst_paise=50000,
    )
    t31 = tables["table_3_1"]["a_outward_taxable_supplies"]
    assert t31["txval"] == 1000000
    assert t31["camt"] == 90000
    assert t31["samt"] == 90000

    t4 = tables["table_4"]["A_itc_available"]["5_all_other_itc"]
    assert t4["camt"] == 50000
    assert t4["samt"] == 50000


def test_export_gstr3b_gstn_json():
    from engines.gst import generate_gstr3b_tables, export_gstr3b_gstn_json
    tables = generate_gstr3b_tables(
        output_taxable_paise=1000000,
        output_igst_paise=0,
        output_cgst_paise=90000,
        output_sgst_paise=90000,
        itc_igst_paise=0,
        itc_cgst_paise=50000,
        itc_sgst_paise=50000,
    )
    json_export = export_gstr3b_gstn_json("27AAACA1234A1Z1", "062026", tables)
    assert json_export["gstin"] == "27AAACA1234A1Z1"
    assert json_export["ret_period"] == "062026"
    assert json_export["sup_details"]["osup_det"]["camt"] == "900.00"
    assert json_export["itc_elg"]["itc_avl"][0]["camt"] == "500.00"
