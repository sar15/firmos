"""V1 cannot send filing writes to WhiteBooks."""

import pytest

from connectors.gst_filing.base import ManualFilingRequiredError
from connectors.gst_filing.whitebooks.client import WhiteBooksGspClient


@pytest.mark.asyncio
async def test_whitebooks_filing_is_manual_only():
    client = WhiteBooksGspClient("27AAACA1234A1Z1")
    with pytest.raises(ManualFilingRequiredError):
        await client.file_gstr3b("27AAACA1234A1Z1", "062026", "123456")
