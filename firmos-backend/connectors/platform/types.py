"""Canonical connector requests and results; provider dictionaries stop here."""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class ResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    NO_DATA = "NO_DATA"
    UNSUPPORTED = "UNSUPPORTED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_MAPPING = "INVALID_MAPPING"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    AMBIGUOUS_RESULT = "AMBIGUOUS_RESULT"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(frozen=True)
class Cursor:
    value: str | None = None


@dataclass(frozen=True)
class Scope:
    client_id: str | None = None
    period: str | None = None


@dataclass(frozen=True)
class ConnectorResult(Generic[T]):
    status: ResultStatus
    data: T | None = None
    next_cursor: Cursor | None = None
    reason_code: str = ""
    retry_after_seconds: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalObject:
    object_type: str
    provider_id: str
    values: dict[str, Any]
    provider_version: str | None = None


@dataclass(frozen=True)
class ApprovedAction:
    id: str
    operation: str
    payload: dict[str, Any]
    payload_hash: str
    correlation_id: str


@dataclass(frozen=True)
class ExecutionAttempt:
    number: int
    idempotency_key: str
