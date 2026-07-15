"""Small, explainable helpers for ITR source reconciliation and schedules."""
import json


def values(row) -> dict:
    value=row["extracted_values"]
    return json.loads(value) if isinstance(value,str) else dict(value or {})


def aggregate_sources(rows) -> dict[str,dict[str,int]]:
    totals: dict[str,dict[str,int]]={}
    for row in rows:
        kind=str(row["source_type"]);bucket=totals.setdefault(kind,{})
        for key,value in values(row).items():
            if key.endswith("_paise"):
                bucket[key]=bucket.get(key,0)+int(value or 0)
    return totals


def reconciliation_pairs(by_type: dict[str,dict[str,int]]) -> list[tuple[str,dict[str,int]]]:
    form_tds=by_type.get("FORM16",{}).get("tds_paise",0)+by_type.get("FORM16A",{}).get("tds_paise",0)
    return [
        ("REPORTED_INCOME",{"AIS":by_type.get("AIS",{}).get("reported_income_paise",0),"BOOKS":by_type.get("BOOKS",{}).get("reported_income_paise",0)}),
        ("TDS",{"26AS":by_type.get("26AS",{}).get("tds_paise",0),"FORMS":form_tds}),
        ("BANK_CREDITS",{"BANK":by_type.get("BANK",{}).get("bank_credits_paise",0),"AIS":by_type.get("AIS",{}).get("bank_credits_paise",0)}),
    ]


def draft_amounts(by_type: dict[str,dict[str,int]]) -> dict[str,int]:
    salary=by_type.get("FORM16",{}).get("salary_income_paise",0)
    business=by_type.get("BOOKS",{}).get("business_income_paise",0)
    other=by_type.get("AIS",{}).get("other_income_paise",0)
    gains=by_type.get("AIS",{}).get("capital_gains_paise",0)
    deductions=by_type.get("FORM16",{}).get("deductions_paise",0)+by_type.get("BOOKS",{}).get("deductions_paise",0)
    form_tds=by_type.get("FORM16",{}).get("tds_paise",0)+by_type.get("FORM16A",{}).get("tds_paise",0)
    credits=max(by_type.get("26AS",{}).get("tds_paise",0),form_tds)+by_type.get("26AS",{}).get("tcs_paise",0)
    credits+=by_type.get("BOOKS",{}).get("advance_tax_paise",0)+by_type.get("BOOKS",{}).get("self_assessment_tax_paise",0)
    return {"salary_income_paise":salary,"business_income_paise":business,"other_income_paise":other,
            "capital_gains_paise":gains,"deductions_paise":deductions,"tax_credits_paise":credits}


def source_links(rows, source_type: str) -> list[dict]:
    return [{"source_id":str(row["id"]),"source_type":source_type,"source_version":str(row["source_version"])}
            for row in rows if str(row["source_type"])==source_type]
