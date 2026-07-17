"""Zoho Books specific connector API routes."""

import logging
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from api.deps import get_current_firm, FirmContext, get_db
from core.money import rupees_to_paise

router = APIRouter(prefix="/api/connectors/zoho", tags=["zoho"])
logger = logging.getLogger(__name__)


class ItcEligibilityRequest(BaseModel):
    itc_eligible: bool


def _period_to_dates(period: str) -> tuple[str, str]:
    """Convert MMYYYY period string to (date_start, date_end) in YYYY-MM-DD.

    e.g. '062026' → ('2026-06-01', '2026-06-30')
    """
    month = int(period[:2])
    year = int(period[2:])
    start = date(year, month, 1)
    # Last day of month: go to next month day 1, subtract 1 day
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    from datetime import timedelta
    end = end - timedelta(days=1)
    return start.isoformat(), end.isoformat()


async def compute_gst_summary(client_id: str, period: str, firm: FirmContext, db_pool) -> dict:
    """Compute GST summary (output tax from invoices + 2B-matched ITC) directly from DB/Zoho."""
    from core.config import settings
    if settings.strict_no_mock and not db_pool:
        raise RuntimeError("STRICT_NO_MOCK enforced: Database pool required for compute_gst_summary")
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not available")

    from connectors.zoho_books.legacy_credentials import legacy_zoho_client
    from connectors.zoho_books.sync import list_invoices_by_period
    client = await legacy_zoho_client(db_pool, firm.firm_id)
    if not client:
        raise HTTPException(status_code=400, detail="Zoho Books not connected")

    # Fetch sales invoices for the specific period
    date_start, date_end = _period_to_dates(period)
    invoices_resp = await list_invoices_by_period(client, date_start, date_end)
    invoices = invoices_resp.get("invoices", [])

    # Calculate output GST sum (in paise) and persist to sales_register
    output_gst_paise = 0
    async with db_pool.acquire() as conn:
        for inv in invoices:
            tax_total = inv.get("tax_total", 0)
            tax_paise = rupees_to_paise(tax_total)
            output_gst_paise += tax_paise

            # Upsert into sales_register so the CA can audit which invoices form the output tax
            inv_id = inv.get("invoice_id", "")
            reg_id = f"sr-{inv_id}" if inv_id else f"sr-{uuid.uuid4().hex[:8]}"
            try:
                await conn.execute(
                    """INSERT INTO sales_register
                       (id, firm_id, client_id, period, zoho_invoice_id, invoice_number,
                        customer_name, invoice_date, total_paise, tax_total_paise, status)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8::date, $9, $10, $11)
                       ON CONFLICT (firm_id, client_id, zoho_invoice_id)
                       DO UPDATE SET tax_total_paise = $10, total_paise = $9, synced_at = NOW()""",
                    reg_id, firm.firm_id, client_id, period,
                    inv_id, inv.get("invoice_number", ""),
                    inv.get("customer_name", ""),
                    inv.get("date", None),
                    rupees_to_paise(inv.get("total", 0)),
                    tax_paise,
                    inv.get("status", ""),
                )
            except Exception:
                # ponytail: don't fail the summary if upsert fails on one row
                logger.warning("Failed to upsert sales register row")

    # 2. Use the uploaded GSTR-2B evidence for this exact period.
    from api.routes.reconciliation import get_reconciliation
    recon_res = await get_reconciliation(client_id, mode="GSTR2B_VS_PURCHASE", period=period, firm=firm, db_pool=db_pool)

    # Eligible ITC = auto-matched total from the reconciliation engine
    itc_eligible_paise = int(recon_res.summary.totalAutoMatched)

    return {
        "client_id": client_id,
        "period": period,
        "output_gst_paise": output_gst_paise,
        "itc_eligible_paise": itc_eligible_paise,
        "invoices_count": len(invoices),
    }


@router.get("/gst-summary")
async def get_gst_summary(
    client_id: str,
    period: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db),
):
    """GET /api/connectors/zoho/gst-summary?client_id=&period=

    Fetches output tax from Zoho Books (sales invoices, period-filtered)
    and 2B-matched ITC (input tax) from the reconciliation engine.

    Period format: MMYYYY (e.g. '062026' for June 2026).
    """
    return await compute_gst_summary(client_id, period, firm, db_pool)


@router.get("/gstr3b-tables")
async def get_gstr3b_tables(
    client_id: str,
    period: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db),
):
    """GET /api/connectors/zoho/gstr3b-tables?client_id=&period=

    Returns only a working draft when jurisdictional tax components are available.
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="GST working store unavailable")
    _period_to_dates(period)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT source_type, taxable_paise, igst_paise, cgst_paise, sgst_paise, cess_paise,
                      components_verified, itc_eligible
               FROM gst_tax_components WHERE firm_id=$1 AND client_id=$2 AND period=$3""",
            firm.firm_id, client_id, period,
        )
    if not rows:
        raise HTTPException(status_code=409, detail="Sync the Zoho registers to retrieve provider tax components first")
    unverified = sum(1 for row in rows if not row["components_verified"])
    undecided_itc = sum(1 for row in rows if row["source_type"] == "PURCHASE" and row["itc_eligible"] is None)
    if unverified or undecided_itc:
        raise HTTPException(status_code=409, detail={"message": "GSTR-3B working remains blocked until every component is proven and every purchase ITC decision is reviewed.", "unverified_components": unverified, "undecided_itc": undecided_itc})
    from api.routes.reconciliation import get_reconciliation
    reconciliation = await get_reconciliation(client_id, mode="GSTR2B_VS_PURCHASE", period=period, firm=firm, db_pool=db_pool)
    if reconciliation.summary.suggested or reconciliation.summary.unmatched:
        raise HTTPException(status_code=409, detail="Resolve GSTR-2B purchase exceptions before generating the 3B working")
    def total(source_type: str, column: str, eligible_only: bool = False) -> int:
        return sum(int(row[column]) for row in rows if row["source_type"] == source_type and (not eligible_only or row["itc_eligible"] is True))
    from engines.gst import generate_gstr3b_tables
    tables = generate_gstr3b_tables(
        output_taxable_paise=total("SALES", "taxable_paise"), output_igst_paise=total("SALES", "igst_paise"),
        output_cgst_paise=total("SALES", "cgst_paise"), output_sgst_paise=total("SALES", "sgst_paise"),
        itc_igst_paise=total("PURCHASE", "igst_paise", True), itc_cgst_paise=total("PURCHASE", "cgst_paise", True),
        itc_sgst_paise=total("PURCHASE", "sgst_paise", True),
    )
    return {"period": period, "tables": tables, "portal_filing": "MANUAL", "status": "CA_REVIEW_REQUIRED"}


@router.get("/gst-components")
async def get_gst_components(client_id: str, period: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    """Return source-level GST evidence, including ITC decisions still needing a CA."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="GST working store unavailable")
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id,source_type,source_id,taxable_paise,igst_paise,cgst_paise,sgst_paise,cess_paise,components_verified,itc_eligible,synced_at
               FROM gst_tax_components WHERE firm_id=$1 AND client_id=$2 AND period=$3 ORDER BY source_type, source_id""",
            firm.firm_id, client_id, period,
        )
    return {"components": [dict(row) for row in rows]}


@router.post("/gst-components/{component_id}/itc-eligibility")
async def set_itc_eligibility(component_id: str, payload: ItcEligibilityRequest, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    """Record the accountant's explicit ITC decision; this is not a provider-side write."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="GST working store unavailable")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE gst_tax_components SET itc_eligible=$1 WHERE id=$2::uuid AND firm_id=$3 AND source_type='PURCHASE'
               RETURNING id,itc_eligible""", payload.itc_eligible, component_id, firm.firm_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Purchase GST component not found")
    return dict(row)


@router.get("/gstr3b-json")
async def get_gstr3b_json(
    client_id: str,
    period: str,
    gstin: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db),
):
    """GET /api/connectors/zoho/gstr3b-json?client_id=&period=&gstin=

    Is intentionally blocked until the GSTR-3B working has real tax components.
    """
    tables_res = await get_gstr3b_tables(client_id, period, firm, db_pool)
    from engines.gst import export_gstr3b_gstn_json
    return export_gstr3b_gstn_json(gstin=gstin, period=period, tables=tables_res["tables"])


@router.get("/manual-gst-pack")
async def get_manual_gst_pack(
    client_id: str,
    period: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    """Return the evidence pack a CA reviews before manually filing on the GST portal."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="GST working store unavailable")
    _period_to_dates(period)
    async with db_pool.acquire() as conn:
        sales = await conn.fetchrow(
            """SELECT COUNT(*) AS count, COALESCE(SUM(total_paise), 0) AS total_paise,
                      COALESCE(SUM(tax_total_paise), 0) AS tax_paise
               FROM sales_register WHERE firm_id=$1 AND client_id=$2 AND period=$3""",
            firm.firm_id, client_id, period,
        )
        purchases = await conn.fetchrow(
            """SELECT COUNT(*) AS count, COALESCE(SUM(total_paise), 0) AS total_paise,
                      COALESCE(SUM(tax_total_paise), 0) AS tax_paise
               FROM purchase_register WHERE firm_id=$1 AND client_id=$2 AND period=$3""",
            firm.firm_id, client_id, period,
        )
        evidence = await conn.fetchrow(
            "SELECT uploaded_at FROM gstr2b_uploads WHERE firm_id=$1 AND client_id=$2 AND period=$3",
            firm.firm_id, client_id, period,
        )
        components = await conn.fetch(
            """SELECT source_type, taxable_paise, igst_paise, cgst_paise, sgst_paise, cess_paise, components_verified, itc_eligible
               FROM gst_tax_components WHERE firm_id=$1 AND client_id=$2 AND period=$3""", firm.firm_id, client_id, period,
        )

    from api.routes.reconciliation import get_reconciliation
    reconciliation = await get_reconciliation(
        client_id, mode="GSTR2B_VS_PURCHASE", period=period, firm=firm, db_pool=db_pool,
    )
    sales_tax = int(sales["tax_paise"])
    matched_itc = int(reconciliation.summary.totalAutoMatched)
    unverified = sum(1 for row in components if not row["components_verified"])
    undecided_itc = sum(1 for row in components if row["source_type"] == "PURCHASE" and row["itc_eligible"] is None)
    ready = bool(evidence) and bool(components) and not unverified and not undecided_itc and reconciliation.summary.suggested == 0 and reconciliation.summary.unmatched == 0
    return {
        "client_id": client_id,
        "period": period,
        "filing_status": "CA_REVIEW_READY" if ready else "NEEDS_COMPONENT_REVIEW",
        "portal_filing": "MANUAL",
        "evidence": {"gstr2b_uploaded": bool(evidence), "uploaded_at": evidence["uploaded_at"] if evidence else None},
        "sales_register": {"count": int(sales["count"]), "total_paise": int(sales["total_paise"]), "tax_paise": sales_tax},
        "purchase_register": {"count": int(purchases["count"]), "total_paise": int(purchases["total_paise"]), "tax_paise": int(purchases["tax_paise"])},
        "gstr2b_mismatch_report": reconciliation.model_dump(),
        "gstr3b_working": {
            "output_tax_paise": sales_tax,
            "matched_itc_paise": matched_itc,
            "provisional_net_tax_paise": sales_tax - matched_itc,
            "component_rows": len(components), "unverified_components": unverified, "undecided_itc": undecided_itc,
            "warning": "This pack supports CA review. Filing remains a manual portal task; review reversals, RCM, zero-rated and exempt supplies before filing.",
        },
        "review_checklist": [
            {"item": "GSTR-2B evidence uploaded for selected period", "complete": bool(evidence)},
            {"item": "Resolve suggested and unmatched purchase entries", "complete": reconciliation.summary.suggested == 0 and reconciliation.summary.unmatched == 0},
            {"item": "Provider CGST, SGST, IGST and taxable-value splits reconcile", "complete": bool(components) and unverified == 0},
            {"item": "CA records an ITC decision for every purchase component", "complete": undecided_itc == 0},
            {"item": "CA reviews and files manually on GST portal", "complete": False},
        ],
        "ready_for_ca_review": ready,
    }
