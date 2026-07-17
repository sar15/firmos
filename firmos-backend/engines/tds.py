"""TDS computation engine — section rates. Deterministic, NO AI.

All amounts in PAISE.
"""

# TDS rates per section (as percentages)
TDS_RATES: dict[str, float] = {
    "194A": 10.0,    # Interest (other than on securities)
    "194C": 1.0,     # Contractor (individual/HUF — 1%, others — 2%)
    "194C_COMPANY": 2.0,
    "194H": 5.0,     # Commission / brokerage
    "194I_LAND": 10.0,  # Rent — land/building
    "194I_PLANT": 2.0,  # Rent — plant/machinery/equipment
    "194J_TECH": 2.0,   # Technical services
    "194J_PROF": 10.0,  # Professional services
    "194Q": 0.1,     # Purchase of goods (> ₹50L)
    "192": 0.0,      # Salary — slab rates, computed separately via tax.py
}

# Threshold limits (in paise) below which TDS is NOT applicable
TDS_THRESHOLDS: dict[str, int] = {
    "194A": 4000000,       # ₹40,000
    "194C": 3000000,       # ₹30,000 single / ₹1,00,000 aggregate
    "194H": 1500000,       # ₹15,000
    "194I_LAND": 24000000, # ₹2,40,000
    "194I_PLANT": 24000000,
    "194J_TECH": 3000000,  # ₹30,000
    "194J_PROF": 3000000,
    "194Q": 500000000,     # ₹50,00,000
}


def calculate_tds(
    section: str,
    gross_amount_paise: int,
    pan_available: bool = True,
    prior_period_amount_paise: int = 0,
    buyer_prior_year_turnover_paise: int | None = None,
) -> dict:
    """Compute TDS for a payment.
    
    If PAN is not available, section 206AA applies the higher statutory rate.
    Returns dict with tds_amount, net_amount (both in paise).
    """
    if section not in TDS_RATES:
        raise ValueError(f"Unknown TDS section: {section}")

    rate = TDS_RATES[section]

    # Higher rate if PAN not available (section 206AA)
    if not pan_available:
        # 194Q has an express 5% substitution; other supported sections use
        # the 20% statutory floor (or a higher applicable rate).
        rate = max(rate, 5.0 if section == "194Q" else 20.0)

    threshold = TDS_THRESHOLDS.get(section, 0)
    if section == "194Q":
        if buyer_prior_year_turnover_paise is None:
            return {
                "section": section, "gross_amount": gross_amount_paise,
                "tds_amount": 0, "net_amount": gross_amount_paise,
                "needs_context": True,
                "reason": "Prior-year buyer turnover is required for Section 194Q.",
            }
        if buyer_prior_year_turnover_paise <= 10000000000:
            return {
                "section": section, "gross_amount": gross_amount_paise,
                "tds_amount": 0, "net_amount": gross_amount_paise,
                "reason": "Buyer prior-year turnover does not exceed ₹10 crore.",
            }
        prior = max(0, prior_period_amount_paise)
        cumulative = prior + gross_amount_paise
        taxable_amount = max(0, cumulative - threshold) - max(0, prior - threshold)
    else:
        taxable_amount = gross_amount_paise

    if taxable_amount <= 0 or (section != "194Q" and gross_amount_paise <= threshold):
        return {
            "section": section,
            "gross_amount": gross_amount_paise,
            "rate": 0.0,
            "tds_amount": 0,
            "net_amount": gross_amount_paise,
            "reason": f"Below threshold of ₹{threshold // 100}",
        }

    tds_paise = int(taxable_amount * rate / 100)

    return {
        "section": section,
        "gross_amount": gross_amount_paise,
        "taxable_amount": taxable_amount,
        "rate": rate,
        "tds_amount": tds_paise,
        "net_amount": gross_amount_paise - tds_paise,
    }
