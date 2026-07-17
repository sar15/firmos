"""Income tax computation engine — slabs, surcharge, cess. Deterministic, NO AI.

FY 2024-25 (AY 2025-26) new regime rates. All amounts in PAISE.
Needed for ITR_APPROVAL decisions.
"""


# New regime slabs FY 2024-25 (Budget 2024)
# (upper_limit_paise, rate_percentage)
NEW_REGIME_SLABS = [
    (300000_00, 0),     # 0 - 3L: nil
    (700000_00, 5),     # 3L - 7L: 5%
    (1000000_00, 10),   # 7L - 10L: 10%
    (1200000_00, 15),   # 10L - 12L: 15%
    (1500000_00, 20),   # 12L - 15L: 20%
    (None, 30),         # > 15L: 30%
]

# Old regime slabs
OLD_REGIME_SLABS = [
    (250000_00, 0),     # 0 - 2.5L: nil
    (500000_00, 5),     # 2.5L - 5L: 5%
    (1000000_00, 20),   # 5L - 10L: 20%
    (None, 30),         # > 10L: 30%
]

# Surcharge thresholds (on income, not tax)
SURCHARGE_RATES = [
    (5000000_00, 0),       # <= 50L: nil
    (10000000_00, 10),     # 50L - 1Cr: 10%
    (20000000_00, 15),     # 1Cr - 2Cr: 15%
    (50000000_00, 25),     # 2Cr - 5Cr: 25%
    (None, 37),            # > 5Cr: 37%
]

# New regime surcharge capped at 25% for income > 2Cr
NEW_REGIME_SURCHARGE_CAP = 25

# Health & Education Cess
CESS_RATE = 4  # percentage


def _slab_tax_amount(taxable_income_paise: int, slabs: list[tuple[int | None, int]]) -> int:
    """Return tax before rebate, surcharge and cess for the supplied slabs."""
    remaining = taxable_income_paise
    tax = 0
    previous_limit = 0
    for upper_limit, rate in slabs:
        taxable_in_slab = remaining if upper_limit is None else min(remaining, upper_limit - previous_limit)
        if taxable_in_slab <= 0:
            break
        tax += taxable_in_slab * rate // 100
        remaining -= taxable_in_slab
        previous_limit = upper_limit or previous_limit
        if remaining <= 0:
            break
    return tax


def _surcharge_band(taxable_income_paise: int, regime: str) -> tuple[int, int | None, int]:
    """Return the surcharge rate, its threshold, and the preceding rate.

    The threshold is retained for marginal-relief calculation.  Under the new
    regime 25% continues above Rs. 5 crore, so that boundary does not create a
    fresh surcharge step or a fresh marginal-relief calculation.
    """
    if taxable_income_paise <= 5000000_00:
        return 0, None, 0
    if taxable_income_paise <= 10000000_00:
        return 10, 5000000_00, 0
    if taxable_income_paise <= 20000000_00:
        return 15, 10000000_00, 10
    if taxable_income_paise <= 50000000_00 or regime == "NEW":
        return 25, 20000000_00, 15
    return 37, 50000000_00, 25


def calculate_income_tax(
    taxable_income_paise: int,
    regime: str = "NEW",
) -> dict:
    """Compute income tax + surcharge + cess.
    
    regime: "NEW" or "OLD"
    Returns all values in paise.
    """
    slabs = NEW_REGIME_SLABS if regime == "NEW" else OLD_REGIME_SLABS
    remaining = taxable_income_paise
    tax = 0
    slab_details = []
    prev_limit = 0

    for upper, rate in slabs:
        if upper is None:
            taxable_in_slab = remaining
        else:
            taxable_in_slab = min(remaining, upper - prev_limit)

        if taxable_in_slab <= 0:
            break

        tax_in_slab = int(taxable_in_slab * rate / 100)
        tax += tax_in_slab
        slab_details.append({
            "range": f"{prev_limit // 100} - {(upper // 100) if upper else '∞'}",
            "rate": rate,
            "taxable": taxable_in_slab,
            "tax": tax_in_slab,
        })

        remaining -= taxable_in_slab
        prev_limit = upper or prev_limit

        if remaining <= 0:
            break

    # Section 87A rebate (new regime): if income <= 7L, tax = 0
    rebate = 0
    if regime == "NEW" and taxable_income_paise <= 700000_00:
        rebate = tax
        tax = 0

    # Surcharge and marginal relief.  A surcharge bracket must not make tax
    # plus surcharge exceed the tax at the preceding threshold plus the amount
    # by which income exceeds that threshold.
    surcharge_rate, surcharge_threshold, preceding_surcharge_rate = _surcharge_band(taxable_income_paise, regime)
    unrelieved_surcharge = tax * surcharge_rate // 100
    marginal_relief = 0
    if surcharge_threshold is not None:
        tax_at_threshold = _slab_tax_amount(surcharge_threshold, slabs)
        maximum_tax_with_surcharge = (
            tax_at_threshold
            + tax_at_threshold * preceding_surcharge_rate // 100
            + taxable_income_paise
            - surcharge_threshold
        )
        marginal_relief = max(0, tax + unrelieved_surcharge - maximum_tax_with_surcharge)
    surcharge = unrelieved_surcharge - marginal_relief

    # Cess on (tax + surcharge)
    cess = int((tax + surcharge) * CESS_RATE / 100)

    total_tax = tax + surcharge + cess

    return {
        "taxable_income": taxable_income_paise,
        "regime": regime,
        "base_tax": tax,
        "rebate_87a": rebate,
        "surcharge_rate": surcharge_rate,
        "surcharge": surcharge,
        "marginal_relief": marginal_relief,
        "cess_rate": CESS_RATE,
        "cess": cess,
        "total_tax": total_tax,
        "slab_details": slab_details,
    }
