"""Sarvam extraction with typed, non-invented failures."""

from __future__ import annotations
import json
import re
import uuid
import asyncio
import httpx
import logging
from typing import Dict, Any

from core.config import settings
from core.logging import log
from extraction.shared import (
    compute_overall_confidence as _compute_overall_confidence,
    confidence_level as _confidence_level,
    untrusted_document_prompt,
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

SARVAM_MAX_POLLS = 15
SARVAM_POLL_INTERVAL = 2.0

logger = logging.getLogger(__name__)


def _extract_json_from_text(text: str) -> dict | None:
    """Try to find and parse a JSON object from arbitrary text (e.g. reasoning_content)."""
    if not text:
        return None
    # Find the first { ... } block that looks like our schema
    # Use a greedy approach: find first { and last }
    start = text.find("{")
    if start == -1:
        return None
    # Find matching closing brace by counting braces
    depth = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                # Don't break — keep looking for a LATER, more complete JSON block
    if end == -1:
        return None
    # Try to parse the last complete JSON block
    # Walk backwards to find the last valid JSON
    candidates = []
    depth = 0
    block_end = -1
    for i in range(len(text) - 1, -1, -1):
        if text[i] == "}":
            if depth == 0:
                block_end = i
            depth += 1
        elif text[i] == "{":
            depth -= 1
            if depth == 0 and block_end != -1:
                candidates.append(text[i:block_end + 1])
                break
    # Also try first-to-last approach
    candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
            # Validate it has our expected keys
            if "vendor_name" in obj or "invoice_number" in obj:
                return obj
        except (json.JSONDecodeError, ValueError):
            continue
    return None


async def digitize_to_md(image_bytes: bytes, mime_type: str) -> str:
    """Run Sarvam Vision (document intelligence) to convert image/PDF to markdown text."""
    from sarvamai import AsyncSarvamAI
    client = AsyncSarvamAI(api_subscription_key=settings.sarvam_api_key)

    # 1. Initialize digitisation job
    res_init = await client.document_intelligence.initialise(job_parameters={"output_format": "md"})
    job_id = res_init.job_id

    if "pdf" in mime_type:
        file_ext = "pdf"
    elif "png" in mime_type:
        file_ext = "png"
    elif "jpeg" in mime_type or "jpg" in mime_type:
        file_ext = "jpg"
    else:
        file_ext = "jpg"

    filename = f"doc_{uuid.uuid4().hex[:8]}.{file_ext}"

    # 2. Get upload link
    res_ul = await client.document_intelligence.get_upload_links(job_id=job_id, files=[filename])
    url = res_ul.upload_urls[filename].file_url

    # 3. Upload file
    headers = {"x-ms-blob-type": "BlockBlob", "Content-Type": mime_type}
    async with httpx.AsyncClient(timeout=60.0) as http:
        put_resp = await http.put(url, content=image_bytes, headers=headers)
        put_resp.raise_for_status()

    # 4. Start job
    await client.document_intelligence.start(job_id=job_id)

    # 5. Poll for completion
    completed = False
    for _ in range(SARVAM_MAX_POLLS):
        await asyncio.sleep(SARVAM_POLL_INTERVAL)
        status_res = await client.document_intelligence.get_status(job_id=job_id)
        if status_res.job_state == "Completed":
            completed = True
            break
        elif status_res.job_state == "Failed":
            raise RuntimeError(f"Sarvam vision job failed: {status_res.error_message}")

    if not completed:
        raise RuntimeError("Sarvam vision job timed out")

    # 6. Get download link and fetch markdown
    dl = await client.document_intelligence.get_download_links(job_id=job_id)
    dl_url = list(dl.download_urls.values())[0].file_url

    import zipfile
    import io

    async with httpx.AsyncClient(timeout=60.0) as http:
        md_resp = await http.get(dl_url)
        md_resp.raise_for_status()

        # Sarvam returns a ZIP archive containing 'document.md'
        zip_data = io.BytesIO(md_resp.content)
        with zipfile.ZipFile(zip_data, 'r') as zf:
            md_filename = next((name for name in zf.namelist() if name.endswith(".md")), None)
            if not md_filename:
                raise RuntimeError("No markdown file found in Sarvam download archive")
            markdown_text = zf.read(md_filename).decode("utf-8")

    logger.info("Sarvam Vision OCR completed")
    return markdown_text


async def _run_sarvam_pipeline(image_bytes: bytes, mime_type: str) -> dict:
    markdown_text = await digitize_to_md(image_bytes, mime_type)

    # 7. Feed markdown to Sarvam Chat — reasoning DISABLED
    # WHY: sarvam-30b defaults to reasoning_effort="medium", which burns all 4096
    # tokens on hidden reasoning_content and produces content=None (finish_reason=length).
    # Setting reasoning_effort=null disables reasoning entirely → all tokens go to JSON output.
    system_msg = (
        "You are a JSON extraction API. Output ONLY a valid JSON object. "
        "No explanation, no markdown fencing."
    )
    user_msg = untrusted_document_prompt(EXTRACTION_PROMPT, markdown_text)

    async with httpx.AsyncClient(timeout=120.0) as http:
        resp = await http.post(
            "https://api.sarvam.ai/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "API-Subscription-Key": settings.sarvam_api_key,
            },
            json={
                "model": "sarvam-30b",
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.1,
                "max_tokens": 4096,
                "reasoning_effort": None,  # THE FIX: disable reasoning to prevent token exhaustion
            },
        )
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"].get("content")
    finish_reason = data["choices"][0].get("finish_reason", "unknown")

    logger.info(f"Sarvam Chat: finish_reason={finish_reason}, content_len={len(content) if content else 0}")

    if content:
        raw_text = content.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw_text)

    # Safety net: try parsing from reasoning_content if it somehow still exists
    reasoning = data["choices"][0]["message"].get("reasoning_content", "")
    if reasoning:
        parsed = _extract_json_from_text(reasoning)
        if parsed:
            logger.info("Extracted structured JSON from provider response")
            return parsed

    raise RuntimeError(f"Sarvam Chat returned no content (finish_reason={finish_reason})")


class SarvamExtractor:
    """Extractor implementation using Sarvam AI API."""

    async def extract(self, image_bytes: bytes, mime_type: str) -> ExtractionResult:
        if mime_type not in {"application/pdf", "image/jpeg", "image/png"}:
            return ExtractionResult.failure(ExtractionStatus.UNSUPPORTED, "UNSUPPORTED_MIME", "This document type is not supported.", "sarvam")
        if not settings.sarvam_api_key or settings.sarvam_api_key.startswith(("your_", "dummy_")):
            return ExtractionResult.failure(ExtractionStatus.PROVIDER_ERROR, "API_KEY_MISSING", "Sarvam extraction is not configured.", "sarvam")

        try:
            primary = await _run_sarvam_pipeline(image_bytes, mime_type)
            primary["source"] = "sarvam_ai"
            
            # Auto-compute total from line items if model returned 0
            if not primary.get("total_paise"):
                computed = sum(item.get("amount_paise", 0) for item in primary.get("line_items", []))
                if computed > 0:
                    primary["total_paise"] = computed
            if not primary.get("taxable_amount_paise"):
                primary["taxable_amount_paise"] = primary.get("total_paise", 0)
            
            primary_conf = _compute_overall_confidence(primary)
            primary["confidence"] = primary_conf
            result = ExtractionResult.from_fields(primary, "sarvam_ai", primary_conf)
            if not result.succeeded:
                return result

            log.info(
                "extraction_sarvam_complete",
                model="sarvam-30b",
                vendor=primary.get("vendor_name", "?"),
                invoice=primary.get("invoice_number", "?"),
                confidence=primary_conf,
            )
            return result
        except json.JSONDecodeError:
            return ExtractionResult.failure(ExtractionStatus.INVALID_SCHEMA, "MALFORMED_JSON", "Sarvam returned malformed JSON.", "sarvam")
        except Exception as exc:
            reason_code = "EMPTY_PROVIDER_RESULT" if "no content" in str(exc).lower() else "SARVAM_REQUEST_FAILED"
            log.error("extraction_failed", provider="sarvam", reason_code=reason_code)
            return ExtractionResult.failure(ExtractionStatus.PROVIDER_ERROR, reason_code, "Sarvam extraction could not complete.", "sarvam")
