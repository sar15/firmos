from core.agent_experience import action_view, exception_view


def _row(status="AWAITING_APPROVAL"):
    return {
        "id": "action-1",
        "client_id": "client-1",
        "provider": "ZOHO_BOOKS",
        "operation": "zoho.write.purchase_bill.create",
        "status": status,
        "payload_hash": "a" * 64,
        "payload": {
            "invoice_number": "INV-7",
            "total_paise": 118000,
            "cgst_paise": 9000,
            "sgst_paise": 9000,
            "organization_id": "not-exposed-in-diff",
        },
        "risk_level": "HIGH",
        "correlation_id": "corr-1",
        "document_id": "doc-1",
        "missing_mappings": [],
    }


def test_action_view_contains_complete_typed_plan_and_safe_financial_diff():
    view = action_view(_row())
    step = view["plan_step"]
    assert step["operation_key"] == "zoho.write.purchase_bill.create"
    assert step["input_source_ids"] == ["doc-1"]
    assert step["approval_policy"] == "EXPLICIT_CA_APPROVAL"
    assert view["financial_diff"]["total_paise"] == 118000
    assert "organization_id" not in view["financial_diff"]["after"]
    assert view["disabled_reason"] is None


def test_exception_view_is_priority_orderable_and_has_recovery():
    exception = exception_view(action_view(_row("AUTH_EXPIRED")))
    assert exception["priority"] == 1
    assert "Reconnect" in exception["recovery_action"]
    assert exception_view(action_view(_row("SUCCEEDED"))) is None


def test_run_timeline_never_claims_future_stages_are_complete():
    timeline = action_view(_row("EXECUTING"))["run_timeline"]
    states = {item["stage"]: item["state"] for item in timeline}
    assert states["QUEUED"] == "complete"
    assert states["EXECUTING"] == "active"
    assert states["PROVIDER_ACCEPTED"] == "pending"
