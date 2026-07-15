"""Safe, typed Zoho failure boundary."""
from dataclasses import dataclass
from uuid import uuid4

from connectors.platform.types import ConnectorResult, ResultStatus


@dataclass
class ZohoError(Exception):
    status: ResultStatus
    reason_code: str
    safe_message: str
    retry_after_seconds: int | None = None
    correlation_id: str = ""

    def __post_init__(self) -> None:
        self.correlation_id = self.correlation_id or str(uuid4())
        super().__init__(self.safe_message)

    def result(self) -> ConnectorResult:
        return ConnectorResult(
            self.status,
            reason_code=self.reason_code,
            retry_after_seconds=self.retry_after_seconds,
            details={"correlation_id": self.correlation_id},
        )


def error_from_response(status_code: int, payload: dict, retry_after: str | None = None) -> ZohoError:
    provider_code = str(payload.get("code", "UNKNOWN"))
    if status_code == 401:
        return ZohoError(ResultStatus.AUTH_EXPIRED, "ZOHO_AUTH_EXPIRED", "Zoho authorization expired")
    if status_code == 404:
        return ZohoError(ResultStatus.NO_DATA, "ZOHO_NOT_FOUND", "Zoho object was not found")
    if status_code == 429:
        seconds = int(retry_after) if retry_after and retry_after.isdigit() else 60
        return ZohoError(ResultStatus.RATE_LIMITED, "ZOHO_RATE_LIMITED", "Zoho rate limit reached", seconds)
    if status_code >= 500:
        return ZohoError(ResultStatus.PROVIDER_UNAVAILABLE, "ZOHO_PROVIDER_UNAVAILABLE", "Zoho is temporarily unavailable")
    return ZohoError(ResultStatus.INVALID_PAYLOAD, f"ZOHO_{provider_code}", "Zoho rejected the request")
