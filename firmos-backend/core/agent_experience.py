"""Safe, read-only views over persistent finance actions."""

import json
from collections.abc import Mapping
from typing import Any


EXCEPTION_PRIORITY = {
    "AUTH_EXPIRED": 1,
    "DEAD_LETTER": 2,
    "NEEDS_REVIEW": 3,
    "NEEDS_INPUT": 4,
    "FAILED": 5,
}

RUN_STAGES = (
    "QUEUED",
    "CLAIMED",
    "EXECUTING",
    "PROVIDER_ACCEPTED",
    "VERIFYING",
    "SUCCEEDED",
)

VISIBLE_FIELDS = (
    "invoice_number",
    "date",
    "vendor_name",
    "party_ledger",
    "purchase_ledger",
    "reference_number",
    "tally_company",
    "taxable_amount_paise",
    "cgst_paise",
    "sgst_paise",
    "igst_paise",
    "total_paise",
)


def _value(row: Mapping[str, Any], name: str, default=None):
    value = row.get(name, default)
    return default if value is None else value


def _payload(row: Mapping[str, Any]) -> dict[str, Any]:
    value = _value(row, "payload", {})
    return json.loads(value) if isinstance(value, str) else dict(value)


def _source_ids(row: Mapping[str, Any], payload: dict[str, Any]) -> list[str]:
    values = [
        _value(row, "document_id"),
        payload.get("source_document_id"),
        payload.get("source_id"),
        *(payload.get("input_source_ids") or []),
    ]
    return list(dict.fromkeys(str(value) for value in values if value))


def _dependencies(row: Mapping[str, Any]) -> list[str]:
    missing = _value(row, "missing_mappings", [])
    if isinstance(missing, str):
        missing = json.loads(missing)
    return [str(value) for value in missing]


def action_view(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the typed plan, diff, and recovery view used by the UI."""
    payload = _payload(row)
    operation = str(row["operation"])
    status = str(row["status"])
    provider = str(row["provider"])
    after = {key: payload[key] for key in VISIBLE_FIELDS if key in payload}
    action_id = str(row["id"])
    dependencies = _dependencies(row)
    active_index = RUN_STAGES.index(status) if status in RUN_STAGES else -1
    run_timeline = [
        {
            "stage": stage,
            "state": (
                "complete"
                if active_index >= 0 and index < active_index
                else "complete"
                if stage == "SUCCEEDED" and status == "SUCCEEDED"
                else "active"
                if index == active_index
                else "pending"
            ),
        }
        for index, stage in enumerate(RUN_STAGES)
    ]
    return {
        "id": action_id,
        "client_id": str(row["client_id"]),
        "provider": provider,
        "operation": operation,
        "status": status,
        "payload_hash": str(row["payload_hash"]),
        "risk_level": str(_value(row, "risk_level", "HIGH")),
        "correlation_id": str(_value(row, "correlation_id", "")),
        "external_reference_id": _value(row, "external_reference_id"),
        "created_at": str(_value(row, "created_at", "")),
        "updated_at": str(_value(row, "updated_at", "")),
        "plan_step": {
            "operation_key": operation,
            "client_id": str(row["client_id"]),
            "period": str(payload.get("period", "")),
            "input_source_ids": _source_ids(row, payload),
            "required_capability": operation,
            "read_write_risk": "WRITE_HIGH",
            "expected_output": f"Verified {provider} provider object",
            "approval_policy": "EXPLICIT_CA_APPROVAL",
            "dependencies": dependencies,
            "rollback_recovery": (
                "Cancel before claim; after provider acceptance use read-back recovery"
            ),
        },
        "financial_diff": {
            "kind": "NEW_OBJECT",
            "before": None,
            "after": after,
            "taxes": {
                key: after[key]
                for key in ("cgst_paise", "sgst_paise", "igst_paise")
                if key in after
            },
            "total_paise": after.get("total_paise"),
            "evidence_ids": _source_ids(row, payload),
        },
        "run_timeline": run_timeline,
        "disabled_reason": (
            None
            if status == "AWAITING_APPROVAL"
            else f"Action is {status.lower().replace('_', ' ')}"
        ),
    }


def exception_view(action: dict[str, Any]) -> dict[str, Any] | None:
    status = action["status"]
    if status not in EXCEPTION_PRIORITY:
        return None
    recovery = {
        "AUTH_EXPIRED": "Reconnect the provider, then retry.",
        "DEAD_LETTER": "Open the run and review the last failed attempt.",
        "NEEDS_REVIEW": "Compare the provider read-back with the approved draft.",
        "NEEDS_INPUT": "Supply the missing evidence or mapping.",
        "FAILED": "Review the failure reason before retrying.",
    }[status]
    return {
        "action_id": action["id"],
        "status": status,
        "priority": EXCEPTION_PRIORITY[status],
        "operation": action["operation"],
        "recovery_action": recovery,
        "correlation_id": action["correlation_id"],
    }
