"""Tally Prime Office Bridge Daemon — firmOS.

This local daemon runs on the Chartered Accountant's office PC or server where
Tally Prime is active. It polls Tally for ledgers and transactions and pushes
them via HTTPS to the firmOS cloud backend (/api/tally/push).

Why standard library urllib instead of requests?
Ensures any office PC with Python 3.10+ can execute this sync daemon immediately
without needing pip installation or internet repository access.
"""

import os
import sys
import json
import time
import hashlib
import logging
import argparse
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from tally_client import (
    TallyConnectionError,
    TallyXmlError,
    fetch_tally_companies,
    fetch_tally_ledgers,
    fetch_tally_vouchers,
    build_purchase_voucher_xml,
    parse_tally_import_response,
    post_tally_xml,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tally_bridge.daemon")


class CloudPushError(Exception):
    """Raised when pushing synced data to the firmOS cloud API fails."""
    pass


def sync_idempotency_key(payload: Dict[str, Any]) -> str:
    """Key a Tally snapshot by business content, not collection metadata."""
    stable_payload = {
        key: value for key, value in payload.items()
        if key not in {"timestamp", "collected_at", "sent_at"}
    }
    canonical = json.dumps(stable_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def push_to_cloud(
    cloud_url: str,
    api_token: str,
    payload: Dict[str, Any],
    timeout: int = 30,
) -> Dict[str, Any]:
    """Push a JSON payload to the firmOS cloud backend over HTTPS.
    
    Why: Bridges the local desktop Tally instance to the SaaS Postgres DB
    with Bearer authentication and idempotency headers.
    """
    endpoint = cloud_url.rstrip("/") + "/api/tally/push"
    data_bytes = json.dumps(payload).encode("utf-8")
    
    # Collection timestamps change on a replay; business content does not.
    # Keeping those timestamps out of the key makes retrying a sync safe.
    idempotency_key = sync_idempotency_key(payload)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}",
        "X-Idempotency-Key": idempotency_key,
        "User-Agent": "firmOS-TallyBridge-Daemon/1.0",
    }
    
    request = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")
    
    try:
        logger.info("Pushing sync payload (%d bytes) to %s (idempotency: %s)", len(data_bytes), endpoint, idempotency_key)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            resp_body = response.read().decode("utf-8")
            if not resp_body:
                return {"status": "ok", "message": "Empty response body"}
            return json.loads(resp_body)
    except urllib.error.HTTPError as exc:
        err_text = exc.read().decode("utf-8", errors="replace")
        raise CloudPushError(f"Cloud API returned HTTP {exc.code}: {err_text}") from exc
    except urllib.error.URLError as exc:
        raise CloudPushError(f"Network error reaching cloud API at {endpoint}: {exc.reason}") from exc
    except Exception as exc:
        raise CloudPushError(f"Unexpected error during cloud push: {exc}") from exc


def run_sync_cycle(
    company_name: str,
    cloud_url: str,
    api_token: str,
    from_date: str,
    to_date: str,
    tally_host: str = "localhost",
    tally_port: int = 9000,
) -> Dict[str, Any]:
    """Execute a single full synchronization cycle for a specific Tally company.
    
    Why: Exports both ledgers (masters) and vouchers (transactions), wraps them
    in a canonical schema, and transmits to firmOS in a single atomic payload.
    """
    logger.info("Starting sync cycle for company '%s'", company_name)
    
    # Verify company is open in Tally
    companies = fetch_tally_companies(host=tally_host, port=tally_port)
    open_names = [c["name"] for c in companies]
    if company_name not in open_names:
        raise TallyConnectionError(
            f"Company '{company_name}' is not currently open in Tally Prime. "
            f"Open companies: {open_names}"
        )
        
    ledgers = fetch_tally_ledgers(company_name, host=tally_host, port=tally_port)
    vouchers = fetch_tally_vouchers(company_name, from_date, to_date, host=tally_host, port=tally_port)
    
    payload = {
        "sync_version": "1.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tally_company": company_name,
        "period": {"from_date": from_date, "to_date": to_date},
        "ledgers": ledgers,
        "vouchers": vouchers,
    }
    
    result = push_to_cloud(cloud_url, api_token, payload)
    logger.info("Sync cycle completed successfully: %s", result.get("message", "OK"))
    return result


def poll_and_execute_pending_writes(
    cloud_url: str,
    api_token: str,
    company_name: str,
    bridge_device_id: str,
    tally_host: str = "localhost",
    tally_port: int = 9000,
    enable_tally_write: bool = False,
) -> int:
    """Poll firmOS cloud for pending approved Tally write commands and execute them locally.

    PREREQUISITE GATES:
    Write execution is strictly disabled by default until Gate 1 (CA verification sign-off)
    and Gate 2 (Licensed TallyPrime non-Educational instance) are cleared.
    """
    if not enable_tally_write:
        logger.info(
            "Tally write execution is DISABLED (enable_tally_write=False). "
            "Gate 1 (CA sign-off) and Gate 2 (Licensed TallyPrime) must be satisfied before enabling."
        )
        return 0

    endpoint = cloud_url.rstrip("/") + "/api/bridge/actions/claim"
    req = urllib.request.Request(
        endpoint,
        data=json.dumps({"tally_company": company_name, "bridge_device_id": bridge_device_id}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            claim = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        logger.warning("Could not fetch pending write commands: %s", exc)
        return 0

    action = claim.get("action") if claim.get("claimed") else None
    if not action:
        return 0

    action_id = action["action_id"]
    result = {"correlation_id": action["correlation_id"], "bridge_device_id": bridge_device_id, "status": "FAILED"}
    try:
        if action["operation"] != "tally.write.purchase_voucher.create":
            raise TallyXmlError(f"Unsupported bridge operation: {action['operation']}")
        xml = build_purchase_voucher_xml(action["payload"], action_id, company_name)
        result.update(parse_tally_import_response(post_tally_xml(xml, host=tally_host, port=tally_port, timeout=30)))
        if result["status"] == "SUCCEEDED":
            # Tally confirmed this deterministic REMOTEID. Read-back resolves its GUID later.
            result["external_reference_id"] = action_id
    except Exception as exc:
        result["error_message"] = str(exc)

    result_url = cloud_url.rstrip("/") + f"/api/bridge/actions/{action_id}/result"
    res_req = urllib.request.Request(
        result_url,
        data=json.dumps(result).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(res_req, timeout=15)
        return 1 if result["status"] == "SUCCEEDED" else 0
    except Exception as exc:
        logger.error("Failed to report command result to cloud: %s", exc)
        return 0


def main():
    parser = argparse.ArgumentParser(description="firmOS Tally Prime Office Bridge Daemon")
    parser.add_argument("--company", required=True, help="Exact name of the Tally company to sync")
    parser.add_argument("--cloud-url", default=os.getenv("FIRMOS_CLOUD_URL", "http://localhost:8000"), help="firmOS backend API base URL")
    parser.add_argument("--api-token", default=os.getenv("FIRMOS_API_TOKEN", "dev_token_123"), help="firmOS API authentication token")
    parser.add_argument("--from-date", default="20240401", help="Start date in YYYYMMDD format (default: 20240401)")
    parser.add_argument("--to-date", default="20250331", help="End date in YYYYMMDD format (default: 20250331)")
    parser.add_argument("--tally-host", default="localhost", help="Tally Prime gateway host (default: localhost)")
    parser.add_argument("--tally-port", type=int, default=9000, help="Tally Prime gateway port (default: 9000)")
    parser.add_argument("--interval", type=int, default=3600, help="Poll interval in seconds for daemon mode (default: 3600 = 1 hour, 0 for one-shot)")
    parser.add_argument("--enable-tally-write", action="store_true", help="CAUTION: Enable write execution. Requires Gate 1 & Gate 2 clearance.")
    parser.add_argument("--device-id", default=os.getenv("FIRMOS_BRIDGE_DEVICE_ID"), required=not os.getenv("FIRMOS_BRIDGE_DEVICE_ID"), help="Registered bridge device ID")

    args = parser.parse_args()

    if args.interval <= 0:
        logger.info("Running one-shot synchronization...")
        try:
            run_sync_cycle(args.company, args.cloud_url, args.api_token, args.from_date, args.to_date, args.tally_host, args.tally_port)
            poll_and_execute_pending_writes(args.cloud_url, args.api_token, args.company, args.device_id, args.tally_host, args.tally_port, args.enable_tally_write)
            sys.exit(0)
        except Exception as exc:
            logger.error("One-shot sync failed: %s", exc)
            sys.exit(1)

    logger.info("Starting Tally Bridge Daemon (poll interval: %d seconds)...", args.interval)
    while True:
        try:
            run_sync_cycle(args.company, args.cloud_url, args.api_token, args.from_date, args.to_date, args.tally_host, args.tally_port)
            poll_and_execute_pending_writes(args.cloud_url, args.api_token, args.company, args.device_id, args.tally_host, args.tally_port, args.enable_tally_write)
        except Exception as exc:
            logger.error("Sync error during daemon cycle: %s", exc)
            logger.info("Will retry at next interval in %d seconds...", args.interval)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
