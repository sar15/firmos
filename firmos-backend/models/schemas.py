"""Pydantic models matching frontend Zod schemas in types/index.ts.

RULE: canonical money is always integer paise. Field value strings are display-only.
"""

from __future__ import annotations

from typing import Literal, Optional
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


# --- Money ---
# Matches MoneySchema: { paise: z.number().int(), currency: z.literal("INR") }
class Money(BaseModel):
    paise: int
    currency: Literal["INR"] = "INR"


# --- Client ---
# Matches ClientSchema in types/index.ts L9-19
class Client(BaseModel):
    id: str
    legalName: str
    pan: str
    gstin: Optional[str] = None
    entityType: Literal["PRIVATE_LIMITED", "LLP", "PROPRIETOR", "PARTNERSHIP"]
    state: str
    booksProvider: Optional[Literal["ZOHO_BOOKS", "TALLY", "QUICKBOOKS", "CSV", "NONE"]] = None
    nextDue: str  # ISO date string
    complianceStatus: Literal["ON_TRACK", "DUE_SOON", "OVERDUE"]


# --- Decision ---
# Matches DecisionSchema in types/index.ts L22-33
class Decision(BaseModel):
    id: str
    clientId: str
    kind: Literal["TDS_DEFAULT", "GST_NOTICE", "GSTR_APPROVAL", "ITR_APPROVAL", "RECONCILIATION"]
    title: str
    firmOsRecommendation: str
    urgency: Literal["NEEDS_YOU_NOW", "DUE_TODAY", "THIS_WEEK"]
    amountAtStake: Optional[Money] = None
    dueDate: str  # ISO datetime
    confidence: float = Field(ge=0, le=1)


# --- Connector (rich schema — per Q1 decision) ---
# Matches ConnectorSchema in types/index.ts L36-44
ConnectorStatusType = Literal["CONNECTED", "DISCONNECTED", "NEEDS_ATTENTION"]

class Connector(BaseModel):
    id: str
    name: str
    category: Literal["FEATURED", "ACCOUNTING", "GOVERNMENT", "BANKING", "DOCS", "DEVELOPER"]
    description: str
    status: ConnectorStatusType
    authMethod: Literal["OAUTH", "CREDENTIALS", "API_KEY", "CONSENT"]
    lastSyncedAt: Optional[str] = None


# --- Audit ---
# Matches AuditEntrySchema in types/index.ts L47-56
class AuditEntry(BaseModel):
    id: str
    timestamp: str  # ISO datetime
    actor: Literal["firmOS", "HUMAN"]
    actorName: str
    action: Literal["PORTAL_SUBMITTED", "HUMAN_APPROVED", "STEP_COMPLETED", "DATA_READ", "DOCUMENT_EXTRACTED"]
    description: str
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


# --- Document ---
# Matches types/index.ts L59-107
class Bbox(BaseModel):
    page: int
    x: float
    y: float
    w: float
    h: float


class ExtractedField(BaseModel):
    key: str
    label: str
    value: str  # ALWAYS a string, even for numbers — display-only
    confidence: float = Field(ge=0, le=1)
    level: Literal["HIGH", "REVIEW", "LOW"]
    bbox: Optional[Bbox] = None


class LineItem(BaseModel):
    desc: str
    hsn: Optional[str] = None
    qty: Decimal
    rate: int
    amount: int


class ExtractedDocument(BaseModel):
    id: str
    clientId: str
    clientName: str
    fileUrl: str
    fileType: Literal["pdf", "image", "spreadsheet"]
    docKind: Literal["VENDOR_BILL", "SALES_INVOICE", "RECEIPT", "PAYMENT", "JOURNAL"]
    status: Literal["PENDING_REVIEW", "POSTED", "REJECTED", "NEEDS_INFO"]
    vendorName: str
    fields: list[ExtractedField]
    lineItems: list[LineItem]
    total: int  # paise as raw number (1845000 = ₹18,450)
    uploadedAt: str  # ISO datetime


# --- Reconciliation ---
# Matches types/index.ts L110-135
ReconModeType = Literal["BANK_VS_BOOKS", "GSTR2B_VS_PURCHASE"]
MatchStatusType = Literal["AUTO_MATCHED", "SUGGESTED", "UNMATCHED"]

class ReconLine(BaseModel):
    id: str
    date: str  # ISO date
    description: str
    counterparty: str
    amount: int  # paise
    ref: Optional[str] = None
    gstin: Optional[str] = None


class ReconMatch(BaseModel):
    id: str
    status: MatchStatusType
    score: Optional[float] = Field(default=None, ge=0, le=1)
    source: Optional[ReconLine] = None
    target: Optional[ReconLine] = None
    flag: Optional[Literal["SUPPLIER_NOT_FILED", "PORTAL_ENTRY_NOT_IN_BOOKS", "AMOUNT_MISMATCH", "DATE_DRIFT"]] = None

    @model_validator(mode="after")
    def require_a_reconciliation_side(self):
        if self.source is None and self.target is None:
            raise ValueError("A reconciliation match needs a source or target line")
        return self


class ReconciliationSummary(BaseModel):
    autoMatched: int
    suggested: int
    unmatched: int
    totalAutoMatched: int  # paise
    totalSuggested: int
    totalUnmatched: int


class ReconciliationResult(BaseModel):
    matches: list[ReconMatch]
    summary: ReconciliationSummary


# --- Notification ---
# Matches notifications.api.ts AppNotification interface
class AppNotification(BaseModel):
    id: str
    group: Literal["NEEDS_YOU", "UPDATES"]
    title: str
    clientName: str
    timestamp: str  # ISO or relative like "2 hours ago"
    isRead: bool
    actionUrl: str
    urgency: Literal["red", "amber", "royal"]  # design tokens, not severity
