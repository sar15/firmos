from base64 import b64encode
from datetime import datetime, timedelta, timezone
import time
import uuid

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from starlette.requests import Request

from api.routes.tally_agent_auth import require_device
from core.device_signing import body_digest, signing_message, validate_public_key, verify_device_signature


def signed(body=b'{"ok":true}', timestamp="1784073600"):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    digest = body_digest(body)
    message = signing_message("POST", "/api/tally-agent/heartbeat", timestamp, "nonce-1", digest)
    return {
        "public_key": b64encode(public).decode(),
        "signature": b64encode(private.sign(message)).decode(),
        "method": "POST", "path": "/api/tally-agent/heartbeat",
        "timestamp": timestamp, "nonce": "nonce-1", "claimed_digest": digest,
        "body": body, "now": datetime.fromtimestamp(int(timestamp), tz=timezone.utc),
    }


def test_signed_device_request_accepts_exact_body():
    request = signed()
    validate_public_key(request["public_key"])
    verify_device_signature(**request)


def test_signed_device_request_rejects_tamper_and_stale_timestamp():
    request = signed()
    request["body"] = b'{"ok":false}'
    with pytest.raises(ValueError, match="DEVICE_BODY_TAMPERED"):
        verify_device_signature(**request)
    request = signed()
    request["now"] += timedelta(minutes=6)
    with pytest.raises(ValueError, match="DEVICE_TIMESTAMP_EXPIRED"):
        verify_device_signature(**request)


def test_signed_device_request_rejects_wrong_key():
    request = signed()
    other = signed()
    request["public_key"] = other["public_key"]
    with pytest.raises(ValueError, match="DEVICE_SIGNATURE_INVALID"):
        verify_device_signature(**request)


class FakeConnection:
    def __init__(self, row, nonce_result="new-nonce"):
        self.row, self.nonce_result = row, nonce_result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def transaction(self):
        return self

    async def fetchrow(self, *_args):
        return self.row

    async def fetchval(self, *_args):
        return self.nonce_result


class FakePool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return self.connection


def http_request(body: bytes, path="/api/tally-agent/heartbeat"):
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request({
        "type": "http", "method": "POST", "path": path, "headers": [],
        "query_string": b"", "scheme": "http", "server": ("test", 80),
        "client": ("test", 1),
    }, receive)


@pytest.mark.asyncio
@pytest.mark.parametrize("row", [None, {"firm_id": "other-firm"}])
async def test_device_dependency_rejects_revoked_or_wrong_firm(row):
    device_id = str(uuid.uuid4())
    with pytest.raises(HTTPException) as error:
        await require_device(
            http_request(b"{}"), FakePool(FakeConnection(row)), device_id, "firm-a",
            str(int(time.time())), "nonce", "0" * 64, "invalid",
        )
    assert error.value.detail == {"code": "DEVICE_BINDING_INVALID"}


@pytest.mark.asyncio
async def test_device_dependency_rejects_nonce_replay():
    device_id, installation_id = str(uuid.uuid4()), str(uuid.uuid4())
    request = signed(timestamp=str(int(time.time())))
    row = {
        "id": device_id, "firm_id": "firm-a", "client_id": "client-a",
        "installation_id": installation_id, "company_name": "Acme",
        "company_guid": "company-guid", "public_key": request["public_key"],
        "agent_version": "1.0.0",
    }
    with pytest.raises(HTTPException) as error:
        await require_device(
            http_request(request["body"]), FakePool(FakeConnection(row, None)),
            device_id, "firm-a", request["timestamp"], request["nonce"],
            request["claimed_digest"], request["signature"],
        )
    assert error.value.status_code == 409
    assert error.value.detail == {"code": "DEVICE_NONCE_REPLAY"}
