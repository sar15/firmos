"""Checks for truthful, period-scoped register projections."""
import pytest
from fastapi import HTTPException

from api.routes.registers import _bounds, _paise


def test_register_period_is_explicit_and_uses_gst_format():
    assert _bounds("062026") == ("2026-06-01", "2026-06-30")
    assert _bounds("122026") == ("2026-12-01", "2026-12-31")
    with pytest.raises(HTTPException):
        _bounds("June 2026")


def test_register_money_conversion_never_uses_float_rounding():
    assert _paise("118.25") == 11825
    assert _paise("0.01") == 1
    with pytest.raises(ValueError):
        _paise("not-money")


@pytest.mark.asyncio
async def test_register_sync_paginates_past_zoho_default_page_size():
    from connectors.zoho_books.sync import list_all_bills_by_period

    class Client:
        async def get(self, _path, params):
            page = params["page"]
            return {"bills": [{"bill_id": str(page)}], "page_context": {"has_more_page": page == 1}}

    assert [bill["bill_id"] for bill in await list_all_bills_by_period(Client(), "2026-06-01", "2026-06-30")] == ["1", "2"]
