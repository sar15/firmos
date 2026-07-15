"""Period-aware register projections backed by firmOS storage.

# ponytail: registers read only materialized rows; sync is the single explicit
# path that reads Zoho and refreshes those rows.
"""
import json
import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from api.deps import FirmContext, get_current_firm, get_db
from core.money import rupees_to_paise

_paise = rupees_to_paise
router = APIRouter(prefix="/api/registers", tags=["registers"])
_PERIOD = re.compile(r"^(0[1-9]|1[0-2])\d{4}$")


def _bounds(period: str) -> tuple[str, str]:
    if not _PERIOD.fullmatch(period):
        raise HTTPException(status_code=422, detail="period must be MMYYYY")
    month, year = int(period[:2]), int(period[2:])
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _json(value, fallback):
    if value is None:
        return fallback
    return json.loads(value) if isinstance(value, str) else value


async def _rows(conn, table: str, firm_id: str, client_id: str, period: str) -> list[dict]:
    if table == "sales_register":
        records = await conn.fetch(
            """SELECT id,invoice_number,customer_name,customer_gstin,invoice_date,place_of_supply,
               taxable_paise,cgst_paise,sgst_paise,igst_paise,cess_paise,total_paise,tax_total_paise,
               e_invoice,status,provider,provider_object_id,document_id,finance_action_id,verification_id,
               source_version,evidence
               FROM sales_register WHERE firm_id = $1 AND client_id = $2 AND period = $3
               AND active AND (provider_object_id IS NOT NULL OR verification_id IS NOT NULL)
               ORDER BY invoice_date DESC, invoice_number DESC""",
            firm_id, client_id, period,
        )
        return [{
            "id": str(r["id"]), "invoiceNumber": str(r["invoice_number"] or ""),
            "customerName": str(r["customer_name"] or "Unknown Customer"),
            "customerGstin": str(r["customer_gstin"] or ""),
            "invoiceDate": r["invoice_date"].isoformat() if r["invoice_date"] else "",
            "placeOfSupply": str(r["place_of_supply"] or ""),
            "taxablePaise": int(r["taxable_paise"] or 0),
            "cgstPaise": int(r["cgst_paise"] or 0), "sgstPaise": int(r["sgst_paise"] or 0),
            "igstPaise": int(r["igst_paise"] or 0), "cessPaise": int(r["cess_paise"] or 0),
            "totalPaise": int(r["total_paise"] or 0), "taxTotalPaise": int(r["tax_total_paise"] or 0),
            "status": str(r["status"] or "Synced"), "provider": str(r["provider"] or "EXTERNAL"),
            "providerObjectId": str(r["provider_object_id"] or ""), "documentId": str(r["document_id"] or ""),
            "financeActionId": str(r["finance_action_id"] or ""), "verificationId": str(r["verification_id"] or ""),
            "sourceVersion": str(r["source_version"] or ""), "eInvoice": _json(r["e_invoice"], {}),
            "evidence": _json(r["evidence"], []),
            "verified": bool(r["provider_object_id"] or r["verification_id"]),
        } for r in records]

    records = await conn.fetch(
        """SELECT id,bill_number,vendor_name,vendor_gstin,bill_date,total_paise,tax_total_paise,source,status,
           provider,provider_object_id,document_id,finance_action_id,verification_id,evidence,active
           FROM purchase_register WHERE firm_id = $1 AND client_id = $2 AND period = $3 AND active
           AND (provider_object_id IS NOT NULL OR verification_id IS NOT NULL)
           ORDER BY bill_date DESC, bill_number DESC""",
        firm_id, client_id, period,
    )
    return [{
        "id": str(r["id"]), "billNumber": str(r["bill_number"] or ""),
        "vendorName": str(r["vendor_name"] or "Unknown Vendor"), "vendorGstin": str(r["vendor_gstin"] or ""),
        "billDate": r["bill_date"].isoformat() if r["bill_date"] else "",
        "totalPaise": int(r["total_paise"] or 0), "taxTotalPaise": int(r["tax_total_paise"] or 0),
        "source": str(r["provider"] or r["source"] or "EXTERNAL"), "status": str(r["status"] or "Synced"),
        "providerObjectId": str(r["provider_object_id"] or ""), "documentId": str(r["document_id"] or ""),
        "financeActionId": str(r["finance_action_id"] or ""), "verificationId": str(r["verification_id"] or ""),
        "evidence": json.loads(r["evidence"]) if isinstance(r["evidence"], str) else (r["evidence"] or []),
        "verified": bool(r["provider_object_id"] or r["verification_id"]),
    } for r in records]


@router.get("/sales")
async def get_sales_register(client_id: str, period: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    _bounds(period)
    if not db_pool:
        raise HTTPException(status_code=503, detail="Register store unavailable")
    async with db_pool.acquire() as conn:
        return await _rows(conn, "sales_register", firm.firm_id, client_id, period)


@router.get("/purchase")
async def get_purchase_register(client_id: str, period: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    _bounds(period)
    if not db_pool:
        raise HTTPException(status_code=503, detail="Register store unavailable")
    async with db_pool.acquire() as conn:
        return await _rows(conn, "purchase_register", firm.firm_id, client_id, period)


@router.get("/purchase/status")
async def purchase_register_status(client_id: str, period: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    _bounds(period)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT state,expected_count,processed_count,expected_totals,processed_totals,complete_through,updated_at
               FROM register_sync_windows WHERE firm_id=$1 AND client_id=$2 AND register_type='PURCHASE'
               AND period=$3 ORDER BY updated_at DESC LIMIT 1""", firm.firm_id, client_id, period,
        )
    return dict(row) if row else {"state": "PARTIAL", "message": "No complete sync has been recorded for this period."}


@router.get("/sales/status")
async def sales_register_status(client_id: str, period: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    _bounds(period)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT state,expected_count,processed_count,expected_totals,processed_totals,complete_through,updated_at
               FROM register_sync_windows WHERE firm_id=$1 AND client_id=$2 AND register_type='SALES'
               AND period=$3 ORDER BY updated_at DESC LIMIT 1""", firm.firm_id, client_id, period,
        )
    return dict(row) if row else {"state": "PARTIAL", "message": "No complete sales sync has been recorded for this period."}


@router.post("/sync", status_code=202)
async def sync_zoho_registers(client_id: str, period: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    """Queue durable Zoho register sync; provider I/O stays in the worker."""
    _bounds(period)
    if not db_pool:
        raise HTTPException(status_code=503, detail="Register store unavailable")
    async with db_pool.acquire() as conn, conn.transaction():
        installation = await conn.fetchrow(
            """SELECT id FROM connector_installations WHERE firm_id=$1 AND client_id=$2
               AND provider='ZOHO_BOOKS' AND status='AVAILABLE'""", firm.firm_id, client_id,
        )
        if not installation:
            raise HTTPException(status_code=409, detail="Zoho Books is not connected for this client")
        job_ids = []
        for capability in ("zoho.sync.sales_invoices", "zoho.sync.purchase_bills"):
            row = await conn.fetchrow(
                """INSERT INTO connector_sync_jobs(firm_id,client_id,installation_id,
                   capability_key,period,status,correlation_id)
                   VALUES($1,$2,$3,$4,$5,'QUEUED',gen_random_uuid()::text) RETURNING id""",
                firm.firm_id, client_id, installation["id"], capability, period,
            )
            job_ids.append(str(row["id"]))
    return {"status": "QUEUED", "period": period, "job_ids": job_ids}
