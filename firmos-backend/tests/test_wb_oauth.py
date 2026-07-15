import asyncio
import httpx
import os

async def main():
    client_id = os.environ.get("GSP_API_KEY")
    client_secret = os.environ.get("GSP_API_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("Set GSP_API_KEY and GSP_API_SECRET before running this live probe")
    
    url = "https://apisandbox.whitebooks.in/oauth/token"
    print(f"Trying OAuth token on {url}...")
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "gst einvoice eway"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        print(resp.status_code)
        print("OAuth response received; response body is redacted")

if __name__ == "__main__":
    asyncio.run(main())
