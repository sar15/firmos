"""Zoho Books OAuth helpers with explicit data-center metadata."""

import urllib.parse

from core.config import settings


# India DC endpoints — NEVER .com
ZOHO_AUTH_URL = "https://accounts.zoho.in/oauth/v2/auth"
ZOHO_TOKEN_URL = "https://accounts.zoho.in/oauth/v2/token"
ZOHO_REVOKE_URL = "https://accounts.zoho.in/oauth/v2/token/revoke"
ZOHO_API_BASE = "https://www.zohoapis.in/books/v3"
ACCOUNTS_BY_DC = {
    "us": "https://accounts.zoho.com", "eu": "https://accounts.zoho.eu",
    "in": "https://accounts.zoho.in", "au": "https://accounts.zoho.com.au",
    "jp": "https://accounts.zoho.jp", "ca": "https://accounts.zohocloud.ca",
    "sa": "https://accounts.zoho.sa", "uk": "https://accounts.zoho.uk",
}
API_BY_DC = {
    "us": "https://www.zohoapis.com", "eu": "https://www.zohoapis.eu",
    "in": "https://www.zohoapis.in", "au": "https://www.zohoapis.com.au",
    "jp": "https://www.zohoapis.jp", "ca": "https://www.zohoapis.ca",
    "sa": "https://www.zohoapis.sa", "uk": "https://www.zohoapis.uk",
}

# Least privilege: firmOS maps to existing Zoho contacts and never creates them during connection.
ZOHO_SCOPES = "ZohoBooks.bills.READ,ZohoBooks.bills.CREATE,ZohoBooks.invoices.READ,ZohoBooks.invoices.CREATE,ZohoBooks.contacts.READ,ZohoBooks.settings.READ"


def accounts_url(data_center: str | None = None) -> str:
    return ACCOUNTS_BY_DC.get((data_center or "in").lower(), ACCOUNTS_BY_DC["in"])


def api_domain(value: str | None, data_center: str | None = None) -> str:
    allowed = set(API_BY_DC.values())
    return value.rstrip("/") if value and value.rstrip("/") in allowed else API_BY_DC.get(
        (data_center or "in").lower(), API_BY_DC["in"],
    )


def get_authorize_url(state: str, redirect_uri: str = None) -> str:
    """Build OAuth authorize redirect URL. access_type=offline is REQUIRED."""
    callback_uri = redirect_uri or settings.zoho_redirect_uri
    params = {
        "client_id": settings.zoho_client_id,
        "response_type": "code",
        "access_type": "offline",  # REQUIRED — without this, no refresh token
        "prompt": "consent",
        "redirect_uri": callback_uri,
        "scope": ZOHO_SCOPES,
        "state": state,
    }
    return f"{ZOHO_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code_for_tokens(code: str, redirect_uri: str = None, data_center: str | None = None) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    import httpx
    callback_uri = redirect_uri or settings.zoho_redirect_uri

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{accounts_url(data_center)}/oauth/v2/token", data={
            "code": code,
            "client_id": settings.zoho_client_id,
            "client_secret": settings.zoho_client_secret,
            "redirect_uri": callback_uri,
            "grant_type": "authorization_code",
        })
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        raise ValueError(f"Zoho token error: {data['error']}")

    granted_scopes = str(data.get("scope") or ZOHO_SCOPES).replace(" ", ",")
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_in": data.get("expires_in", 3600),
        "token_type": data.get("token_type", "Zoho-oauthtoken"),
        "api_domain": api_domain(data.get("api_domain"), data.get("location") or data_center),
        "data_center": (data.get("location") or data_center or "in").lower(),
        "scopes": [scope for scope in granted_scopes.split(",") if scope],
    }


async def refresh_access_token(refresh_token: str, data_center: str | None = None) -> dict:
    """Use refresh token to get a new access token."""
    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{accounts_url(data_center)}/oauth/v2/token", data={
            "refresh_token": refresh_token,
            "client_id": settings.zoho_client_id,
            "client_secret": settings.zoho_client_secret,
            "grant_type": "refresh_token",
        })
        resp.raise_for_status()
        data = resp.json()

    return {
        "access_token": data["access_token"],
        "expires_in": data.get("expires_in", 3600),
        "api_domain": api_domain(data.get("api_domain"), data_center),
    }


async def revoke_token(refresh_token: str, data_center: str | None = None) -> None:
    """Revoke a refresh token."""
    import httpx

    async with httpx.AsyncClient() as client:
        await client.post(f"{accounts_url(data_center)}/oauth/v2/token/revoke", params={"token": refresh_token})
