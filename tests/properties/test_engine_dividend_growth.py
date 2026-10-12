"""The dividend growth review property at its full count (#290). It calls its unit stand-in, in
tests/engine/test_dividend_growth.py, on every case it draws."""

from datetime import date

import test_dividend_growth as unit
from hypothesis import given
from hypothesis import strategies as st


@given(
    st.lists(
        st.dates(min_value=date(2025, 1, 1), max_value=date(2027, 12, 31)),
        min_size=1,
        max_size=12,
        unique=True,
    ).map(sorted)
)
def test_it_reviews_on_no_day_but_the_first_and_each_new_years_first(days: list[date]) -> None:
    unit.test_it_reviews_on_no_day_but_the_first_and_each_new_years_first(days)
