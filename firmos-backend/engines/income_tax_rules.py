"""Assessment-year-specific individual tax rules and deterministic computation."""
from copy import deepcopy

OFFICIAL_SOURCE = "https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-1"
OLD_SLABS = [[250000_00,0],[500000_00,5],[1000000_00,20],[None,30]]
SURCHARGE = [[5000000_00,10],[10000000_00,15],[20000000_00,25],[50000000_00,37]]
DEFAULT_RULES = {
    "2025-26": {"new_slabs":[[300000_00,0],[700000_00,5],[1000000_00,10],[1200000_00,15],[1500000_00,20],[None,30]],
                "old_slabs":OLD_SLABS,"new_rebate_threshold_paise":700000_00,"new_rebate_max_paise":25000_00,
                "old_rebate_threshold_paise":500000_00,"old_rebate_max_paise":12500_00,"cess_percent":4,
                "surcharge":SURCHARGE,"new_surcharge_cap":25,"round_to_paise":1000},
    "2026-27": {"new_slabs":[[400000_00,0],[800000_00,5],[1200000_00,10],[1600000_00,15],[2000000_00,20],[2400000_00,25],[None,30]],
                "old_slabs":OLD_SLABS,"new_rebate_threshold_paise":1200000_00,"new_rebate_max_paise":60000_00,
                "old_rebate_threshold_paise":500000_00,"old_rebate_max_paise":12500_00,"cess_percent":4,
                "surcharge":SURCHARGE,"new_surcharge_cap":25,"round_to_paise":1000},
}


def official_rule(assessment_year: str) -> dict:
    if assessment_year not in DEFAULT_RULES:
        raise ValueError("No bundled official rule exists for this assessment year")
    return deepcopy(DEFAULT_RULES[assessment_year])


def validate_rule(rule: dict) -> None:
    for regime in ("new_slabs","old_slabs"):
        slabs=rule.get(regime) or []
        if not slabs or slabs[-1][0] is not None:
            raise ValueError(f"{regime} must end with an open slab")
        limits=[item[0] for item in slabs[:-1]]
        if limits!=sorted(limits) or any(rate<0 or rate>100 for _,rate in slabs):
            raise ValueError(f"{regime} is invalid")
    if int(rule.get("cess_percent",-1)) not in range(0,101):
        raise ValueError("cess_percent is invalid")


def _slab_tax(income: int, slabs: list[list[int|None]]) -> tuple[int,list[dict]]:
    tax,lower,details=0,0,[]
    for upper,rate in slabs:
        taxable=max(0,income-lower) if upper is None else max(0,min(income,upper)-lower)
        if taxable:
            amount=taxable*int(rate)//100;tax+=amount
            details.append({"from_paise":lower,"to_paise":upper,"rate_percent":rate,"taxable_paise":taxable,"tax_paise":amount})
        if upper is None or income<=upper:break
        lower=int(upper)
    return tax,details


def _surcharge(income: int, tax: int, rule: dict, regime: str, slabs: list) -> tuple[int,int,int]:
    rate=0;threshold=0
    for limit,candidate in rule.get("surcharge",[]):
        if income>int(limit):rate,threshold=int(candidate),int(limit)
    if regime=="NEW":rate=min(rate,int(rule.get("new_surcharge_cap",rate)))
    surcharge=tax*rate//100
    marginal_relief=0
    if rate and threshold:
        threshold_tax,_=_slab_tax(threshold,slabs)
        prior_rate=max((int(candidate) for limit,candidate in rule.get("surcharge",[]) if int(limit)<threshold),default=0)
        if regime=="NEW":prior_rate=min(prior_rate,int(rule.get("new_surcharge_cap",prior_rate)))
        permitted=threshold_tax+(threshold_tax*prior_rate//100)+(income-threshold)
        marginal_relief=max(0,tax+surcharge-permitted);surcharge-=marginal_relief
    return rate,surcharge,marginal_relief


def calculate(rule: dict, *, income_paise: int, deductions_paise: int=0, tax_credits_paise: int=0,
              regime: str="NEW", resident: bool=True, special_rate_income_paise: int=0,
              special_rate_tax_paise: int=0, new_regime_allowed_deductions_paise: int=0) -> dict:
    validate_rule(rule);regime=regime.upper()
    if regime not in {"NEW","OLD"}:raise ValueError("regime must be NEW or OLD")
    requested_deductions=max(0,int(deductions_paise))
    allowed_new=max(0,min(requested_deductions,int(new_regime_allowed_deductions_paise)))
    applied_deductions=requested_deductions if regime=="OLD" else allowed_new
    normal_taxable=max(0,int(income_paise)-applied_deductions);taxable=normal_taxable+int(special_rate_income_paise)
    slabs=rule[f"{regime.lower()}_slabs"];slab_tax,details=_slab_tax(normal_taxable,slabs)
    prefix=regime.lower();threshold=int(rule.get(f"{prefix}_rebate_threshold_paise",0));maximum=int(rule.get(f"{prefix}_rebate_max_paise",0))
    rebate=min(slab_tax,maximum) if resident and taxable<=threshold else 0
    normal_tax=slab_tax-rebate
    surcharge_rate,surcharge,marginal_relief=_surcharge(taxable,normal_tax+int(special_rate_tax_paise),rule,regime,slabs)
    cess=(normal_tax+int(special_rate_tax_paise)+surcharge)*int(rule["cess_percent"])//100
    gross=normal_tax+int(special_rate_tax_paise)+surcharge+cess
    payable=max(0,gross-int(tax_credits_paise));refund=max(0,int(tax_credits_paise)-gross)
    unit=int(rule.get("round_to_paise",1000));rounded=((payable+unit//2)//unit)*unit
    return {"income_paise":int(income_paise),"deductions_paise":applied_deductions,
            "deductions_disallowed_paise":requested_deductions-applied_deductions,
            "normal_taxable_income_paise":normal_taxable,"special_rate_income_paise":int(special_rate_income_paise),
            "taxable_income_paise":taxable,
            "regime":regime,"slab_details":details,"slab_tax_paise":slab_tax,"rebate_paise":rebate,
            "special_rate_tax_paise":int(special_rate_tax_paise),"surcharge_rate":surcharge_rate,
            "surcharge_paise":surcharge,"marginal_relief_paise":marginal_relief,"cess_paise":cess,
            "gross_tax_paise":gross,"tax_credits_paise":int(tax_credits_paise),"payable_paise":payable,
            "rounded_payable_paise":rounded,"refund_paise":refund,"rounding_rule":f"NEAREST_{unit//100}_RUPEES"}
