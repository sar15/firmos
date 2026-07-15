"""Typed, non-invented outcomes for document extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ExtractionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNSUPPORTED = "UNSUPPORTED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INVALID_SCHEMA = "INVALID_SCHEMA"


SUCCESSFUL_STATUSES = {
    ExtractionStatus.SUCCESS,
    ExtractionStatus.PARTIAL,
    ExtractionStatus.LOW_CONFIDENCE,
}
REQUIRED_FIELDS = {
    "doc_kind", "vendor_name", "vendor_gstin", "invoice_number", "invoice_date",
    "taxable_amount_paise", "cgst_paise", "sgst_paise", "igst_paise",
    "total_paise", "line_items",
}


@dataclass(frozen=True)
class ExtractionResult:
    status: ExtractionStatus
    fields: dict[str, Any] = field(default_factory=dict)
    reason_code: str = ""
    reason_message: str = ""
    provider: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status in SUCCESSFUL_STATUSES

    @classmethod
    def failure(
        cls, status: ExtractionStatus, reason_code: str, reason_message: str, provider: str
    ) -> "ExtractionResult":
        return cls(status, reason_code=reason_code, reason_message=reason_message[:240], provider=provider)

    @classmethod
    def from_fields(cls, fields: object, provider: str, confidence: float) -> "ExtractionResult":
        if not isinstance(fields, dict) or not REQUIRED_FIELDS.issubset(fields):
            return cls.failure(ExtractionStatus.INVALID_SCHEMA, "REQUIRED_FIELDS_MISSING", "Provider returned an incomplete document schema.", provider)
        if not isinstance(fields.get("line_items"), list) or any(
            not isinstance(fields.get(key), int)
            for key in ("taxable_amount_paise", "cgst_paise", "sgst_paise", "igst_paise", "total_paise")
        ):
            return cls.failure(ExtractionStatus.INVALID_SCHEMA, "FIELD_TYPES_INVALID", "Provider returned invalid document field types.", provider)
        status = ExtractionStatus.SUCCESS if confidence >= 0.9 else (
            ExtractionStatus.PARTIAL if confidence >= 0.6 else ExtractionStatus.LOW_CONFIDENCE
        )
        safe_fields = dict(fields)
        safe_fields.update(source=provider, confidence=confidence)
        return cls(status, safe_fields, provider=provider)
