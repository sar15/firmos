"""Activation of reviewed GST workpaper rules from official source material."""
import json

from fastapi import APIRouter, Depends, HTTPException

from api.deps import FirmContext, get_current_firm, get_db

router = APIRouter(prefix="/api/gst/rules", tags=["gst-rules"])
SOURCE = "https://tutorial.gst.gov.in/userguide/returns/Create_and_Submit_GSTR3B.htm"
DEFAULTS = {
    "GSTR1_BASE": {
        "effective_from":"2017-07-01",
        "rule":{"registered_customer":"GSTR-1 B2B","unregistered_customer":"GSTR-1 B2C"},
        "tests":[{"customer_gstin":"27ABCDE1234F1Z5","expected":"GSTR-1 B2B"},{"customer_gstin":"","expected":"GSTR-1 B2C"}],
    },
    "GSTR3B_BASE": {
        "effective_from":"2024-10-01",
        "rule":{"outward":"3.1(a)","reverse_charge":"3.1(d)","eligible_itc":"4(A)","reversal":"4(B)","ineligible":"4(D)","ims_reject":"ineligible","ims_pending":"review"},
        "tests":[{"ims":"ACCEPT","expected":"4(A)"},{"ims":"REJECT","expected":"4(D)"},{"ims":"PENDING","expected":"review"}],
    },
}


def _valid(item: dict) -> bool:
    return bool(item.get("rule") and item.get("tests") and item.get("effective_from"))


@router.get("")
async def list_rules(firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    async with db_pool.acquire() as conn:
        rows=await conn.fetch("SELECT id,rule_key,version,effective_from,effective_to,source_citation,reviewed_by,reviewed_at FROM gst_rule_versions ORDER BY rule_key,effective_from DESC")
    return [dict(row) for row in rows]


@router.post("/activate-official-defaults",status_code=201)
async def activate(firm:FirmContext=Depends(get_current_firm),db_pool=Depends(get_db)):
    firm.require("compliance.review")
    if not all(_valid(item) for item in DEFAULTS.values()):
        raise HTTPException(500,"Bundled GST rules failed validation")
    async with db_pool.acquire() as conn,conn.transaction():
        rows=[]
        for key,item in DEFAULTS.items():
            row=await conn.fetchrow(
                """INSERT INTO gst_rule_versions(jurisdiction,rule_key,version,effective_from,source_citation,rule,tests,reviewed_by)
                   VALUES('IN',$1,'firmos-2026.1',$2::date,$3,$4::jsonb,$5::jsonb,$6)
                   ON CONFLICT(jurisdiction,rule_key,version) DO UPDATE SET reviewed_by=EXCLUDED.reviewed_by,
                   reviewed_at=NOW() RETURNING id,rule_key,version,effective_from,reviewed_by,reviewed_at""",
                key,item["effective_from"],SOURCE,json.dumps(item["rule"]),json.dumps(item["tests"]),firm.user_id,
            )
            rows.append(dict(row))
    return {"rules":rows,"source_citation":SOURCE,"reviewed_by":firm.user_id}
