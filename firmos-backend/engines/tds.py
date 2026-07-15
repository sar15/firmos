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
    "194Q": 5000000000,    # ₹50,00,000
}


def calculate_tds(
    section: str,
    gross_amount_paise: int,
    pan_available: bool = True,
) -> dict:
    """Compute TDS for a payment.
    
    If PAN not available, rate doubles (max 20%).
    Returns dict with tds_amount, net_amount (both in paise).
    """
    if section not in TDS_RATES:
        raise ValueError(f"Unknown TDS section: {section}")

    rate = TDS_RATES[section]

    # Higher rate if PAN not available (section 206AA)
    if not pan_available:
        rate = min(rate * 2, 20.0)

    # Check threshold
    threshold = TDS_THRESHOLDS.get(section, 0)
    if gross_amount_paise <= threshold:
        return {
            "section": section,
            "gross_amount": gross_amount_paise,
            "rate": 0.0,
            "tds_amount": 0,
            "net_amount": gross_amount_paise,
            "reason": f"Below threshold of ₹{threshold // 100}",
        }

    tds_paise = int(gross_amount_paise * rate / 100)

    return {
        "section": section,
        "gross_amount": gross_amount_paise,
        "rate": rate,
        "tds_amount": tds_paise,
        "net_amount": gross_amount_paise - tds_paise,
    }
