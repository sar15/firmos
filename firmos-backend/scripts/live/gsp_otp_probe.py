import asyncio
from core.config import settings
from connectors.gst_filing.whitebooks.client import WhiteBooksGspClient

async def main():
    gstin = settings.test_gstin
    username = settings.gst_username
    print("Testing WhiteBooks GSP authentication flow")
    client = WhiteBooksGspClient(gstin=gstin)
    
    try:
        print("Executing Step 1: request_otp")
        txn = await client.request_otp(username)
        print("OTP request completed")
    except Exception:
        print("OTP request failed")
        return

    try:
        print("Executing Step 2: authenticate (with OTP 575757)")
        await client.authenticate(username, otp="575757")
        print("Authentication completed")
    except Exception:
        print("Authentication failed")

if __name__ == "__main__":
    asyncio.run(main())
