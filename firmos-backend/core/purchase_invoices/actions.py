"""Connector-neutral purchase proposal creation over certified executors."""
from __future__ import annotations

import json

from fastapi import HTTPException

from core.finance_actions import FinanceActionEngine, compute_payload_hash
from core.purchase_invoices.drafts import save_draft
from core.purchase_invoices.validation import validate_invoice, validation_state


def _response(provider: str, **values) -> dict:
    return {"provider": provider, "status": "ACTION_PROPOSED", "missing_mappings": [],
            "vendor_candidates": [], "account_candidates": [], "customer_candidates": [],
            "item_candidates": [], "tax_candidates": [], **values}


def _totals(doc, field_value, tax_paise) -> dict:
    taxable = int(round(float(field_value(doc, "taxableAmount", "taxable_amount") or 0) * 100))
    tax = tax_paise(doc)
    return {"taxable_paise": taxable, "tax_paise": tax, "other_charges_paise": max(0, int(doc.total)-taxable-tax),
            "total_paise": int(doc.total), "currency": "INR"}


async def _installation(db_pool, firm_id: str, client_id: str, provider: str):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id,configuration FROM connector_installations WHERE firm_id=$1 AND client_id=$2
               AND provider=$3 AND status='AVAILABLE'""", firm_id, client_id, provider,
        )
    if not row:
        label = "Zoho Books" if provider == "ZOHO_BOOKS" else "Tally Agent"
        raise HTTPException(status_code=409, detail=f"Connect {label} for this client first")
    configuration = json.loads(row["configuration"]) if isinstance(row["configuration"], str) else row["configuration"]
    return row, configuration


async def _zoho(doc, request, firm, db_pool, reference: str, date: str, totals: dict) -> tuple[dict, dict, str, str]:
    from api.routes.agent_tools import _zoho_plugin
    from api.routes.document_review import _line, _unique_match
    row, configuration = await _installation(db_pool, firm.firm_id, doc.clientId, "ZOHO_BOOKS")
    plugin = await _zoho_plugin(db_pool, firm.firm_id, doc.clientId)
    contacts = (await plugin.read("zoho.read.contacts.search", {"query": doc.vendorName}))["contacts"]
    accounts = (await plugin.read("zoho.read.chart_of_accounts", {}))["accounts"]
    taxes = (await plugin.read("zoho.read.taxes", {}))["taxes"]
    vendors = [{"id": str(x["contact_id"]), "label": str(x.get("contact_name", ""))} for x in contacts if x.get("contact_id")]
    ledgers = [{"id": str(x["account_id"]), "label": str(x.get("account_name", ""))} for x in accounts
               if x.get("account_id") and x.get("account_type") in ("expense", "cost_of_goods_sold", "other_expense")]
    tax_options = [{"id": str(x["tax_id"]), "label": str(x.get("tax_name_formatted") or x.get("tax_name") or "Tax")}
                   for x in taxes if x.get("tax_id") and not x.get("is_inactive")]
    vendor = request.vendor_id or _unique_match(vendors, doc.vendorName)
    from api.routes.documents import _field_value
    account = request.account_id or _unique_match(ledgers, _field_value(doc, "expenseHead", "expense_head"))
    missing = ([] if vendor in {x["id"] for x in vendors} else ["vendor_id"])
    missing += ([] if account in {x["id"] for x in ledgers} else ["account_id"])
    if totals["tax_paise"] and request.tax_id not in {x["id"] for x in tax_options}:
        missing.append("tax_id")
    response = _response("ZOHO_BOOKS", vendor_candidates=vendors, account_candidates=ledgers,
                         tax_candidates=tax_options if totals["tax_paise"] else [], missing_mappings=missing,
                         status="NEEDS_MAPPING" if missing else "ACTION_PROPOSED")
    mappings = {"vendor_id": vendor, "account_id": account, "tax_id": request.tax_id}
    if missing:
        return response, {}, str(row["id"]), "zoho.write.purchase_bill.create"
    lines = [_line(item, "account_id", account, request.tax_id) for item in doc.lineItems]
    payload = {"vendor_id": vendor, "bill_number": reference, "reference_number": f"FIRMOS-{doc.id}",
               "date": date, "line_items": lines,
               "notes": f"firmOS evidence: {doc.id}", "organization_id": configuration["organization_id"],
               "currency_code": "INR", "subtotal_paise": totals["taxable_paise"],
               "tax_total_paise": totals["tax_paise"], "total_paise": totals["total_paise"]}
    from connectors.zoho_books.purchase_bill import build_purchase_bill
    build_purchase_bill(payload)
    return response | {"mappings": mappings}, payload, str(row["id"]), "zoho.write.purchase_bill.create"


async def _tally(doc, request, firm, db_pool, reference: str, date: str, totals: dict) -> tuple[dict, dict, str, str]:
    row, configuration = await _installation(db_pool, firm.firm_id, doc.clientId, "TALLY_PRIME")
    async with db_pool.acquire() as conn:
        ledger_rows = await conn.fetch(
            """SELECT name,parent FROM tally_ledgers WHERE firm_id=$1 AND client_id=$2 AND installation_id=$3
               AND active ORDER BY name LIMIT 500""", firm.firm_id, doc.clientId, row["id"],
        )
    options = [{"id": str(x["name"]), "label": str(x["name"])} for x in ledger_rows]
    names = {x["id"] for x in options}
    party, purchase = request.party_ledger, request.purchase_ledger
    missing = ([] if party in names else ["party_ledger"]) + ([] if purchase in names else ["purchase_ledger"])
    from api.routes.documents import _field_value
    components = {
        "CGST": int(round(float(_field_value(doc, "cgst") or 0) * 100)),
        "SGST": int(round(float(_field_value(doc, "sgst") or 0) * 100)),
        "IGST": int(round(float(_field_value(doc, "igst") or 0) * 100)),
    }
    tax_ledgers = {"CGST": request.cgst_ledger, "SGST": request.sgst_ledger, "IGST": request.igst_ledger}
    for tax_type, amount in components.items():
        if amount and tax_ledgers[tax_type] not in names:
            missing.append(f"{tax_type.lower()}_ledger")
    response = _response("TALLY_PRIME", vendor_candidates=options, account_candidates=options,
                         missing_mappings=missing, status="NEEDS_MAPPING" if missing else "ACTION_PROPOSED")
    mappings = {"party_ledger": party, "purchase_ledger": purchase, **{
        f"{key.lower()}_ledger": value for key, value in tax_ledgers.items() if components[key]
    }}
    if missing:
        return response | {"mappings": mappings}, {}, str(row["id"]), "tally.write.purchase_voucher.create"
    gst_details = [{"ledger_name": tax_ledgers[key], "tax_type": key, "amount_paise": -amount}
                   for key, amount in components.items() if amount]
    entries = [{"ledger_name": party, "amount_paise": totals["total_paise"]},
               {"ledger_name": purchase, "amount_paise": -totals["taxable_paise"]},
               *[{"ledger_name": item["ledger_name"], "amount_paise": item["amount_paise"]} for item in gst_details]]
    payload = {"date": date, "voucher_number": reference, "reference": reference, "party_ledger": party,
               "purchase_ledger": purchase, "total_paise": totals["total_paise"],
               "taxable_paise": totals["taxable_paise"], "tax_paise": totals["tax_paise"],
               "tax_total_paise": totals["tax_paise"], "entries": entries, "gst_details": gst_details,
               "tally_company": configuration.get("company_name"), "company_guid": configuration.get("company_guid"),
               "narration": f"firmOS evidence: {doc.id}"}
    from connectors.tally.canonical import validate_purchase
    validate_purchase(payload)
    return response | {"mappings": mappings}, payload, str(row["id"]), "tally.write.purchase_voucher.create"


async def propose_purchase(doc, request, firm, db_pool, *, field_value, date_parser, tax_paise) -> dict:
    if doc.docKind != "VENDOR_BILL":
        raise HTTPException(status_code=409, detail="Only purchase invoices are certified in this workflow")
    if any(field.level != "HIGH" for field in doc.fields):
        raise HTTPException(status_code=400, detail="Verify every low confidence or uncertain field before preparing the action")
    if not db_pool:
        raise HTTPException(status_code=503, detail="Action store unavailable")
    reference, raw_date = field_value(doc, "invoiceNumber", "invoice_number"), field_value(doc, "invoiceDate", "invoice_date")
    if not reference or not raw_date or not doc.lineItems:
        raise HTTPException(status_code=422, detail="Invoice number, date, and at least one line item are required")
    try:
        date = date_parser(raw_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    totals = _totals(doc, field_value, tax_paise)
    canonical = {"invoice_date": date, "vendor_gstin": field_value(doc, "gstin", "vendorGstin", "vendor_gstin"),
                 "taxable_amount_paise": totals["taxable_paise"],
                 "cgst_paise": int(round(float(field_value(doc, "cgst") or 0) * 100)),
                 "sgst_paise": int(round(float(field_value(doc, "sgst") or 0) * 100)),
                 "igst_paise": int(round(float(field_value(doc, "igst") or 0) * 100)),
                 "other_charges_paise": totals["other_charges_paise"], "total_paise": totals["total_paise"],
                 "line_items": [item.model_dump() for item in doc.lineItems], "currency": "INR"}
    findings = validate_invoice(canonical)
    state = validation_state(findings)
    if state == "FAILED":
        raise HTTPException(status_code=422, detail={"code": "DETERMINISTIC_VALIDATION_FAILED", "findings": findings})
    if totals["other_charges_paise"]:
        raise HTTPException(status_code=422, detail={"code": "OTHER_CHARGES_NEED_LINES",
                                                     "message": "Add freight, discount, or other charges as invoice lines before posting."})
    provider = request.provider.upper()
    if provider not in {"ZOHO_BOOKS", "TALLY_PRIME"}:
        raise HTTPException(status_code=422, detail="Choose Zoho Books or Tally Prime")
    builder = _zoho if provider == "ZOHO_BOOKS" else _tally
    response, payload, installation_id, operation = await builder(doc, request, firm, db_pool, reference, date, totals)
    mappings = response.pop("mappings", {})
    action = None
    async with db_pool.acquire() as conn:
        current_version = await conn.fetchval(
            """SELECT version FROM accounting_drafts WHERE firm_id=$1 AND document_id=$2
               AND provider=$3 AND operation=$4""", firm.firm_id, doc.id, provider, operation,
        )
    draft_version = int(current_version or 0) + 1
    if payload:
        digest = compute_payload_hash(payload)
        action = await FinanceActionEngine(db_pool).propose_action(
            firm.firm_id, doc.clientId, provider, operation, payload,
            f"document:{doc.id}:{provider}:{digest[:24]}", proposed_by=firm.user_id, risk_level="HIGH",
            installation_id=installation_id, source_identity=doc.id, source_version=str(draft_version),
        )
    draft = await save_draft(
        db_pool, firm_id=firm.firm_id, client_id=doc.clientId, document_id=doc.id, provider=provider,
        operation=operation, status="ACTION_PROPOSED" if action else "NEEDS_MAPPING", payload=payload,
        mappings=mappings, totals=totals, validation_state=state, missing=response["missing_mappings"],
        action_id=str(action["id"]) if action else None, changed_by=firm.user_id, reason="Reviewer prepared purchase action",
    )
    if not action:
        return response | {"draft_version": draft["version"]}
    return response | {"action_id": str(action["id"]), "payload_hash": action["payload_hash"],
                       "draft_version": draft["version"]}
