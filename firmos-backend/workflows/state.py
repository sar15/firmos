"""Shared state shape for workflow graphs."""
from typing import Optional, TypedDict


class WorkflowState(TypedDict, total=False):
    firm_id: str
    client_id: str
    document_id: Optional[str]
    doc_kind: Optional[str]
    decision_id: Optional[str]
    approved: bool
    gstin: str
    period: str
    status: str
    audit_entries: list[dict]
    error: Optional[str]
    file_bytes: bytes
    file_mime: str
    extracted_fields: Optional[dict]
    bank_source_lines: list[dict]
    books_target_lines: list[dict]
    taxable_income_paise: Optional[int]
    regime: str
    gstr3b_draft: Optional[dict]
    recon_result: Optional[dict]
    arn: Optional[str]
    ledger_ref: Optional[str]
    gsp_auth_token: str
    evc_otp: str
