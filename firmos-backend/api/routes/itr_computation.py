"""Draft AY schedules and computation from classified, reconciled sources."""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import FirmContext, get_current_firm, get_db
from api.routes.itr_workspaces import _require_authorization
from core.itr_drafting import aggregate_sources, draft_amounts, source_links
from engines.income_tax_rules import calculate

router=APIRouter(prefix="/api/itr/workspaces",tags=["itr-computation"])


class DraftRequest(BaseModel):
    regime:str=Field(pattern=r"^(NEW|OLD)$")
    resident:bool=True
    special_rate_tax_paise:int=Field(default=0,ge=0)


@router.post("/{workspace_id}/draft")
async def draft(workspace_id:str,body:DraftRequest,firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    firm.require("books.propose")
    async with db_pool.acquire() as conn,conn.transaction():
        workspace=await conn.fetchrow("SELECT * FROM itr_workspaces WHERE id=$1::uuid AND firm_id=$2 FOR UPDATE",workspace_id,firm.firm_id)
        if not workspace:raise HTTPException(404,"Workspace not found")
        await _require_authorization(conn,workspace_id,"PREPARE",firm.user_id)
        reconciliation=await conn.fetchrow(
            "SELECT count(*) AS total,count(*) FILTER (WHERE status='MATCHED') AS matched FROM itr_reconciliation_items WHERE workspace_id=$1",
            workspace["id"],
        )
        if reconciliation["total"]<3 or reconciliation["matched"]!=reconciliation["total"]:
            raise HTTPException(409,"Reconcile all required sources before drafting")
        rule_row=await conn.fetchrow("SELECT id,rule FROM itr_rule_versions WHERE assessment_year=$1 AND rule_key='INDIVIDUAL_NORMAL_INCOME' ORDER BY reviewed_at DESC LIMIT 1",workspace["assessment_year"])
        if not rule_row:raise HTTPException(409,"Activate and review the assessment-year rule before drafting")
        sources=await conn.fetch("SELECT id,source_type,source_version,extracted_values FROM itr_sources WHERE workspace_id=$1 ORDER BY created_at",workspace["id"])
        if not sources:raise HTTPException(409,"Classified source evidence is required")
        amounts=draft_amounts(aggregate_sources(sources));income=sum(amounts[key] for key in ("salary_income_paise","business_income_paise","other_income_paise"))
        if amounts["capital_gains_paise"] and not body.special_rate_tax_paise:
            raise HTTPException(409,"Enter reviewed special-rate tax for the capital-gains schedule")
        rule=json.loads(rule_row["rule"]) if isinstance(rule_row["rule"],str) else dict(rule_row["rule"])
        computation=calculate(rule,income_paise=income,deductions_paise=amounts["deductions_paise"],
                              tax_credits_paise=amounts["tax_credits_paise"],regime=body.regime,
                              resident=body.resident,special_rate_income_paise=amounts["capital_gains_paise"],
                              special_rate_tax_paise=body.special_rate_tax_paise)
        await conn.execute("DELETE FROM itr_schedule_lines WHERE workspace_id=$1",workspace["id"])
        specs=[("SALARY","income",amounts["salary_income_paise"],"FORM16"),("BUSINESS","income",amounts["business_income_paise"],"BOOKS"),("OTHER_SOURCES","income",amounts["other_income_paise"],"AIS"),("CAPITAL_GAINS","income",amounts["capital_gains_paise"],"AIS"),("DEDUCTIONS","deductions",-amounts["deductions_paise"],"FORM16"),("TAX_CREDITS","credits",-amounts["tax_credits_paise"],"26AS")]
        for schedule,line,amount,source_type in specs:
            links=source_links(sources,source_type)
            if amount and not links:raise HTTPException(409,f"{schedule} has no source link")
            if amount:await conn.execute("INSERT INTO itr_schedule_lines(workspace_id,firm_id,schedule_key,line_key,amount_paise,source_links,rule_id,explanation) VALUES($1,$2,$3,$4,$5,$6::jsonb,$7,$8)",workspace["id"],firm.firm_id,schedule,line,amount,json.dumps(links),rule_row["id"],f"Drafted from classified {source_type} source values")
        row=await conn.fetchrow("UPDATE itr_workspaces SET computation=$1::jsonb,status='NEEDS_REVIEW',stale=false,updated_at=NOW() WHERE id=$2 RETURNING *",json.dumps(computation),workspace["id"])
    return dict(row)
