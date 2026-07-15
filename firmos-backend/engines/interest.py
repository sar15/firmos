"""Interest computation engine — 234B and 234C. Deterministic, NO AI.

All amounts in PAISE. Interest rate is 1% per month.
"""

from datetime import date


# Interest rate per month (percentage)
INTEREST_RATE_PER_MONTH = 1.0


def calculate_234b_interest(
    total_tax_paise: int,
    advance_tax_paid_paise: int,
    assessment_year_end: date,
    actual_filing_date: date,
) -> dict:
    """Section 234B — interest for non-payment/short-payment of advance tax.
    
    Applicable when advance tax paid < 90% of assessed tax.
    Rate: 1% per month (part month = full month).
    Period: April 1 of AY to date of filing.
    """
    threshold = int(total_tax_paise * 0.9)
    shortfall = max(0, total_tax_paise - advance_tax_paid_paise)

    if advance_tax_paid_paise >= threshold:
        return {
            "section": "234B",
            "applicable": False,
            "interest": 0,
            "reason": "Advance tax >= 90% of assessed tax",
        }

    # Period: April 1 of AY to filing date
    ay_start = date(assessment_year_end.year, 4, 1)
    if actual_filing_date <= ay_start:
        months = 1  # minimum 1 month
    else:
        months = (actual_filing_date.year - ay_start.year) * 12 + (actual_filing_date.month - ay_start.month)
        if actual_filing_date.day > 1:
            months += 1  # part month = full month
        months = max(1, months)

    interest_paise = int(shortfall * INTEREST_RATE_PER_MONTH / 100) * months

    return {
        "section": "234B",
        "applicable": True,
        "shortfall": shortfall,
        "months": months,
        "rate_per_month": INTEREST_RATE_PER_MONTH,
        "interest": interest_paise,
    }


def calculate_234c_interest(
    total_tax_paise: int,
    installments_paid: list[dict],
) -> dict:
    """Section 234C — interest for deferment of advance tax installments.
    
    Due dates: 15 Jun (15%), 15 Sep (45%), 15 Dec (75%), 15 Mar (100%).
    Rate: 1% per month for 3 months per installment shortfall.
    """
    due_percentages = [
        ("15 Jun", 15, 3),
        ("15 Sep", 45, 3),
        ("15 Dec", 75, 3),
        ("15 Mar", 100, 1),  # last quarter: only 1 month interest
    ]

    total_interest = 0
    details = []

    cumulative_paid = 0
    for label, pct, penalty_months in due_percentages:
        required = int(total_tax_paise * pct / 100)

        # Find payment for this installment
        installment = next((i for i in installments_paid if i.get("label") == label), None)
        paid_this = installment.get("amount_paise", 0) if installment else 0
        cumulative_paid += paid_this

        shortfall = max(0, required - cumulative_paid)
        if shortfall > 0:
            interest = int(shortfall * INTEREST_RATE_PER_MONTH / 100) * penalty_months
            total_interest += interest
            details.append({
                "installment": label,
                "required": required,
                "paid_cumulative": cumulative_paid,
                "shortfall": shortfall,
                "months": penalty_months,
                "interest": interest,
            })

    return {
        "section": "234C",
        "applicable": total_interest > 0,
        "total_interest": total_interest,
        "details": details,
    }
