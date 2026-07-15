"""Compute API routes — exposing the tax engines."""

from datetime import date
from typing import List, Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_current_firm, FirmContext
from engines import gst, tds, interest

router = APIRouter(prefix="/api/compute", tags=["compute"])

# --- Models ---

class TDSRequest(BaseModel):
    section: str
    gross_amount_paise: int
    pan_available: bool = True

class InterestRequest(BaseModel):
    total_tax_paise: int
    advance_tax_paid_paise: int
    assessment_year_end: date
    actual_filing_date: date
    installments_paid: List[Dict[str, Any]] = []

class GSTRequest(BaseModel):
    taxable_paise: int
    rate_percent: float
    is_interstate: bool

class ITCEligibilityRequest(BaseModel):
    supplier_filed: bool
    invoice_amount_paise: int
    gstr2b_amount_paise: int
    tolerance_paise: int = 100

class NetGSTPayableRequest(BaseModel):
    output_gst_paise: int
    itc_available_paise: int
    itc_eligible_paise: int

# --- Routes ---

@router.post("/tds")
def compute_tds(
    req: TDSRequest,
    firm: FirmContext = Depends(get_current_firm),
):
    """Compute TDS amount based on section and PAN availability."""
    return tds.calculate_tds(
        section=req.section,
        gross_amount_paise=req.gross_amount_paise,
        pan_available=req.pan_available,
    )

@router.post("/interest")
def compute_interest(
    req: InterestRequest,
    firm: FirmContext = Depends(get_current_firm),
):
    """Compute 234B and 234C interest for advance tax defaults."""
    res_234b = interest.calculate_234b_interest(
        total_tax_paise=req.total_tax_paise,
        advance_tax_paid_paise=req.advance_tax_paid_paise,
        assessment_year_end=req.assessment_year_end,
        actual_filing_date=req.actual_filing_date,
    )
    
    res_234c = interest.calculate_234c_interest(
        total_tax_paise=req.total_tax_paise,
        installments_paid=req.installments_paid,
    )
    
    return {
        "234b": res_234b,
        "234c": res_234c,
        "total_interest_paise": res_234b.get("interest", 0) + res_234c.get("total_interest", 0)
    }

@router.post("/gst")
def compute_gst(
    req: GSTRequest,
    firm: FirmContext = Depends(get_current_firm),
):
    """Compute CGST, SGST, IGST from taxable amount and rate."""
    return gst.calculate_gst(
        taxable_paise=req.taxable_paise,
        rate_percent=req.rate_percent,
        is_interstate=req.is_interstate,
    )

@router.post("/itc-eligibility")
def check_itc(
    req: ITCEligibilityRequest,
    firm: FirmContext = Depends(get_current_firm),
):
    """Check ITC eligibility against GSTR-2B data."""
    return gst.check_itc_eligibility(
        supplier_filed=req.supplier_filed,
        invoice_amount_paise=req.invoice_amount_paise,
        gstr2b_amount_paise=req.gstr2b_amount_paise,
        tolerance_paise=req.tolerance_paise,
    )

@router.post("/net-gst-payable")
def compute_net_gst(
    req: NetGSTPayableRequest,
    firm: FirmContext = Depends(get_current_firm),
):
    """Compute net GST payable after eligible ITC deduction."""
    return gst.calculate_net_gst_payable(
        output_gst_paise=req.output_gst_paise,
        itc_available_paise=req.itc_available_paise,
        itc_eligible_paise=req.itc_eligible_paise,
    )
