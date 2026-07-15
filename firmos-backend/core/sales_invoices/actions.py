"""Review-bound sales proposal creation over existing connector infrastructure."""
import json

from fastapi import HTTPException

from core.finance_actions import FinanceActionEngine, compute_payload_hash
from core.purchase_invoices.actions import _installation, _response, _totals
from core.purchase_invoices.drafts import save_draft
from core.purchase_invoices.validation import validation_state
from core.sales_invoices.validation import validate_sales_invoice


async def _zoho(doc,request,firm,db_pool,reference,date,totals,field_value):
    from api.routes.agent_tools import _zoho_plugin
    from api.routes.document_review import _line,_unique_match
    row,configuration=await _installation(db_pool,firm.firm_id,doc.clientId,"ZOHO_BOOKS")
    plugin=await _zoho_plugin(db_pool,firm.firm_id,doc.clientId)
    contacts=(await plugin.read("zoho.read.contacts.search",{"query":doc.vendorName}))["contacts"]
    accounts=(await plugin.read("zoho.read.chart_of_accounts",{}))["accounts"]
    taxes=(await plugin.read("zoho.read.taxes",{}))["taxes"]
    customers=[{"id":str(x["contact_id"]),"label":str(x.get("contact_name", ""))} for x in contacts if x.get("contact_id")]
    income=[{"id":str(x["account_id"]),"label":str(x.get("account_name", ""))} for x in accounts
            if x.get("account_id") and x.get("account_type") in ("income","other_income")]
    tax_options=[{"id":str(x["tax_id"]),"label":str(x.get("tax_name_formatted") or x.get("tax_name") or "Tax")} for x in taxes if x.get("tax_id") and not x.get("is_inactive")]
    customer=request.customer_id or _unique_match(customers,doc.vendorName)
    account=request.account_id or _unique_match(income,field_value(doc,"revenueHead","incomeHead","income_head"))
    missing=([] if customer in {x["id"] for x in customers} else ["customer_id"])+([] if account in {x["id"] for x in income} else ["account_id"])
    if totals["tax_paise"] and request.tax_id not in {x["id"] for x in tax_options}: missing.append("tax_id")
    response=_response("ZOHO_BOOKS",customer_candidates=customers,account_candidates=income,tax_candidates=tax_options,
                       missing_mappings=missing,status="NEEDS_MAPPING" if missing else "ACTION_PROPOSED")
    mappings={"customer_id":customer,"account_id":account,"tax_id":request.tax_id}
    operation="zoho.write.sales_invoice.create"
    if missing:return response|{"mappings":mappings},{},str(row["id"]),operation
    lines=[_line(item,"account_id",account,request.tax_id) for item in doc.lineItems]
    payload={"organization_id":configuration["organization_id"],"customer_id":customer,"invoice_number":reference,
             "reference_number":f"FIRMOS-{doc.id}","date":date,
             "place_of_supply":field_value(doc,"placeOfSupply","place_of_supply"),"line_items":lines,
             "subtotal_paise":totals["taxable_paise"],"tax_total_paise":totals["tax_paise"],"total_paise":totals["total_paise"]}
    from connectors.zoho_books.sales_invoice import build_sales_invoice
    build_sales_invoice(payload)
    return response|{"mappings":mappings},payload,str(row["id"]),operation


async def _tally(doc,request,firm,db_pool,reference,date,totals,field_value):
    row,configuration=await _installation(db_pool,firm.firm_id,doc.clientId,"TALLY_PRIME")
    async with db_pool.acquire() as conn:
        ledger_rows=await conn.fetch("SELECT name,parent FROM tally_ledgers WHERE firm_id=$1 AND client_id=$2 AND installation_id=$3 AND active ORDER BY name LIMIT 500",firm.firm_id,doc.clientId,row["id"])
    options=[{"id":str(x["name"]),"label":str(x["name"])} for x in ledger_rows];names={x["id"] for x in options}
    party,sales=request.party_ledger,request.sales_ledger
    missing=([] if party in names else ["party_ledger"])+([] if sales in names else ["sales_ledger"])
    components={key:int(round(float(field_value(doc,key.lower()) or 0)*100)) for key in ("CGST","SGST","IGST")}
    taxes={"CGST":request.cgst_ledger,"SGST":request.sgst_ledger,"IGST":request.igst_ledger}
    for key,amount in components.items():
        if amount and taxes[key] not in names:missing.append(f"{key.lower()}_ledger")
    response=_response("TALLY_PRIME",customer_candidates=options,account_candidates=options,missing_mappings=missing,status="NEEDS_MAPPING" if missing else "ACTION_PROPOSED")
    mappings={"party_ledger":party,"sales_ledger":sales,**{f"{k.lower()}_ledger":v for k,v in taxes.items() if components[k]}}
    operation="tally.write.sales_voucher.create"
    if missing:return response|{"mappings":mappings},{},str(row["id"]),operation
    entries=[{"ledger_name":party,"amount_paise":-totals["total_paise"]},{"ledger_name":sales,"amount_paise":totals["taxable_paise"]},
             *[{"ledger_name":taxes[k],"amount_paise":amount} for k,amount in components.items() if amount]]
    payload={"date":date.replace("-",""),"voucher_number":reference,"reference":reference,"party_ledger":party,
             "sales_ledger":sales,"total_paise":totals["total_paise"],"taxable_paise":totals["taxable_paise"],
             "tax_total_paise":totals["tax_paise"],"entries":entries,"company_name":configuration.get("company_name"),
             "company_guid":configuration.get("company_guid"),"place_of_supply":field_value(doc,"placeOfSupply","place_of_supply"),
             "narration":f"firmOS evidence: {doc.id}"}
    from connectors.tally.write_engine import build_import_data_envelope
    build_import_data_envelope(payload["date"],"Sales",party,f"draft:{doc.id}",[
        {"ledger":x["ledger_name"],"is_debit":x["amount_paise"]<0,"amount_paise":x["amount_paise"]} for x in entries])
    return response|{"mappings":mappings},payload,str(row["id"]),operation


async def propose_sale(doc,request,firm,db_pool,*,field_value,date_parser,tax_paise):
    if doc.docKind not in {"SALES_INVOICE","CUSTOMER_INVOICE"}:raise HTTPException(409,"This document is not a sales invoice")
    if any(field.level!="HIGH" for field in doc.fields):raise HTTPException(400,"Verify every uncertain field before preparing the action")
    reference,raw_date=field_value(doc,"invoiceNumber","invoice_number"),field_value(doc,"invoiceDate","invoice_date")
    if not reference or not raw_date or not doc.lineItems:raise HTTPException(422,"Invoice number, date and lines are required")
    try:date=date_parser(raw_date)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    totals=_totals(doc,field_value,tax_paise)
    canonical={"invoice_number":reference,"invoice_date":date,"customer_name":doc.vendorName,
               "seller_gstin":field_value(doc,"sellerGstin","clientGstin"),"customer_gstin":field_value(doc,"customerGstin","gstin"),
               "place_of_supply_state":field_value(doc,"placeOfSupply","place_of_supply"),"taxable_amount_paise":totals["taxable_paise"],
               "cgst_paise":int(round(float(field_value(doc,"cgst") or 0)*100)),"sgst_paise":int(round(float(field_value(doc,"sgst") or 0)*100)),
               "igst_paise":int(round(float(field_value(doc,"igst") or 0)*100)),"other_charges_paise":totals["other_charges_paise"],
               "total_paise":totals["total_paise"],"line_items":[x.model_dump() for x in doc.lineItems],"currency":"INR"}
    findings=validate_sales_invoice(canonical);state=validation_state(findings)
    if state=="FAILED":raise HTTPException(422,{"code":"DETERMINISTIC_VALIDATION_FAILED","findings":findings})
    provider=request.provider.upper()
    if provider not in {"ZOHO_BOOKS","TALLY_PRIME"}:raise HTTPException(422,"Choose Zoho Books or Tally Prime")
    builder=_zoho if provider=="ZOHO_BOOKS" else _tally
    response,payload,installation_id,operation=await builder(doc,request,firm,db_pool,reference,date,totals,field_value)
    mappings=response.pop("mappings",{});action=None
    async with db_pool.acquire() as conn:
        current=await conn.fetchval("SELECT version FROM accounting_drafts WHERE firm_id=$1 AND document_id=$2 AND provider=$3 AND operation=$4",firm.firm_id,doc.id,provider,operation)
    version=int(current or 0)+1
    if payload:
        digest=compute_payload_hash(payload)
        action=await FinanceActionEngine(db_pool).propose_action(firm.firm_id,doc.clientId,provider,operation,payload,
          f"document:{doc.id}:{provider}:{digest[:24]}",proposed_by=firm.user_id,risk_level="HIGH",installation_id=installation_id,source_identity=doc.id,source_version=str(version))
    draft=await save_draft(db_pool,firm_id=firm.firm_id,client_id=doc.clientId,document_id=doc.id,provider=provider,
      operation=operation,status="ACTION_PROPOSED" if action else "NEEDS_MAPPING",payload=payload,mappings=mappings,totals=totals,
      validation_state=state,missing=response["missing_mappings"],action_id=str(action["id"]) if action else None,
      changed_by=firm.user_id,reason="Reviewer prepared sales action")
    return response|({"action_id":str(action["id"]),"payload_hash":action["payload_hash"],"draft_version":draft["version"]} if action else {"draft_version":draft["version"]})
