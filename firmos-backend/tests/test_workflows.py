"""Tests for LangGraph workflows — proving interrupt() behavior and audit logs."""

import pytest
from langgraph.checkpoint.memory import MemorySaver

from workflows.graphs import (
    build_t1_workflow,
    build_t4_workflow,
    build_t5_workflow,
)
from extraction.result import ExtractionResult


class _OwnedRunConnection:
    def __init__(self, row):
        self.row = row

    async def fetchrow(self, *_args):
        return self.row


class _OwnedRunPool:
    def __init__(self, row):
        self.connection = _OwnedRunConnection(row)

    def acquire(self):
        from api.deps import _BorrowedConnection
        return _BorrowedConnection(self.connection)


def _install_valid_extractor(monkeypatch):
    class ValidExtractor:
        async def extract(self, *_args):
            return ExtractionResult.from_fields({
                "doc_kind": "PURCHASE_BILL",
                "vendor_name": "Verified supplier",
                "vendor_gstin": "27ABCDE1234F1Z5",
                "invoice_number": "INV-1",
                "invoice_date": "2026-07-01",
                "total_paise": 1180000,
                "taxable_amount_paise": 1000000,
                "cgst_paise": 90000,
                "sgst_paise": 90000,
                "igst_paise": 0,
                "line_items": [{"desc": "Consulting", "amount": 10000}],
            }, "test", 0.95)

    monkeypatch.setattr("extraction.base.get_extractor", lambda: ValidExtractor())


@pytest.mark.asyncio
async def test_t1_workflow_interrupt_and_resume(monkeypatch):
    """T1 vendor bill: runs to review_gate, pauses, resumes on approval.

    The legacy workflow must stop at the immutable finance-action boundary;
    it can never write directly to Zoho.
    """
    _install_valid_extractor(monkeypatch)
    graph = build_t1_workflow()
    checkpointer = MemorySaver()
    app = graph.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "thread-1"}}
    initial_state = {"document_id": "doc-123", "audit_entries": []}

    # 1. Run until first interrupt
    await app.ainvoke(initial_state, config)

    # Should pause at review_gate
    state = app.get_state(config)
    assert state.next == ("review_gate",)

    val = state.values
    assert val["status"] == "VALIDATED"
    assert len(val["audit_entries"]) == 2
    assert val["audit_entries"][0]["action"] == "DOCUMENT_EXTRACTED"

    # 2. Resume with approval using Command
    from langgraph.types import Command
    await app.ainvoke(Command(resume={"approved": True}), config)

    val = app.get_state(config).values
    assert val.get("status") == "NEEDS_ACTION_APPROVAL"
    assert val.get("ledger_ref") is None
    # 3rd audit entry: human approved
    assert len(val["audit_entries"]) == 3
    assert val["audit_entries"][2]["action"] == "HUMAN_APPROVED"


@pytest.mark.asyncio
async def test_t1_workflow_rejection(monkeypatch):
    """T1 vendor bill: if rejected, doesn't post to books."""
    _install_valid_extractor(monkeypatch)
    graph = build_t1_workflow()
    app = graph.compile(checkpointer=MemorySaver())

    config = {"configurable": {"thread_id": "thread-2"}}
    initial_state = {"document_id": "doc-456", "audit_entries": []}

    await app.ainvoke(initial_state, config)

    # Resume with rejection
    from langgraph.types import Command
    await app.ainvoke(Command(resume={"approved": False}), config)

    val = app.get_state(config).values
    assert val.get("status") == "REJECTED"
    assert "ledger_ref" not in val


@pytest.mark.asyncio
async def test_t4_workflow_fails_without_api_server():
    """T4 GSTR-3B: compute step raises RuntimeError without a running API server.

    This proves we removed the silent fallback to hardcoded paise values.
    A CA must never see fake numbers.
    """
    graph = build_t4_workflow()
    app = graph.compile(checkpointer=MemorySaver())

    config = {"configurable": {"thread_id": "thread-3"}}
    initial_state = {"client_id": "cl-1", "audit_entries": []}

    # t4_compute calls compute_gst_summary with Database.pool which is None in unit tests
    # It MUST raise RuntimeError, not silently return hardcoded values
    with pytest.raises(RuntimeError, match="Cannot compute GSTR-3B"):
        await app.ainvoke(initial_state, config)

@pytest.mark.asyncio
async def test_t5_workflow_interrupt_and_resume_without_input():
    """T5 ITR: with no taxable_income_paise in state, MUST return NEEDS_INPUT.

    The old behavior fabricated tax on a hardcoded ₹15L and a fake ARN.
    The honest behavior refuses to compute without real Form 16 / 26AS data.
    """
    graph = build_t5_workflow()
    app = graph.compile(checkpointer=MemorySaver())

    config = {"configurable": {"thread_id": "thread-4"}}
    initial_state = {"client_id": "cl-2", "audit_entries": []}

    await app.ainvoke(initial_state, config)

    val = app.get_state(config).values
    # No taxable income in state → workflow refuses to fabricate
    assert val.get("status") == "NEEDS_INPUT"
    assert val.get("arn") is None  # Never fabricate an acknowledgement


@pytest.mark.asyncio
async def test_t5_workflow_with_real_input_does_not_fake_filing():
    """T5 ITR: with real income input, tax computes but filing is NOT_IMPLEMENTED.

    The tax engine (engines/tax.py) is real and tested. The portal filing is
    Phase 2 scope, so the file node returns NOT_IMPLEMENTED — never a fake ARN.
    """
    graph = build_t5_workflow()
    app = graph.compile(checkpointer=MemorySaver())

    config = {"configurable": {"thread_id": "thread-5"}}
    initial_state = {
        "client_id": "cl-2",
        "taxable_income_paise": 1500000_00,  # real input
        "regime": "NEW",
        "audit_entries": [],
    }

    await app.ainvoke(initial_state, config)

    val = app.get_state(config).values
    assert val.get("status") == "ITR_DRAFT_READY"
    assert "gstr3b_draft" in val  # tax engine produced a real draft

    # Resume with approval
    from langgraph.types import Command
    await app.ainvoke(Command(resume={"approved": True}), config)

    val = app.get_state(config).values
    # Filing is honestly NOT_IMPLEMENTED, never FILED with a fake ARN
    assert val.get("status") == "NOT_IMPLEMENTED"
    assert val.get("arn") is None
    assert val.get("error") is not None  # error message explains Phase 2 scope


@pytest.mark.asyncio
async def test_workflow_state_requires_owned_run():
    from fastapi import HTTPException
    from api.deps import FirmContext
    from api.routes.workflows import _owned_thread

    firm = FirmContext("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "firm-1", "OWNER")
    with pytest.raises(HTTPException) as error:
        await _owned_thread(_OwnedRunPool(None), "t1", "foreign-thread", firm)
    assert error.value.status_code == 404

    owned = await _owned_thread(
        _OwnedRunPool({"storage_thread_id": "firm-1:user-1:thread-1"}),
        "t1", "thread-1", firm,
    )
    assert owned == "firm-1:user-1:thread-1"
