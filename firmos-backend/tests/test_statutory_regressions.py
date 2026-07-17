"""Boundary regressions for statutory calculations."""

import pytest

from engines.income_tax_rules import calculate, official_rule
from engines.tax import calculate_income_tax
from engines.tds import calculate_tds


@pytest.mark.parametrize(
    ("income_paise", "expected_rate"),
    [
        (5000000_00, 0),
        (5000000_00 + 1, 10),
        (10000000_00 + 1, 15),
        (20000000_00 + 1, 25),
        (50000000_00 + 1, 37),
    ],
)
def test_old_regime_surcharge_boundaries(income_paise: int, expected_rate: int):
    assert calculate_income_tax(income_paise, regime="OLD")["surcharge_rate"] == expected_rate


@pytest.mark.parametrize("threshold_paise", [5000000_00, 10000000_00, 20000000_00, 50000000_00])
def test_old_regime_marginal_relief_limits_each_surcharge_step(threshold_paise: int):
    at_threshold = calculate_income_tax(threshold_paise, regime="OLD")
    just_above = calculate_income_tax(threshold_paise + 1, regime="OLD")
    threshold_tax = at_threshold["base_tax"] + at_threshold["surcharge"]
    relieved_tax = just_above["base_tax"] + just_above["surcharge"]
    assert relieved_tax == threshold_tax + 1


def test_new_regime_never_exceeds_25_percent_surcharge():
    assert calculate_income_tax(50000000_00 + 1, regime="NEW")["surcharge_rate"] == 25


def test_new_regime_only_applies_explicitly_classified_allowed_deductions():
    rule = official_rule("2026-27")
    blocked = calculate(rule, income_paise=1500000_00, deductions_paise=100000_00, regime="NEW")
    allowed = calculate(
        rule, income_paise=1500000_00, deductions_paise=100000_00,
        new_regime_allowed_deductions_paise=40000_00, regime="NEW",
    )
    assert blocked["deductions_paise"] == 0
    assert blocked["deductions_disallowed_paise"] == 100000_00
    assert allowed["deductions_paise"] == 40000_00
    assert allowed["deductions_disallowed_paise"] == 60000_00


def test_old_regime_still_applies_the_full_deduction_amount():
    result = calculate(
        official_rule("2026-27"), income_paise=1500000_00,
        deductions_paise=100000_00, regime="OLD",
    )
    assert result["deductions_paise"] == 100000_00
    assert result["deductions_disallowed_paise"] == 0


def test_194q_requires_buyer_eligibility_context_instead_of_guessing():
    missing = calculate_tds("194Q", 100000_00)
    ineligible = calculate_tds(
        "194Q", 100000_00, prior_period_amount_paise=6000000_00,
        buyer_prior_year_turnover_paise=10000000000,
    )
    assert missing["needs_context"] is True
    assert missing["tds_amount"] == 0
    assert ineligible["tds_amount"] == 0


def test_194q_taxes_the_current_payment_once_when_threshold_was_already_crossed():
    result = calculate_tds(
        "194Q", 200000_00, prior_period_amount_paise=6000000_00,
        buyer_prior_year_turnover_paise=11000000000,
    )
    assert result["taxable_amount"] == 200000_00
    assert result["tds_amount"] == 200_00


def test_194q_uses_50_lakh_threshold_and_only_the_excess():
    eligible_buyer = 11000000000
    below = calculate_tds(
        "194Q", 10000000, prior_period_amount_paise=490000000,
        buyer_prior_year_turnover_paise=eligible_buyer,
    )
    result = calculate_tds(
        "194Q", 20000000, prior_period_amount_paise=490000000,
        buyer_prior_year_turnover_paise=eligible_buyer,
    )
    assert below["tds_amount"] == 0
    assert result["taxable_amount"] == 10000000
    assert result["tds_amount"] == 10000


def test_206aa_uses_special_194q_rate_and_20_percent_floor_elsewhere():
    purchases = calculate_tds(
        "194Q", 20000000, pan_available=False, prior_period_amount_paise=490000000,
        buyer_prior_year_turnover_paise=11000000000,
    )
    contractor = calculate_tds("194C", 5000000, pan_available=False)
    assert purchases["rate"] == 5.0
    assert purchases["tds_amount"] == 500000
    assert contractor["rate"] == 20.0
