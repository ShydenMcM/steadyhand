"""The projection properties at their full count (#290). Each calls its unit stand-in's check, in
tests/engine/test_income_projection.py, on every case it draws."""

from decimal import Decimal

import test_income_projection as unit
from hypothesis import example, given, settings
from hypothesis import strategies as st

grosses = st.integers(min_value=12, max_value=10**9)
values = st.integers(min_value=1, max_value=10**11)
targets = st.integers(min_value=1, max_value=10**7)
rates = st.decimals(min_value=Decimal("-0.2"), max_value=Decimal("0.2"), places=4, allow_nan=False)
added = st.integers(min_value=0, max_value=10**6)

# Each example simulates up to three times 600 months, so these run fewer examples than the
# profile's default: the counts they were written with (#94).


@settings(max_examples=100)
@given(values, targets, added)
def test_a_zero_run_rate_cannot_be_projected(value: int, target: int, contribution: int) -> None:
    unit.test_a_zero_run_rate_cannot_be_projected(value, target, contribution)


@settings(max_examples=100)
@given(grosses, values, targets, rates, added, added)
# Found by hypothesis (#97): rounding the income down every month made Rp6 a month take 1.7 years
# where Rp5 took 1.6.
@example(gross=12, value=14, target=6, growth=Decimal(0), smaller=5, extra=1)
def test_a_larger_contribution_never_takes_longer(
    gross: int, value: int, target: int, growth: Decimal, smaller: int, extra: int
) -> None:
    unit.check_a_larger_contribution_never_takes_longer(
        gross, value, target, growth, smaller, extra
    )


@settings(max_examples=100)
@given(grosses, values, targets, rates, added)
def test_pessimistic_never_beats_base_and_base_never_beats_optimistic(
    gross: int, value: int, target: int, growth: Decimal, contribution: int
) -> None:
    unit.check_pessimistic_never_beats_base_and_base_never_beats_optimistic(
        gross, value, target, growth, contribution
    )
