import asyncio
import os

from connectors.gst_filing.whitebooks.client import WhiteBooksGspClient


async def main():
    gstin = os.environ["TEST_GSTIN"]
    username = os.environ["GST_USERNAME"]
    for name in ("GSP_API_KEY", "GSP_API_SECRET", "WHITEBOOKS_EMAIL"):
        if not os.environ.get(name):
            raise SystemExit(f"Set {name} before running this live probe")

    print(f"Testing WhiteBooks client for GSTIN: {gstin} (user: {username})")
    client = WhiteBooksGspClient(gstin=gstin, username=username)

    try:
        print("\nStep 1 & 2: Testing Authentication (OTP -> Token)...")
        await client.authenticate(username, return_raw=True)
        print("SUCCESS: authentication completed; token output is redacted")
    except Exception as e:
        print(f"FAILED: {e}")


if __name__ == "__main__":
    asyncio.run(main())
