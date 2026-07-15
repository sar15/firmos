"""Extractor protocol and configured implementation lookup."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from extraction.result import ExtractionResult


@runtime_checkable
class Extractor(Protocol):
    """Extract document fields or return a typed failure without fields."""

    async def extract(self, image_bytes: bytes, mime_type: str) -> ExtractionResult:
        ...


def get_extractor() -> Extractor:
    """Factory — returns the configured extractor. One-line swap via env var."""
    from core.config import settings

    kind = settings.extractor_type.lower()

    if kind == "gemini":
        from extraction.gemini import GeminiExtractor
        return GeminiExtractor()
    elif kind == "sarvam":
        from extraction.sarvam import SarvamExtractor
        return SarvamExtractor()
    # Future: elif kind == "selfhosted": from extraction.selfhosted import SelfHostedExtractor; return SelfHostedExtractor()
    else:
        from extraction.gemini import GeminiExtractor
        return GeminiExtractor()
