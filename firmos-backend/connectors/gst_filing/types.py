"""Canonical types for GST filing operations.

All amounts in PAISE (int). All periods as MMYYYY strings.
These types are provider-agnostic — used by every GstFilingProvider impl.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GstinDetails:
    """Result of GSTIN verification."""
    gstin: str
    legal_name: str
    trade_name: str
    status: str  # "Active" | "Cancelled" | "Suspended"
    state_code: str
    registration_date: str  # YYYY-MM-DD


@dataclass(frozen=True)
class Gstr2bSupplierEntry:
    """Single supplier invoice from GSTR-2B."""
    supplier_gstin: str
    supplier_name: str
    invoice_number: str
    invoice_date: str  # YYYY-MM-DD
    invoice_value_paise: int
    taxable_value_paise: int
    igst_paise: int
    cgst_paise: int
    sgst_paise: int
    itc_available: bool


@dataclass
class Gstr2bData:
    """Parsed GSTR-2B response from GSP."""
    gstin: str
    period: str  # MMYYYY
    entries: list[Gstr2bSupplierEntry] = field(default_factory=list)
    raw_response: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ReconMatchRow:
    """Single row in a 2B reconciliation report."""
    invoice_number: str
    supplier_gstin: str
    status: str  # "MATCHED" | "MISMATCHED" | "MISSING_IN_2B" | "MISSING_IN_BOOKS"
    books_amount_paise: int
    gstr2b_amount_paise: int
    difference_paise: int
    itc_eligible: bool


@dataclass
class ReconReport:
    """Full 2B reconciliation report from GSP."""
    gstin: str
    period: str
    matched_count: int
    mismatched_count: int
    missing_in_2b_count: int
    missing_in_books_count: int
    total_itc_eligible_paise: int
    total_itc_ineligible_paise: int
    rows: list[ReconMatchRow] = field(default_factory=list)


@dataclass
class Gstr3bSummary:
    """GSTR-3B summary data for save/file operations.

    Table 3.1: Outward supplies
    Table 4: Eligible ITC
    """
    gstin: str
    period: str  # MMYYYY
    # Table 3.1 — outward taxable supplies
    output_igst_paise: int = 0
    output_cgst_paise: int = 0
    output_sgst_paise: int = 0
    output_cess_paise: int = 0
    # Table 4 — ITC
    itc_igst_paise: int = 0
    itc_cgst_paise: int = 0
    itc_sgst_paise: int = 0
    itc_cess_paise: int = 0
    # Net payable (computed by engines/gst.py)
    net_igst_payable_paise: int = 0
    net_cgst_payable_paise: int = 0
    net_sgst_payable_paise: int = 0
    # Interest on late payment
    interest_paise: int = 0


@dataclass(frozen=True)
class FilingAck:
    """Acknowledgement after filing a return."""
    arn: str  # Acknowledgement Reference Number
    status: str  # "SUCCESS" | "PENDING" | "ERROR"
    reference_id: str = ""
    message: str = ""


@dataclass(frozen=True)
class PurchaseRow:
    """Single row from the purchase register (Zoho bills) for 2B recon."""
    invoice_number: str
    invoice_date: str  # YYYY-MM-DD
    supplier_gstin: str
    supplier_name: str
    taxable_value_paise: int
    total_gst_paise: int


@dataclass(frozen=True)
class SalesRow:
    """Single row from sales register for GSTR-1 filing."""
    invoice_number: str
    invoice_date: str  # YYYY-MM-DD
    customer_gstin: str
    customer_name: str
    taxable_value_paise: int
    igst_paise: int
    cgst_paise: int
    sgst_paise: int
    place_of_supply: str  # 2-digit state code
