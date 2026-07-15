"""Sarvam OCR path for scanned bank statements."""

from __future__ import annotations

import json

import httpx
from core.errors import AppError

from core.config import settings
from extraction.sarvam import digitize_to_md
from extraction.shared import untrusted_document_prompt


BANK_STATEMENT_PROMPT = """You are a bank statement parser for Indian bank statements.
Extract all transaction rows from the following markdown text of a bank statement.
Return a JSON array with date, description, amount_paise, txn_type,
running_balance_paise and ref_no. Return only JSON."""


async def extract_bank_statement_scanned(file_bytes: bytes) -> list[dict]:
    """Parse a scanned PDF without inventing transaction rows."""
    md_text = await digitize_to_md(file_bytes, "application/pdf")
    if not md_text:
        raise AppError("BANK_DIGITIZATION_EMPTY", "The scanned statement could not be read.", status_code=422,
                       user_action="Upload a clearer scan or a digital PDF.")
    async with httpx.AsyncClient(timeout=120.0) as http:
        response = await http.post(
            "https://api.sarvam.ai/v1/chat/completions",
            headers={"Content-Type": "application/json", "API-Subscription-Key": settings.sarvam_api_key},
            json={
                "model": "sarvam-30b",
                "messages": [
                    {"role": "system", "content": "Output only a valid JSON array."},
                    {"role": "user", "content": untrusted_document_prompt(BANK_STATEMENT_PROMPT, md_text)},
                ],
                "temperature": 0.1,
                "max_tokens": 4096,
                "reasoning_effort": None,
            },
        )
        response.raise_for_status()
    content = response.json()["choices"][0]["message"].get("content")
    if not content:
        raise AppError("BANK_EXTRACTION_EMPTY", "The statement parser returned no result.", status_code=503,
                       retryable=True, user_action="Retry the extraction.")
    try:
        rows = json.loads(content.strip().removeprefix("```json").removesuffix("```").strip())
    except json.JSONDecodeError as exc:
        raise AppError("BANK_EXTRACTION_INVALID", "The statement parser returned an invalid result.", status_code=503,
                       retryable=True, user_action="Retry the extraction.") from exc
    if not isinstance(rows, list):
        raise AppError("BANK_EXTRACTION_INVALID", "The statement parser returned an invalid result.", status_code=503,
                       retryable=True, user_action="Retry the extraction.")
    from api.routes.bank_statements import _parse_date
    return [
        {
            "txn_date": _parse_date(str(row.get("date", ""))),
            "description": str(row.get("description", "")).strip(),
            "amount": abs(int(row.get("amount_paise", 0))),
            "txn_type": "CREDIT" if str(row.get("txn_type", "")).upper() == "CREDIT" else "DEBIT",
            "running_balance": int(row.get("running_balance_paise", 0)),
            "ref_no": str(row.get("ref_no", "")).strip(),
        }
        for row in rows
    ]
