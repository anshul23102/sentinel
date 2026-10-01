"""Pure-math tests for slo.py — each assertion checks a known SRE ground truth
(full budget at zero errors, exhausted at exactly the SLO, negative once
breached), matching the style of test_seasonal.py."""
import pytest

from slo import error_budget_remaining, burn_rate


def test_full_budget_when_no_errors():
    assert error_budget_remaining(0.99, 1.0) == 1.0


def test_budget_exhausted_at_slo():
    assert error_budget_remaining(0.99, 0.99) == pytest.approx(0.0)


def test_budget_negative_when_breached():
    # 2% errors against a 1% budget -> double the allowance -> -1.0
    assert error_budget_remaining(0.99, 0.98) == pytest.approx(-1.0)


def test_burn_rate_on_pace():
    assert burn_rate(0.99, 0.01) == pytest.approx(1.0)


def test_burn_rate_too_fast():
    assert burn_rate(0.99, 0.05) == pytest.approx(5.0)


def test_burn_rate_zero_when_no_errors():
    assert burn_rate(0.99, 0.0) == 0.0


def test_degenerate_target_leaves_no_budget():
    assert error_budget_remaining(1.0, 0.5) == 0.0
    assert burn_rate(1.0, 0.5) == 0.0
