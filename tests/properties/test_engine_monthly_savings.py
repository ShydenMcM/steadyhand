"""The monthly savings property at its full count (#290). It calls its unit stand-in's check, in
tests/engine/test_monthly_savings.py, on every case it draws."""

import test_monthly_savings as unit
from hypothesis import given
from hypothesis import strategies as st


@given(
    instalments=st.integers(1, 24),
    start=st.integers(1_000, 10**10),
    months=st.lists(
        st.tuples(st.integers(0, 10**8), st.integers(0, 4), st.integers(1, 3)),
        min_size=1,
        max_size=30,
    ),
)
def test_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month(
    instalments: int, start: int, months: list[tuple[int, int, int]]
) -> None:
    unit.check_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month(
        instalments, start, months
    )
