"""Bank reconciliation workflow nodes."""
from core.logging import log
from workflows.state import WorkflowState


async def reconcile(state: WorkflowState) -> dict:
    from engines.reconcile import reconcile as run_reconcile
    from models.schemas import ReconLine

    log.info("t2_reconcile", client_id=state.get("client_id"))
    source = [item if isinstance(item, ReconLine) else ReconLine(**item) for item in state.get("bank_source_lines", [])]
    target = [item if isinstance(item, ReconLine) else ReconLine(**item) for item in state.get("books_target_lines", [])]
    result = run_reconcile(source, target)
    summary = result.summary
    return {
        "status": "RECONCILED", "recon_result": result.model_dump(),
        "audit_entries": state.get("audit_entries", []) + [{
            "actor": "firmOS", "action": "STEP_COMPLETED",
            "description": f"Bank reconciliation: {summary.autoMatched} auto, {summary.suggested} suggested, {summary.unmatched} unmatched",
        }],
    }


def unmatched_gate(state: WorkflowState) -> dict:
    from langgraph.types import interrupt

    if interrupt({"reason": "Review unmatched bank entries"}).get("approved"):
        return {"status": "ENTRIES_APPROVED", "audit_entries": state.get("audit_entries", []) + [{"actor": "HUMAN", "action": "HUMAN_APPROVED", "description": "Approved unmatched bank entries"}]}
    return {}
