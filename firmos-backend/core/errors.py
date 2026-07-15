"""Safe typed API errors shared by routes and exception handlers."""
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ErrorEnvelope:
    code: str
    message: str
    correlation_id: str
    retryable: bool = False
    user_action: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def asdict(self) -> dict[str, Any]:
        return asdict(self)


class AppError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400,
                 retryable: bool = False, user_action: str = "", details: dict | None = None):
        super().__init__(message)
        self.code, self.safe_message, self.status_code = code, message, status_code
        self.retryable, self.user_action = retryable, user_action
        self.details = details or {}
