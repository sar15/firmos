"""ITR draft workflow nodes; portal filing remains explicitly unavailable."""
from core.logging import log
from engines.tax import calculate_income_tax
from workflows.state import WorkflowState


def compute(state: WorkflowState) -> dict:
    taxable = state.get("taxable_income_paise")
    if not taxable:
        return {"status": "NEEDS_INPUT", "audit_entries": state.get("audit_entries", []) + [{"actor": "firmOS", "action": "STEP_FAILED", "description": "ITR compute blocked: taxable_income_paise missing (needs Form 16 / 26AS)"}]}
    result = calculate_income_tax(taxable_income_paise=int(taxable), regime=state.get("regime", "NEW"))
    return {"gstr3b_draft": result, "status": "ITR_DRAFT_READY", "audit_entries": state.get("audit_entries", []) + [{"actor": "firmOS", "action": "STEP_COMPLETED", "description": f"Computed ITR draft (Total Tax: ₹{result['total_tax']/100:.2f} under {result['regime']} regime)"}]}


def approve_gate(state: WorkflowState) -> dict:
    from langgraph.types import interrupt

    if state.get("status") != "ITR_DRAFT_READY":
        return {}
    if interrupt({"reason": "ITR draft ready — approve to file"}).get("approved"):
        return {"status": "FILING_APPROVED", "audit_entries": state.get("audit_entries", []) + [{"actor": "HUMAN", "action": "HUMAN_APPROVED", "description": "Approved ITR for filing"}]}
    return {"status": "REJECTED"}


async def file(state: WorkflowState) -> dict:
    if state.get("status") != "FILING_APPROVED":
        return {}
    log.warning("t5_file_not_implemented", client_id=state.get("client_id"))
    return {"status": "NOT_IMPLEMENTED", "error": "ITR portal filing is Phase 2 scope", "audit_entries": state.get("audit_entries", []) + [{"actor": "firmOS", "action": "STEP_FAILED", "description": "ITR filing not implemented (Phase 2). Tax computed but not submitted."}]}
