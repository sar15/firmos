"""One-page-at-a-time Zoho paginator with durable cursor semantics."""
from connectors.platform.types import ConnectorResult, Cursor, ResultStatus

PER_PAGE = 200
MAX_PAGES = 1000


async def fetch_page(client, path: str, key: str, cursor: Cursor, params: dict | None = None) -> ConnectorResult[list[dict]]:
    page = int(cursor.value or "1")
    if page < 1 or page > MAX_PAGES:
        return ConnectorResult(ResultStatus.INVALID_PAYLOAD, reason_code="ZOHO_CURSOR_OUT_OF_RANGE")
    response = await client.get(path, params={**(params or {}), "page": page, "per_page": PER_PAGE})
    rows = response.get(key, [])
    if not isinstance(rows, list):
        return ConnectorResult(ResultStatus.PROVIDER_UNAVAILABLE, reason_code="ZOHO_INVALID_LIST_RESPONSE")
    has_more = bool(response.get("page_context", {}).get("has_more_page"))
    status = ResultStatus.PARTIAL if has_more else (ResultStatus.SUCCESS if rows else ResultStatus.NO_DATA)
    return ConnectorResult(status, rows, Cursor(str(page + 1)) if has_more else None)
