"""Gemini document extraction with typed, non-invented failures."""

import json
from core.money import paise_to_decimal

from core.config import settings
from core.logging import log
from extraction.shared import (
    compute_overall_confidence as _compute_overall_confidence,
    confidence_level as _confidence_level,
    UNTRUSTED_DOCUMENT_RULES,
)
from extraction.result import ExtractionResult, ExtractionStatus

EXTRACTION_PROMPT = """You are a document extraction system for Indian tax compliance.
Extract fields from this document.

Return a JSON object with EXACTLY these keys:
{
  "doc_kind": "string - MUST BE ONE OF: VENDOR_BILL, SALES_INVOICE, RECEIPT, PAYMENT, JOURNAL",
  "vendor_name": "string (for bills/invoices, the other party's name)",
  "vendor_gstin": "string - 15-char GSTIN if visible, else empty string",
  "invoice_number": "string",
  "invoice_date": "string - DD/MM/YYYY format",
  "taxable_amount_paise": integer (e.g. 1500000 for ₹15,000.00),
  "cgst_paise": integer,
  "sgst_paise": integer,
  "igst_paise": integer (0 if intra-state),
  "total_paise": integer,
  "line_items": [{"desc": "string", "hsn": "string or null", "qty": 1, "rate_paise": integer, "amount_paise": integer}],
  "evidence": {"field_key": {"page": 1, "region": {"x": 0, "y": 0, "w": 0, "h": 0}, "text": "visible source text"}},
  "confidence": number between 0.0 and 1.0
}

Rules:
- Money is ALWAYS integer paise (multiply rupees by 100). Example: ₹1,407.20 = 140720.
- If a field is not visible, use empty string "" for strings, 0 for numbers.
- confidence should reflect how clearly we can read the document.
- GSTIN format: 2-digit state + 5-char PAN + 4 digits + 1 char + 1 char + Z + 1 char.
- Be concise and direct in your reasoning. Do not repeat text or get stuck in a loop.
- Return ONLY the JSON object. No markdown fencing. No explanation."""


__all__ = ["GeminiExtractor", "extract_with_gemini"]


async def _call_gemini(image_bytes: bytes, mime_type: str, model_name: str) -> dict:
    """Make a single Gemini API call. Returns parsed dict or raises."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)

    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            f"{EXTRACTION_PROMPT}\n\n{UNTRUSTED_DOCUMENT_RULES}",
        ],
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )

    raw_text = (response.text or "").strip()
    if not raw_text:
        raise RuntimeError("EMPTY_PROVIDER_RESULT")
    # Strip markdown fencing if model wraps it
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(raw_text)


class GeminiExtractor:
    """Extractor implementation using Google AI Studio Gemini API.

    Confidence escalation: if primary model gives REVIEW or LOW,
    automatically re-extract once with the escalation model and keep the better result.
    """

    async def extract(self, image_bytes: bytes, mime_type: str) -> ExtractionResult:
        if mime_type not in {"application/pdf", "image/jpeg", "image/png", "image/webp"}:
            return ExtractionResult.failure(ExtractionStatus.UNSUPPORTED, "UNSUPPORTED_MIME", "This document type is not supported.", "gemini")
        if not settings.gemini_api_key or settings.gemini_api_key.startswith(("your_", "dummy_")):
            return ExtractionResult.failure(ExtractionStatus.PROVIDER_ERROR, "API_KEY_MISSING", "Gemini extraction is not configured.", "gemini")

        try:
            # Primary extraction (cheap model)
            primary = await _call_gemini(image_bytes, mime_type, settings.model_primary)
            primary["source"] = "gemini_primary"
            primary_conf = _compute_overall_confidence(primary)
            primary["confidence"] = primary_conf
            primary_level = _confidence_level(primary_conf)
            primary_result = ExtractionResult.from_fields(primary, "gemini_primary", primary_conf)
            if not primary_result.succeeded:
                return primary_result

            log.info(
                "extraction_primary_complete",
                model=settings.model_primary,
                confidence=primary_conf,
                level=primary_level,
            )

            # If HIGH confidence, we're done — no need to burn tokens on escalation
            if primary_level == "HIGH":
                return primary_result

            # Escalate: re-extract with better model
            log.info("extraction_escalating", reason=primary_level, model=settings.model_escalate)
            try:
                escalated = await _call_gemini(image_bytes, mime_type, settings.model_escalate)
                escalated["source"] = "gemini_escalated"
                escalated_conf = _compute_overall_confidence(escalated)
                escalated["confidence"] = escalated_conf
                escalated_result = ExtractionResult.from_fields(escalated, "gemini_escalated", escalated_conf)

                log.info(
                    "extraction_escalated_complete",
                    model=settings.model_escalate,
                    confidence=escalated_conf,
                )

                # Keep whichever has higher confidence
                if escalated_result.succeeded and escalated_conf >= primary_conf:
                    return escalated_result
                return primary_result

            except Exception as esc_exc:
                # Escalation failed — return primary (it's still better than nothing)
                log.error("extraction_escalation_failed", error=str(esc_exc))
                return primary_result

        except json.JSONDecodeError:
            return ExtractionResult.failure(ExtractionStatus.INVALID_SCHEMA, "MALFORMED_JSON", "Gemini returned malformed JSON.", "gemini")
        except Exception as exc:
            reason_code = "EMPTY_PROVIDER_RESULT" if str(exc) == "EMPTY_PROVIDER_RESULT" else "GEMINI_REQUEST_FAILED"
            log.error("extraction_failed", provider="gemini", reason_code=reason_code)
            return ExtractionResult.failure(ExtractionStatus.PROVIDER_ERROR, reason_code, "Gemini extraction could not complete.", "gemini")


# Backwards compatibility — callers that import extract_with_gemini directly
async def extract_with_gemini(file_bytes: bytes, file_type: str) -> dict:
    """Legacy wrapper. Use get_extractor().extract() for new code."""
    mime = "application/pdf" if file_type == "pdf" else "image/jpeg"
    extractor = GeminiExtractor()
    result = await extractor.extract(file_bytes, mime)
    if not result.succeeded:
        return {
            "extraction_status": result.status,
            "reason_code": result.reason_code,
            "reason_message": result.reason_message,
        }
    raw = result.fields

    # Convert paise fields back to rupee strings for backwards compat with extractor.py
    return {
        "vendor_name": raw.get("vendor_name", ""),
        "vendor_gstin": raw.get("vendor_gstin", ""),
        "invoice_number": raw.get("invoice_number", ""),
        "invoice_date": raw.get("invoice_date", ""),
        "taxable_amount": str(paise_to_decimal(int(raw.get("taxable_amount_paise", 0)))),
        "cgst": str(paise_to_decimal(int(raw.get("cgst_paise", 0)))),
        "sgst": str(paise_to_decimal(int(raw.get("sgst_paise", 0)))),
        "igst": str(paise_to_decimal(int(raw.get("igst_paise", 0)))),
        "total": str(paise_to_decimal(int(raw.get("total_paise", 0)))),
        "line_items": [
            {
                "desc": item.get("desc", ""),
                "hsn": item.get("hsn"),
                "qty": item.get("qty", 0),
                "rate": str(paise_to_decimal(int(item.get("rate_paise", 0)))),
                "amount": str(paise_to_decimal(int(item.get("amount_paise", 0)))),
            }
            for item in raw.get("line_items", [])
        ],
        "confidence": raw.get("confidence", 0.5),
        "source": raw.get("source", "unknown"),
    }
