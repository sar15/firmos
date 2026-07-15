"""GSTR-3B working and manual-filing handoff workflow nodes."""
from core.logging import log
from engines.gst import calculate_net_gst_payable
from workflows.state import WorkflowState


async def compute(state: WorkflowState) -> dict:
    from api.deps import FirmContext
    from api.routes.zoho import compute_gst_summary
    from core.database import Database

    period = state.get("period")
    user_id, firm_id = state.get("user_id"), state.get("firm_id")
    if not period or not user_id or not firm_id:
        raise RuntimeError("Cannot compute GSTR-3B without period and authenticated tenant context")
    try:
        summary = await compute_gst_summary(state.get("client_id"), period, FirmContext(user_id, firm_id, "REVIEWER"), Database.pool)
    except Exception as exc:
        log.error("t4_compute_failed")
        raise RuntimeError("Cannot compute GSTR-3B: failed to fetch GST summary") from exc
    result = calculate_net_gst_payable(
        output_gst_paise=summary["output_gst_paise"],
        # The verified GSTR-2B match is the only ITC source in v1, so it is
        # both available and eligible; do not invent a separate value.
        itc_available_paise=summary["itc_eligible_paise"],
        itc_eligible_paise=summary["itc_eligible_paise"],
    )
    return {"gstr3b_draft": result, "status": "DRAFT_READY", "audit_entries": state.get("audit_entries", []) + [{"actor": "firmOS", "action": "STEP_COMPLETED", "description": f"Computed GSTR-3B draft (Net Payable: ₹{result['net_payable']/100:.2f})"}]}


def approve_gate(state: WorkflowState) -> dict:
    from langgraph.types import interrupt

    decision = interrupt({"reason": "GSTR-3B working ready — approve handoff for manual portal filing"})
    if decision.get("approved"):
        return {"status": "MANUAL_FILING_APPROVED", "gstin": decision.get("gstin") or state.get("gstin"), "audit_entries": state.get("audit_entries", []) + [{"actor": "HUMAN", "action": "HUMAN_APPROVED", "description": "Approved GSTR-3B working for manual portal filing"}]}
    return {"status": "REJECTED"}


async def request_otp(_: WorkflowState) -> dict:
    return {"status": "NOT_IMPLEMENTED", "error": "GST portal filing is manual; no OTP is requested by firmOS."}


def otp_gate(_: WorkflowState) -> dict:
    return {"status": "NOT_IMPLEMENTED", "error": "GST portal filing is manual; no OTP is collected by firmOS."}


async def manual_handoff(state: WorkflowState) -> dict:
    if state.get("status") != "MANUAL_FILING_APPROVED":
        return {}
    return {"status": "AWAITING_MANUAL_FILING", "audit_entries": state.get("audit_entries", []) + [{"actor": "firmOS", "action": "STEP_COMPLETED", "description": "GSTR-3B working approved; CA must file manually on the GST portal"}]}
