from connectors.tally.canonical import compare_purchase, deterministic_remote_id, validate_purchase
from connectors.tally.ingest import period_for, voucher_total
import pytest


def purchase():
    return {
        "tally_company": "Acme Books", "company_guid": "cmp-1",
        "date": "2026-07-15", "party_ledger": "Vendor A",
        "purchase_ledger": "Purchases", "total_paise": 12345,
    }


def test_purchase_is_normalized_without_float_money():
    value = validate_purchase(purchase())
    assert value["date"] == "20260715"
    assert value["total_paise"] == 12345
    assert deterministic_remote_id("abc") == "firmos:abc"


def test_readback_requires_identity_company_and_amount():
    actual = {
        "remote_id": "firmos:abc", "company_guid": "cmp-1",
        "voucher_type": "Purchase", "date": "20260715",
        "party_ledger": "Vendor A",
        "entries": [
            {"ledger_name": "Vendor A", "amount_paise": 12345},
            {"ledger_name": "Purchases", "amount_paise": -12345},
        ],
        "total_paise": 12345,
    }
    assert compare_purchase(purchase(), actual, "firmos:abc") == {}
    actual["company_guid"] = "wrong"
    assert "company_guid" in compare_purchase(purchase(), actual, "firmos:abc")


def test_register_projection_helpers_are_deterministic():
    assert period_for("20260715") == "072026"
    assert voucher_total([{"amount_paise": 2500}, {"amount_paise": -2500}]) == 2500


def test_purchase_refuses_same_ledger_on_both_sides():
    value = purchase()
    value["purchase_ledger"] = value["party_ledger"]
    with pytest.raises(ValueError, match="different"):
        validate_purchase(value)


def test_purchase_refuses_unbalanced_or_non_inr_entries():
    value = purchase()
    value["entries"] = [
        {"ledger_name": "Vendor A", "amount_paise": 12345},
        {"ledger_name": "Purchases", "amount_paise": -12000},
    ]
    with pytest.raises(ValueError, match="balance"):
        validate_purchase(value)
    value = purchase()
    value["currency"] = "USD"
    with pytest.raises(ValueError, match="INR"):
        validate_purchase(value)
