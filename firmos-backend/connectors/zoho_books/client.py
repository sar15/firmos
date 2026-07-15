"""Pooled, bounded Zoho Books HTTP client."""
import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable

import httpx

from connectors.zoho_books.auth import ZOHO_API_BASE, refresh_access_token
from connectors.zoho_books.errors import ZohoError, error_from_response
from connectors.platform.types import ResultStatus
from core.security import decrypt_token

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_http: httpx.AsyncClient | None = None


def shared_http_client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=30, write=30, pool=10),
            limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
        )
    return _http


async def close_http_client() -> None:
    global _http
    if _http and not _http.is_closed:
        await _http.aclose()
    _http = None


class ZohoClient:
    def __init__(
        self,
        access_token: str,
        refresh_token_enc: bytes | None,
        organization_id: str,
        *,
        api_domain: str | None = None,
        http: httpx.AsyncClient | None = None,
        refresh: Callable[[], Awaitable[str]] | None = None,
    ):
        self._access_token = access_token
        self._refresh_token_enc = refresh_token_enc
        self._org_id = organization_id
        self._base = (api_domain.rstrip("/") + "/books/v3") if api_domain else ZOHO_API_BASE
        self._http = http or shared_http_client()
        self._refresh = refresh
        self._refresh_lock = asyncio.Lock()
        self._on_token_refresh = None

    def set_token_refresh_callback(self, callback) -> None:
        self._on_token_refresh = callback

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Zoho-oauthtoken {self._access_token}"}

    @property
    def organization_id(self) -> str:
        return self._org_id

    async def _renew(self, rejected_token: str | None = None) -> None:
        async with self._refresh_lock:
            if rejected_token and self._access_token != rejected_token:
                return
            if self._refresh:
                self._access_token = await self._refresh()
                return
            if not self._refresh_token_enc:
                raise error_from_response(401, {})
            tokens = await refresh_access_token(decrypt_token(self._refresh_token_enc))
            self._access_token = tokens["access_token"]
            if self._on_token_refresh:
                saved = self._on_token_refresh(self._access_token, tokens["expires_in"])
                if inspect.isawaitable(saved):
                    await saved

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        params = dict(kwargs.pop("params", {}))
        params["organization_id"] = self._org_id
        bill_json = kwargs.pop("bill_json", None)
        json_data = kwargs.pop("json_data", None)
        request = {"headers": self._headers(), "params": params, **kwargs}
        if bill_json is not None:
            request["data"] = {"JSONString": json.dumps(bill_json)}
        if json_data is not None:
            request["json"] = json_data
        rejected_token = self._access_token
        response = await self._http.request(method, f"{self._base}{path}", **request)
        if response.status_code == 401:
            await self._renew(rejected_token)
            request["headers"] = self._headers()
            response = await self._http.request(method, f"{self._base}{path}", **request)
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise ZohoError(ResultStatus.PROVIDER_UNAVAILABLE, "ZOHO_RESPONSE_TOO_LARGE", "Zoho response exceeded the safe size limit")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ZohoError(ResultStatus.PROVIDER_UNAVAILABLE, "ZOHO_INVALID_JSON", "Zoho returned an unreadable response") from exc
        if response.status_code >= 400 or payload.get("code") not in (None, 0, "0"):
            raise error_from_response(response.status_code, payload, response.headers.get("Retry-After"))
        return payload

    async def get(self, path: str, **kwargs) -> dict:
        return await self._request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> dict:
        return await self._request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs) -> dict:
        return await self._request("PUT", path, **kwargs)


async def get_organizations(access_token: str, api_domain: str | None = None) -> list[dict]:
    base = (api_domain.rstrip("/") + "/books/v3") if api_domain else ZOHO_API_BASE
    response = await shared_http_client().get(
        f"{base}/organizations", headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
    )
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ZohoError(ResultStatus.PROVIDER_UNAVAILABLE, "ZOHO_RESPONSE_TOO_LARGE", "Zoho response exceeded the safe size limit")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ZohoError(ResultStatus.PROVIDER_UNAVAILABLE, "ZOHO_INVALID_JSON", "Zoho returned an unreadable response") from exc
    if response.status_code >= 400:
        raise error_from_response(response.status_code, payload, response.headers.get("Retry-After"))
    return payload.get("organizations", [])
