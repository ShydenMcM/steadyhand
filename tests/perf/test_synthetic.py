"""``synthetic``'s market and strategy on the paths the performance runs never take (#374): a day
before the plain market opens, its dividend and protection rules, and a day with nothing to buy.
Unit tests: the performance tests themselves are marked ``perf``, these are not."""

from datetime import date

import pytest
from synthetic import EqualWeight, PlainRules

from steadyhand import IDR, Instrument, Money, PortfolioView, UnsupportedDateError
from steadyhand.market import PayDates
from steadyhand.view import ActionHistory, MarketView, PriceHistory, Tradable

OPENING = date(2000, 1, 3)
MONDAY = date(2020, 1, 6)


def test_the_plain_market_refuses_the_day_before_it_opens() -> None:
    with pytest.raises(UnsupportedDateError, match=r"^the plain market opens on 2000-01-03$"):
        PlainRules().require_supported(date(2000, 1, 2))


def test_the_plain_market_accepts_its_opening_day() -> None:
    PlainRules().require_supported(OPENING)


def test_the_plain_market_sets_no_reinvestment_deadline() -> None:
    assert PlainRules().reinvestment_deadline(MONDAY) is None


def test_a_plain_purchase_is_protected_until_its_own_day_only() -> None:
    assert PlainRules().protection_end(MONDAY) == MONDAY


def test_equal_weight_buys_nothing_when_nothing_is_buyable() -> None:
    held = Instrument("S000", "PLAIN", IDR)
    tradable = Tradable(MONDAY, frozenset(), frozenset({held}), {}, frozenset({held}))
    view = MarketView(
        PriceHistory([]), MONDAY, tradable, ActionHistory(), PayDates(PlainRules(), 2)
    )
    portfolio = PortfolioView(Money(1_000_000, IDR), Money(0, IDR), {held: Money(1_000_000, IDR)})
    assert EqualWeight().decide(view, portfolio, {}).weights == {}
