"""Interest computation engine — 234B and 234C. Deterministic, NO AI.

All amounts in PAISE. Interest rate is 1% per month.
"""

from datetime import date


# Interest rate per month (percentage)
INTEREST_RATE_PER_MONTH = 1.0


def _rule_119a_base(amount_paise: int) -> int:
    """Rule 119A: ignore a fraction of ₹100 before computing interest."""
    return max(0, int(amount_paise)) // 10_000 * 10_000


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
    threshold = total_tax_paise * 90 // 100
    shortfall = max(0, total_tax_paise - advance_tax_paid_paise)

    if advance_tax_paid_paise >= threshold:
        return {
            "section": "234B",
            "applicable": False,
            "interest": 0,
            "reason": "Advance tax >= 90% of assessed tax",
        }

    # assessment_year_end is 31 March of the assessment year. 234B starts
    # on the preceding 1 April, not a year later.
    ay_start = date(assessment_year_end.year - 1, 4, 1)
    if actual_filing_date < ay_start:
        months = 0
    else:
        months = (actual_filing_date.year - ay_start.year) * 12 + (actual_filing_date.month - ay_start.month)
        if actual_filing_date.day > 1:
            months += 1  # Rule 119A: part of a month is a full month here.
        months = max(1, months)
    interest_base = _rule_119a_base(shortfall)
    interest_paise = interest_base * int(INTEREST_RATE_PER_MONTH) // 100 * months

    return {
        "section": "234B",
        "applicable": True,
        "shortfall": shortfall,
        "interest_base": interest_base,
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
    # Statutory advance-tax due percentages are 15/45/75/100. Interest is
    # not charged for the June/September shortfall while the taxpayer has
    # paid at least 12%/36% respectively (section 234C).
    installments = [
        ("15 Jun", 15, 12, 3),
        ("15 Sep", 45, 36, 3),
        ("15 Dec", 75, 75, 3),
        ("15 Mar", 100, 100, 1),  # last quarter: only 1 month interest
    ]

    total_interest = 0
    details = []

    cumulative_paid = 0
    for label, due_pct, interest_pct, penalty_months in installments:
        required = total_tax_paise * due_pct // 100
        interest_threshold = total_tax_paise * interest_pct // 100

        # Find payment for this installment
        installment = next((i for i in installments_paid if i.get("label") == label), None)
        paid_this = installment.get("amount_paise", 0) if installment else 0
        cumulative_paid += paid_this

        shortfall = max(0, required - cumulative_paid)
        if cumulative_paid < interest_threshold and shortfall > 0:
            interest_base = _rule_119a_base(shortfall)
            interest = interest_base * int(INTEREST_RATE_PER_MONTH) // 100 * penalty_months
            total_interest += interest
            details.append({
                "installment": label,
                "required": required,
                "interest_threshold": interest_threshold,
                "paid_cumulative": cumulative_paid,
                "shortfall": shortfall,
                "interest_base": interest_base,
                "months": penalty_months,
                "interest": interest,
            })

    return {
        "section": "234C",
        "applicable": total_interest > 0,
        "total_interest": total_interest,
        "details": details,
    }
