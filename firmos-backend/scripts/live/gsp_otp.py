import asyncio
from core.config import settings
from connectors.gst_filing.whitebooks.client import WhiteBooksGspClient

async def run():
    client = WhiteBooksGspClient(gstin=settings.test_gstin)
    print("Testing WhiteBooks API Sandbox...")
    try:
        txn = await client.request_otp(settings.gst_username)
        print("OTP request completed")
    except Exception:
        print("OTP request failed")
        return

    try:
        await client.authenticate(settings.gst_username, "575757")
        print("Authentication completed")
    except Exception:
        print("Authentication failed")

if __name__ == "__main__":
    asyncio.run(run())
