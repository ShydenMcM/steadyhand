"""The run rate properties at their full count (#290). Each calls its unit stand-in, in
tests/engine/test_income_run_rate.py, on every case it draws."""

from decimal import Decimal

import test_income_run_rate as unit
from hypothesis import assume, given
from hypothesis import strategies as st

prices = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal(10_000),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)
ratios = st.tuples(st.integers(1, 10), st.integers(1, 10)).filter(lambda pair: pair[0] != pair[1])


@given(prices, st.integers(min_value=1, max_value=10**7))
def test_without_a_later_split_a_dividend_is_priced_as_the_engine_credits_it(
    per_share: Decimal, shares: int
) -> None:
    unit.test_without_a_later_split_a_dividend_is_priced_as_the_engine_credits_it(per_share, shares)


@given(prices, st.integers(min_value=1, max_value=10**6), ratios, ratios)
def test_restating_across_two_splits_equals_restating_across_their_combined_ratio(
    per_share: Decimal, shares: int, first: tuple[int, int], second: tuple[int, int]
) -> None:
    # Two splits that cancel out combine into one that changes nothing, which Split refuses.
    assume(first[0] * second[0] != first[1] * second[1])
    unit.test_restating_across_two_splits_equals_restating_across_their_combined_ratio(
        per_share, shares, first, second
    )
