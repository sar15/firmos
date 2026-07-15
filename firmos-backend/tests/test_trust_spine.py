"""Deterministic money, idempotency, connector contract, and credentials."""
from decimal import Decimal
import pytest
from connectors.platform.contract_tests import ReferenceConnector
from connectors.platform.credentials import open_credentials, seal_credentials
from connectors.platform.types import ApprovedAction, Cursor, ExecutionAttempt, ResultStatus
from core.idempotency import idempotency_key
from core.money import MoneyParseError, currency_precision, paise_to_decimal, parse_signed_amount, rupees_to_paise
from core.security import StoredCredentialError


@pytest.mark.parametrize(("value", "paise"), [
    ("₹1,234.56", 123456), ("-1.00", -100), ("0", 0), ("999999999999.99", 99999999999999),
])
def test_money_conversion(value, paise):
    assert rupees_to_paise(value) == paise
    assert paise_to_decimal(paise) == Decimal(paise) / 100


@pytest.mark.parametrize("value", ["1.001", "NaN", "Infinity", "", None])
def test_money_rejects_invalid_or_ambiguous_values(value):
    with pytest.raises(MoneyParseError): rupees_to_paise(value)


def test_signed_amount_and_currency_precision():
    assert parse_signed_amount("1,000 DR") == -100000
    assert parse_signed_amount("1,000", "Cr") == 100000
    assert currency_precision("JPY") == 0 and currency_precision("INR") == 2


def test_idempotency_is_stable_and_complete():
    values = dict(firm_id="f", client_id="c", installation_id="i", operation="write",
                  source_identity="invoice-1", source_version="2", approved_payload_hash="abc")
    assert idempotency_key(**values) == idempotency_key(**values)
    with pytest.raises(ValueError): idempotency_key(**{**values, "source_identity": ""})


def test_credential_envelope_is_tenant_bound_and_tamper_evident():
    sealed = seal_credentials("firm-1", "install-1", {"refresh_token": "secret"}, "v1")
    assert open_credentials("firm-1", "install-1", sealed, "v1")["refresh_token"] == "secret"
    with pytest.raises(StoredCredentialError): open_credentials("firm-2", "install-1", sealed, "v1")
    with pytest.raises(StoredCredentialError): open_credentials("firm-1", "install-1", sealed[:-1] + b"x", "v1")


@pytest.mark.asyncio
@pytest.mark.parametrize(("scenario", "status"), [
    ("auth_expiry", ResultStatus.AUTH_EXPIRED), ("no_data", ResultStatus.NO_DATA),
    ("rate_limit", ResultStatus.RATE_LIMITED), ("timeout", ResultStatus.PROVIDER_UNAVAILABLE),
    ("ambiguous", ResultStatus.AMBIGUOUS_RESULT),
])
async def test_reference_connector_failure_contract(scenario, status):
    connector = ReferenceConnector(scenario)
    if scenario == "auth_expiry": result = await connector.probe()
    elif scenario == "no_data": result = await connector.get_object("bill", "1")
    else: result = await connector.execute_write(ApprovedAction("1", "reference.write", {}, "hash", "corr"), ExecutionAttempt(1, "key"))
    assert result.status is status


@pytest.mark.asyncio
async def test_reference_connector_pagination_duplicate_and_mismatch_contract():
    connector = ReferenceConnector("pagination")
    first = await connector.list_masters("ledger", Cursor())
    assert first.status is ResultStatus.PARTIAL and first.next_cursor
    assert (await connector.list_masters("ledger", first.next_cursor)).status is ResultStatus.SUCCESS
    assert await connector.accept_event("event-1") is ResultStatus.SUCCESS
    assert await connector.accept_event("event-1") is ResultStatus.NO_DATA
    mismatch = ReferenceConnector("mismatch")
    assert (await mismatch.verify_write(first.data[0], {})).status is ResultStatus.NEEDS_REVIEW
    assert (await connector.disconnect()).status is ResultStatus.SUCCESS


@pytest.mark.asyncio
async def test_reference_connector_partial_page_and_no_data_are_explicit():
    partial = await ReferenceConnector("partial").list_transactions("bill", None, Cursor())
    assert partial.status is ResultStatus.PARTIAL and partial.next_cursor
    empty = await ReferenceConnector("no_data").list_masters("ledger", Cursor())
    assert empty.status is ResultStatus.NO_DATA and empty.data == []
