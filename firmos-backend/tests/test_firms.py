"""Firm selection contract tests."""

import pytest

from api.deps import FirmContext
from api.routes.firms import list_firms


class FirmConnection:
    async def fetch(self, _query, user_id):
        assert user_id == "user-1"
        return [
            {"firm_id": "firm-1", "name": "Primary Firm", "role": "OWNER"},
            {"firm_id": "firm-2", "name": "Second Firm", "role": "REVIEWER"},
        ]


class BorrowedFirmConnection:
    async def __aenter__(self):
        return FirmConnection()

    async def __aexit__(self, *_args):
        return None


class FirmPool:
    def acquire(self):
        return BorrowedFirmConnection()


@pytest.mark.asyncio
async def test_list_firms_returns_all_active_memberships_and_current_selection():
    result = await list_firms(FirmContext("user-1", "firm-2", "REVIEWER"), FirmPool())
    assert result["currentFirmId"] == "firm-2"
    assert [firm["id"] for firm in result["firms"]] == ["firm-1", "firm-2"]
