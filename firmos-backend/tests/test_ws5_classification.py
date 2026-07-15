"""Tests for WS-5 Ledger Classification."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.deps import get_db
from core.config import settings

client = TestClient(app)

def test_classification_expense_head():
    """Test the POST /api/classify/expense-head endpoint."""
    settings.firmos_auth_mode = "dev"
    app.dependency_overrides[get_db] = lambda: None
    
    # Test software classification
    resp = client.post("/api/classify/expense-head", json={
        "description": "AWS Hosting Services",
        "vendor_name": "Amazon Web Services",
        "amount_paise": 500000
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["suggested_head"] == "Software & Cloud Services"
    
    # Test travel classification
    resp = client.post("/api/classify/expense-head", json={
        "description": "Flight to Delhi",
        "vendor_name": "MakeMyTrip",
        "amount_paise": 1500000
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggested_head"] == "Travel & Accommodation"
    
    # Test unknown classification
    resp = client.post("/api/classify/expense-head", json={
        "description": "Random thing",
        "vendor_name": "Unknown",
        "amount_paise": 10000
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggested_head"] == "General Expenses"
    assert data["confidence"] == "LOW"
    app.dependency_overrides.pop(get_db, None)
