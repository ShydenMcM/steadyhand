"""The exemption claim property at its full count (#290). It calls its unit stand-in, in
tests/engine/test_exemption.py, on every case it draws."""

import test_exemption as unit
from hypothesis import given
from hypothesis import strategies as st


@given(
    gross=st.integers(1, 100_000),
    steps=st.lists(
        st.tuples(st.integers(0, 100), st.integers(0, 150)), min_size=1, max_size=len(unit.TRADING)
    ),
    last_day=st.integers(0, len(unit.TRADING) - 1),
)
def test_a_claims_tax_never_exceeds_its_full_tax_plus_one_unit_per_extra_booking(
    gross: int, steps: list[tuple[int, int]], last_day: int
) -> None:
    unit.test_a_claims_tax_never_exceeds_its_full_tax_plus_one_unit_per_extra_booking(
        gross, steps, last_day
    )
