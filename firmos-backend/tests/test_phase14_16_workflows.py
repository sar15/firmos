"""Small checks for sales and manual-pack trust boundaries."""
from api.routes.gst_workpapers import _hash, _tables
from connectors.document_upload.extractor import raw_to_extracted_fields
from connectors.platform.types import CanonicalObject
from connectors.tally.canonical import compare_sales, validate_sales
from connectors.zoho_books.sales_invoice import build_sales_invoice, compare_sales_invoice
from core.sales_invoices.validation import validate_sales_invoice
from core.gst_workpapers.calculation import build_source_rows, summarize_tables
from core.itr_drafting import aggregate_sources, draft_amounts, reconciliation_pairs
from engines.income_tax_rules import calculate, official_rule


def sale(**changes):
    return {"invoice_number":"S-1","invoice_date":"2026-07-01","customer_name":"Acme",
      "seller_gstin":"27AAPFU0939F1ZV","customer_gstin":"27AAPFU0939F1ZV","place_of_supply_state":"27",
      "taxable_amount_paise":10000,"cgst_paise":900,"sgst_paise":900,"igst_paise":0,
      "other_charges_paise":0,"total_paise":11800,"line_items":[{"qty":1,"rate_paise":10000,"amount_paise":10000}],"currency":"INR"}|changes


def test_sales_validation_reuses_money_rules_and_requires_sales_identity():
    assert validate_sales_invoice(sale()) == []
    codes={x["code"] for x in validate_sales_invoice(sale(customer_name="",total_paise=11500))}
    assert {"CUSTOMER_NAME_REQUIRED","TOTAL_MISMATCH"}.issubset(codes)


def test_sales_extraction_keeps_review_specific_mapping_fields():
    raw={"vendor_name":"Acme","invoice_number":"S-1","invoice_date":"2026-07-01",
         "taxable_amount":"100","total":"100","revenue_item":"Sales","place_of_supply":"27"}
    fields={field.key:field.value for field in raw_to_extracted_fields(raw,1,is_sales=True)}
    assert fields["revenueHead"]=="Sales"
    assert fields["placeOfSupply"]=="27"


def test_zoho_sales_payload_is_stable_and_readback_bound():
    data={"organization_id":"org","customer_id":"c1","invoice_number":"S-1","date":"2026-07-01",
      "place_of_supply":"27","line_items":[{"account_id":"income","tax_id":"tax","rate_paise":10000,"quantity":1}],"total_paise":11800}
    request=build_sales_invoice(data)
    assert request.request_hash==build_sales_invoice(data).request_hash
    actual=CanonicalObject("sales_invoice","z1",{"organization_id":"org","customer_id":"c1","invoice_number":"S-1",
      "date":"2026-07-01","place_of_supply":"27","total_paise":11800})
    assert compare_sales_invoice(data,actual,"org")=={}


def test_tally_sales_readback_requires_type_identity_amount_and_entries():
    payload={"company_name":"Books","company_guid":"g1","party_ledger":"Acme","sales_ledger":"Sales",
      "date":"20260701","total_paise":11800,"entries":[{"ledger_name":"Acme","amount_paise":-11800},{"ledger_name":"Sales","amount_paise":11800}]}
    wanted=validate_sales(payload)
    actual={"remote_id":"firmos:a","company_guid":"g1","voucher_type":"Sales","date":"20260701",
      "party_ledger":"Acme","total_paise":11800,"entries":wanted["entries"]}
    assert compare_sales(payload,actual,"firmos:a")=={}
    actual["voucher_type"]="Purchase"
    assert "voucher_type" in compare_sales(payload,actual,"firmos:a")


def test_gst_totals_keep_sources_and_adjustments_distinct():
    rows=[{"table_key":"OUTWARD_SUPPLIES","amount_paise":10000}]
    adjustments=[{"table_key":"OUTWARD_SUPPLIES","amount_paise":-100}]
    table=_tables(rows,adjustments)["OUTWARD_SUPPLIES"]
    assert {key:table[key] for key in ("source_total_paise","adjustment_paise","total_paise")}=={
        "source_total_paise":10000,"adjustment_paise":-100,"total_paise":9900}
    assert _hash({"rows":rows})==_hash({"rows":rows})


def test_gstr3b_separates_rcm_itc_and_review_exceptions():
    purchase={"id":"p1","source_version":2,"taxable_paise":10000,"igst_paise":1800,
              "reverse_charge":True,"match_decision":"ACCEPTED","ims_decision":"ACCEPT"}
    rows,exceptions=build_source_rows([], [purchase], "GSTR3B")
    assert {row["table_key"] for row in rows}=={"3.1(d) Reverse charge","4(D) Ineligible ITC"}
    assert exceptions[0]["code"]=="RCM_PAYMENT_EVIDENCE_REQUIRED"
    totals=summarize_tables(rows,[{"table_key":"3.1(d) Reverse charge","component":"igst_paise","amount_paise":-100}])
    assert totals["3.1(d) Reverse charge"]["igst_paise"]==1700
    assert totals["3.1(d) Reverse charge"]["adjustment_paise"]==-100


def test_ay_2026_new_regime_rebate_and_slab_computation():
    rule=official_rule("2026-27")
    rebated=calculate(rule,income_paise=1200000_00)
    assert rebated["rebate_paise"]==60000_00
    assert rebated["rounded_payable_paise"]==0
    above_rebate=calculate(rule,income_paise=1300000_00)
    assert above_rebate["slab_tax_paise"]==75000_00
    assert above_rebate["rounded_payable_paise"]==78000_00


def test_itr_sources_aggregate_versions_and_keep_reconciliation_explainable():
    sources=[
        {"source_type":"FORM16","extracted_values":{"salary_income_paise":500000_00,"tds_paise":25000_00}},
        {"source_type":"FORM16A","extracted_values":{"tds_paise":5000_00}},
        {"source_type":"26AS","extracted_values":{"tds_paise":30000_00}},
        {"source_type":"AIS","extracted_values":{"reported_income_paise":600000_00,"bank_credits_paise":600000_00}},
        {"source_type":"BOOKS","extracted_values":{"reported_income_paise":600000_00,"business_income_paise":100000_00}},
        {"source_type":"BANK","extracted_values":{"bank_credits_paise":600000_00}},
    ]
    grouped=aggregate_sources(sources)
    assert draft_amounts(grouped)["tax_credits_paise"]==30000_00
    assert all(max(values.values())-min(values.values())==0 for _,values in reconciliation_pairs(grouped))
