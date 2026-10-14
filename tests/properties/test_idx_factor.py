"""The adjustment factor property at its full count (#290). It calls its unit stand-in, in
tests/idx/test_factor.py, on every case it draws."""

from datetime import date, timedelta
from decimal import Decimal

import test_factor as unit
from hypothesis import example, given
from hypothesis import strategies as st

ERAS = (date(2015, 3, 2), date(2017, 3, 1), unit.VERIFIED_DAY)


@st.composite
def true_run(draw: st.DrawFn) -> tuple[date, list[list[int]]]:
    """Five to eight days of traded prices on one era's grid, within a factor of two."""
    first = draw(st.sampled_from(ERAS))
    base = draw(st.integers(min_value=50, max_value=20_000))
    days = draw(st.integers(min_value=5, max_value=8))
    prices: list[list[int]] = []
    for offset in range(days):
        day = first + timedelta(offset)
        raw = draw(st.lists(st.integers(base, 2 * base), min_size=4, max_size=4))
        nearest = [unit.grid().nearest(Decimal(p), day) for p in raw]
        prices.append([int(n) for n in nearest if n is not None])
    return first, prices


@example(
    drawn=(date(2015, 3, 2), unit.EDGE_DAYS), factor=Decimal("1.9999201"), noise=Decimal("-0.001")
)
@given(
    true_run(),
    st.decimals(min_value=1, max_value=Decimal("1.9999999"), places=7),
    st.sampled_from([Decimal(0), Decimal("0.001"), Decimal("-0.001"), Decimal("0.0004")]),
)
def test_a_proven_factor_restores_the_true_prices(
    drawn: tuple[date, list[list[int]]], factor: Decimal, noise: Decimal
) -> None:
    unit.test_a_proven_factor_restores_the_true_prices(drawn, factor, noise)
