"""Vendor-bill extraction and human review workflow nodes."""
from core.logging import log
from workflows.state import WorkflowState


async def extract(state: WorkflowState) -> dict:
    log.info("t1_extract", document_id=state.get("document_id"))
    from extraction.base import get_extractor

    result = await get_extractor().extract(state.get("file_bytes") or b"", state.get("file_mime") or "image/jpeg")
    if not result.succeeded:
        return {
            "status": "EXTRACTION_FAILED", "error": result.reason_code,
            "audit_entries": state.get("audit_entries", []) + [{
                "actor": "firmOS", "action": "DOCUMENT_EXTRACTION_FAILED",
                "description": f"Extraction failed: {result.reason_code}",
            }],
        }
    fields = result.fields
    return {
        "extracted_fields": fields, "status": "EXTRACTED",
        "audit_entries": state.get("audit_entries", []) + [{
            "actor": "firmOS", "action": "DOCUMENT_EXTRACTED",
            "description": f"Extracted document {state.get('document_id')} via {fields.get('source', 'unknown')}",
        }],
    }


def after_extract(state: WorkflowState) -> str:
    return "failed" if state.get("status") == "EXTRACTION_FAILED" else "validate"


def validate(state: WorkflowState) -> dict:
    log.info("t1_validate", document_id=state.get("document_id"))
    extracted = state.get("extracted_fields") or {}
    try:
        from engines.tds import calculate_tds

        amount_paise = int(extracted.get("total_paise", 0))
        description = str((extracted.get("line_items") or [{}])[0].get("desc", "")).lower()
        section = "194J_PROF" if any(word in description for word in ("professional", "consult", "audit", "legal")) else "194C" if any(word in description for word in ("contract", "labour", "security")) else ""
        if section:
            result = calculate_tds(section, amount_paise, pan_available=True)
            if result.get("tds_amount", 0):
                extracted["tds_suggestion"] = f"Applicable {section} ({'10%' if section == '194J_PROF' else '1%'}): ₹{result['tds_amount']/100:.2f}"
    except Exception:
        log.warning("t1_tds_validation_failed")
    return {
        "extracted_fields": extracted, "status": "VALIDATED",
        "audit_entries": state.get("audit_entries", []) + [{"actor": "firmOS", "action": "STEP_COMPLETED", "description": "Deterministic validation complete"}],
    }


def review_gate(state: WorkflowState) -> dict:
    from langgraph.types import interrupt

    decision = interrupt({"reason": "Document needs human review before posting to books"})
    if decision.get("approved"):
        return {
            "status": "APPROVED",
            "audit_entries": state.get("audit_entries", []) + [{"actor": "HUMAN", "action": "HUMAN_APPROVED", "description": f"Approved document {state.get('document_id')}"}],
        }
    return {"status": "REJECTED"}


async def post_to_books(state: WorkflowState) -> dict:
    if state.get("status") != "APPROVED":
        return {}
    return {"ledger_ref": None, "status": "NEEDS_ACTION_APPROVAL", "error": "Open document review to map existing Zoho records and approve the exact action."}
