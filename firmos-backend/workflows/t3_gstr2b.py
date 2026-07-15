"""GSTR-2B evidence reconciliation workflow nodes."""
from core.logging import log
from workflows.state import WorkflowState


def fetch_2b(state: WorkflowState) -> dict:
    log.info("t3_fetch_2b", client_id=state.get("client_id"))
    return {"status": "NEEDS_INPUT", "audit_entries": state.get("audit_entries", []) + [{"actor": "firmOS", "action": "STEP_COMPLETED", "description": "Awaiting GSTN-downloaded GSTR-2B evidence upload"}]}


async def reconcile_2b(state: WorkflowState) -> dict:
    from api.routes.reconciliation import _build_purchase_source, _build_uploaded_2b_target
    from core.database import Database
    from engines.reconcile import reconcile

    period = state.get("period")
    if not period or Database.pool is None:
        message = "2B reconcile blocked: select a GST period" if not period else "2B reconcile blocked: database not connected"
        return {"status": "NEEDS_INPUT", "audit_entries": state.get("audit_entries", []) + [{"actor": "firmOS", "action": "STEP_FAILED", "description": message}]}
    try:
        async with Database.pool.acquire() as conn:
            source = await _build_purchase_source(conn, state.get("firm_id"), state.get("client_id"), period)
            target = await _build_uploaded_2b_target(conn, state.get("firm_id"), state.get("client_id"), period)
        result = reconcile(source, target)
        summary = result.summary
        return {
            "status": "2B_RECONCILED", "recon_result": result.model_dump(),
            "audit_entries": state.get("audit_entries", []) + [{"actor": "firmOS", "action": "STEP_COMPLETED", "description": f"2B reconcile: {summary.autoMatched} auto, {summary.suggested} suggested, {summary.unmatched} unmatched"}],
        }
    except Exception:
        log.error("t3_reconcile_failed")
        return {"status": "FAILED", "error": "2B_RECONCILIATION_FAILED", "audit_entries": state.get("audit_entries", []) + [{"actor": "firmOS", "action": "STEP_FAILED", "description": "2B reconcile failed"}]}


def mismatch_gate(state: WorkflowState) -> dict:
    from langgraph.types import interrupt

    interrupt({"reason": "Review GSTR-2B vs purchase register mismatches"})
    return {"audit_entries": state.get("audit_entries", []) + [{"actor": "HUMAN", "action": "HUMAN_APPROVED", "description": "Reviewed GSTR-2B reconciliation mismatches"}]}
