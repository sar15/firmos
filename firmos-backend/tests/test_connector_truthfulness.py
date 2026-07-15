"""Connector setup must never claim an unsupported integration is connected."""

import pytest
from fastapi import HTTPException

from api.deps import FirmContext
from api.routes.connectors import _oauth_state_digest, connect_connector
from connectors.zoho_books.auth import ZOHO_SCOPES


def test_zoho_connection_state_is_non_reversible_and_scopes_limit_writes_to_supported_documents():
    state = "one-time-browser-state"
    assert _oauth_state_digest(state) != state
    assert len(_oauth_state_digest(state)) == 64
    assert "ZohoBooks.contacts.CREATE" not in ZOHO_SCOPES
    assert "ZohoBooks.invoices.CREATE" in ZOHO_SCOPES
    assert "ZohoBooks.bills.CREATE" in ZOHO_SCOPES


@pytest.mark.asyncio
async def test_manual_gst_connector_does_not_fake_a_connection():
    with pytest.raises(HTTPException) as error:
        await connect_connector("c2", FirmContext("user-1", "firm-1", "OWNER"), None)
    assert error.value.status_code == 409
    assert "uploaded manually" in str(error.value.detail)
