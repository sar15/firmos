"""WhatsApp Business API — Embedded Signup v4 + webhook handling.

Inbound: client sends bill photo → extract → PENDING_REVIEW document.
Outbound: send approval notification templates.
"""
from __future__ import annotations

import hmac
import hashlib
import json

import httpx

from core.config import settings
from core.logging import log


WHATSAPP_API_BASE = "https://graph.facebook.com/v21.0"


async def send_template_message(
    phone_number_id: str,
    to: str,
    template_name: str,
    language_code: str = "en",
    parameters: list[dict] | None = None,
) -> dict:
    """Send a WhatsApp template message (for approval notifications)."""
    access_token = settings.whatsapp_app_secret  # ponytail: use page token from connections table when wired

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }

    if parameters:
        payload["template"]["components"] = [
            {"type": "body", "parameters": parameters}
        ]

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"{WHATSAPP_API_BASE}/{phone_number_id}/messages",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def download_media(media_id: str) -> bytes:
    """Download media (bill photo) from WhatsApp.
    Two-step: get URL from media_id, then download the file."""
    access_token = settings.whatsapp_app_secret

    async with httpx.AsyncClient() as http:
        # Step 1: Get download URL
        resp = await http.get(
            f"{WHATSAPP_API_BASE}/{media_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        url = resp.json().get("url", "")

        # Step 2: Download the file
        resp = await http.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.content


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Meta webhook signature (X-Hub-Signature-256 header)."""
    expected = hmac.new(
        settings.whatsapp_app_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def parse_inbound_message(body: dict) -> dict | None:
    """Parse a webhook payload to extract image message data.
    Returns {from, media_id, mime_type} or None if not an image message."""
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return None

        msg = messages[0]
        if msg.get("type") != "image":
            return None

        return {
            "from": msg.get("from", ""),
            "media_id": msg["image"]["id"],
            "mime_type": msg["image"].get("mime_type", "image/jpeg"),
        }
    except (KeyError, IndexError):
        return None
