"""The corporate action view property at its full count (#290). It calls its unit stand-in's
check, in tests/engine/test_view.py, on every case it draws."""

from datetime import date
from decimal import Decimal

import pytest
import test_view as unit
from hypothesis import given
from hypothesis import strategies as st

from steadyhand import CashDividend, CorporateAction, Instrument, Split

_STOCKS = st.sampled_from([unit.BBCA, unit.BBRI])
_DAYS = st.dates(min_value=date(2019, 1, 1), max_value=date(2021, 12, 31))
_DIVIDEND = st.builds(CashDividend, _STOCKS, _DAYS, st.integers(1, 10_000).map(Decimal))
_SPLIT = st.builds(
    lambda stock, day, shares: Split(stock, day, *shares),
    _STOCKS,
    _DAYS,
    st.tuples(st.integers(1, 10), st.integers(1, 10)).filter(lambda pair: pair[0] != pair[1]),
)


@pytest.mark.parametrize("stock", [unit.BBCA, unit.BBRI], ids=lambda stock: stock.symbol)
@given(st.lists(st.one_of(_DIVIDEND, _SPLIT), max_size=12), _DAYS)
def test_nothing_after_today_is_returned_and_each_dividend_is_restated_by_its_own_splits(
    stock: Instrument, actions: list[CorporateAction], today: date
) -> None:
    unit.check_nothing_after_today_is_returned_and_each_dividend_is_restated_by_its_own_splits(
        stock, actions, today
    )
