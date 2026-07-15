"""Redact sensitive evidence before it reaches logs or error reporting."""
import re
import logging
from collections.abc import Mapping
from typing import Any

_SENSITIVE_KEYS = (
    "token", "secret", "password", "authorization", "otp", "pan", "gstin",
    "bank", "account", "invoice", "image", "file", "payload", "response", "content",
    "document", "evidence", "raw", "data",
)
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_BEARER = re.compile(r"(?i)(bearer\s+)[^\s,;]+")
_JWT = re.compile(r"\beyJ[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+){2}\b")
_KEY_VALUE = re.compile(
    r"(?i)((?:token|secret|password|otp|authorization|pan|gstin|bank_account)\s*[:=]\s*)[^,;\s}]+"
)


def redact_text(value: str) -> str:
    """Remove recognizable credentials and PANs from unstructured text."""
    value = _PAN.sub("[REDACTED_PAN]", value)
    value = _BEARER.sub(r"\1[REDACTED]", value)
    value = _JWT.sub("[REDACTED_TOKEN]", value)
    return _KEY_VALUE.sub(r"\1[REDACTED]", value)


def redact(value: Any, key: str = "") -> Any:
    """Return a safe copy for JSON logs, Sentry, and exception metadata."""
    if any(part in key.lower() for part in _SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {str(item_key): redact(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list | tuple):
        return [redact(item, key) for item in value]
    return value


def redact_log_event(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return redact(event_dict)


def redact_sentry_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    return redact(event)


class RedactingFilter(logging.Filter):
    """Protect standard-library log handlers as well as structlog output."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True
