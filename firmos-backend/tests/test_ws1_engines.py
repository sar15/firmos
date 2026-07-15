"""Tests for the engine compute API routes (WS-1)."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.config import settings

client = TestClient(app)

def test_compute_tds():
    settings.firmos_auth_mode = "dev"
    resp = client.post(
        "/api/compute/tds",
        json={"section": "194C", "gross_amount_paise": 5000000, "pan_available": True}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "tds_amount" in data
    assert data["rate"] == 1.0
    assert data["tds_amount"] == 50000

def test_compute_interest():
    settings.firmos_auth_mode = "dev"
    resp = client.post(
        "/api/compute/interest",
        json={
            "total_tax_paise": 1000000,
            "advance_tax_paid_paise": 0,
            "assessment_year_end": "2026-03-31",
            "actual_filing_date": "2026-07-31",
            "installments_paid": []
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "234b" in data
    assert "234c" in data
    assert data["total_interest_paise"] > 0

def test_compute_gst():
    settings.firmos_auth_mode = "dev"
    resp = client.post(
        "/api/compute/gst",
        json={"taxable_paise": 100000, "rate_percent": 18.0, "is_interstate": False}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["cgst"] == 9000
    assert data["sgst"] == 9000
    assert data["igst"] == 0
    assert data["total"] == 118000

def test_compute_itc_eligibility():
    settings.firmos_auth_mode = "dev"
    resp = client.post(
        "/api/compute/itc-eligibility",
        json={
            "supplier_filed": True,
            "invoice_amount_paise": 10000,
            "gstr2b_amount_paise": 10000
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["eligible"] is True

def test_compute_net_gst_payable():
    settings.firmos_auth_mode = "dev"
    resp = client.post(
        "/api/compute/net-gst-payable",
        json={
            "output_gst_paise": 50000,
            "itc_available_paise": 40000,
            "itc_eligible_paise": 30000
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["net_payable"] == 20000  # 50k - 30k eligible
