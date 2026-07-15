"""Domain-reviewed activation of bundled official AY rules."""
import json

from fastapi import APIRouter, Depends, HTTPException

from api.deps import FirmContext, get_current_firm, get_db
from engines.income_tax_rules import OFFICIAL_SOURCE, official_rule, validate_rule

router=APIRouter(prefix="/api/itr/rules",tags=["itr-rules"])


@router.get("")
async def list_rules(assessment_year:str|None=None,firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    query="SELECT id,assessment_year,rule_key,version,source_citation,reviewed_by,reviewed_at FROM itr_rule_versions"
    args=[]
    if assessment_year:query+=" WHERE assessment_year=$1";args.append(assessment_year)
    query+=" ORDER BY assessment_year DESC,rule_key"
    async with db_pool.acquire() as conn:rows=await conn.fetch(query,*args)
    return [dict(row) for row in rows]


@router.post("/{assessment_year}/activate-official-default",status_code=201)
async def activate(assessment_year:str,firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    firm.require("compliance.review")
    try:rule=official_rule(assessment_year);validate_rule(rule)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    tests=[{"income_paise":0,"expected_tax_paise":0},{"regime":"NEW","rebate_threshold_paise":rule["new_rebate_threshold_paise"]}]
    async with db_pool.acquire() as conn:
        row=await conn.fetchrow(
            """INSERT INTO itr_rule_versions(assessment_year,rule_key,version,source_citation,rule,tests,reviewed_by)
               VALUES($1,'INDIVIDUAL_NORMAL_INCOME','firmos-2026.1',$2,$3::jsonb,$4::jsonb,$5)
               ON CONFLICT(assessment_year,rule_key,version) DO UPDATE SET reviewed_by=EXCLUDED.reviewed_by,
               reviewed_at=NOW() RETURNING id,assessment_year,rule_key,version,source_citation,reviewed_by,reviewed_at""",
            assessment_year,OFFICIAL_SOURCE,json.dumps(rule),json.dumps(tests),firm.user_id,
        )
    return dict(row)
