"""IdxMarketRules: the IDX tables behind the engine's MarketRules protocol."""

import copy
import math
from dataclasses import replace
from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand import (
    IDR,
    Currency,
    Instrument,
    MarketRules,
    Money,
    Side,
    UnsupportedDateError,
)
from steadyhand_idx._datafile import load_shipped
from steadyhand_idx.fees import parse_fees
from steadyhand_idx.rules import IdxMarketRules, RuleTables


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


BBCA = Instrument("BBCA", "IDX", IDR)
TODAY = date(2026, 9, 25)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def test_it_is_the_engines_market_rules() -> None:
    market: MarketRules = rules()
    assert isinstance(market, MarketRules)
    assert market.currency == IDR


def test_the_verified_date_is_2021_set_by_stamp_duty() -> None:
    assert rules().verified_from == date(2021, 1, 1)
    rules().require_supported(date(2021, 1, 1))
    with pytest.raises(
        UnsupportedDateError,
        match=(
            r"^steadyhand's IDX rules are primary-verified from 2021-01-01, the first date of "
            r"fees\.toml \[stamp_duty\]; 2020-12-31 is earlier$"
        ),
    ):
        rules().require_supported(date(2020, 12, 31))


def test_the_verified_date_is_derived_from_the_files() -> None:
    document = copy.deepcopy(load_shipped("fees.toml"))
    stamp_duty = document["stamp_duty"]
    assert isinstance(stamp_duty, list)
    stamp_duty[0]["from"] = date(2019, 1, 1)
    tables = replace(RuleTables.shipped(), fees=parse_fees(document))
    rules = IdxMarketRules(tables)
    # The next-latest first date is 13 Mar 2020, shared by three tables; the first listed names it.
    assert rules.verified_from == date(2020, 3, 13)
    with pytest.raises(UnsupportedDateError, match=r"first date of tick_sizes\.toml \[ticks\];"):
        rules.require_supported(date(2020, 3, 12))


def test_a_year_past_the_holiday_data_is_refused() -> None:
    with pytest.raises(UnsupportedDateError, match=r"^holidays\.toml has no IDX holidays for 2028"):
        rules().require_supported(date(2028, 1, 3))


@pytest.mark.parametrize(
    "call",
    [
        lambda: rules().lot_size(BBCA, date(2020, 12, 31)),
        lambda: rules().round_to_tick(BBCA, rp(201), Side.BUY, date(2020, 12, 31)),
        lambda: rules().price_band(BBCA, rp(1000), date(2020, 12, 31)),
        lambda: rules().costs(Side.BUY, rp(1000), date(2020, 12, 31)),
        lambda: rules().daily_costs(rp(1000), date(2020, 12, 31)),
        lambda: rules().settlement_date(date(2020, 12, 30)),
        lambda: rules().dividend_tax(rp(1000), reinvested_by_deadline=False, on=date(2020, 12, 31)),
        lambda: rules().is_trading_day(date(2020, 12, 31)),
    ],
)
def test_every_rule_refuses_an_unverified_day(call: object) -> None:
    assert callable(call)
    with pytest.raises(UnsupportedDateError, match="primary-verified from 2021-01-01"):
        call()


def test_other_markets_and_currencies_are_refused() -> None:
    usd = Currency("USD", 2)
    with pytest.raises(
        ValueError, match=r"^AAPL is a NASDAQ USD instrument; these rules are for IDX"
    ):
        rules().lot_size(Instrument("AAPL", "NASDAQ", usd), TODAY)
    with pytest.raises(ValueError, match=r"^price must be in IDR, got USD 2\.01$"):
        rules().round_to_tick(BBCA, Money(201, usd), Side.BUY, TODAY)
    with pytest.raises(ValueError, match=r"^gross must be in IDR"):
        rules().dividend_tax(Money(1, usd), reinvested_by_deadline=False, on=TODAY)


def test_lots_and_ticks() -> None:
    assert rules().lot_size(BBCA, TODAY) == 100
    assert rules().round_to_tick(BBCA, rp(5_001), Side.BUY, TODAY) == rp(5_025)
    assert rules().round_to_tick(BBCA, rp(5_001), Side.SELL, TODAY) == rp(5_000)


@pytest.mark.parametrize(
    ("on", "reference", "low", "high", "why"),
    [
        (TODAY, 1_000, 850, 1_250, "25% up and 15% down, both on the Rp5 grid"),
        (TODAY, 200, 170, 270, "200 is in the 35% tier for bands"),
        (TODAY, 5_000, 4_250, 6_250, "5,000 is in the 25% tier for bands"),
        (
            TODAY,
            5_025,
            4_280,
            6_025,
            "6,030 is off the Rp25 grid; 4,271.25 rounds up to Rp10's 4,280",
        ),
        (TODAY, 50, 50, 67, "the bottom (42.5) is raised to the Rp50 minimum"),
        (date(2026, 9, 28), 7, 6, 8, "the Rp1-10 tier moves Rp1 either way"),
        (date(2026, 9, 28), 1, 1, 2, "never below the Rp1 minimum"),
        (date(2027, 1, 1), 1_000, 750, 1_250, "symmetric 25% from 2027"),
    ],
)
def test_band_edges_come_from_the_band_and_the_tick_grid_together(
    on: date, reference: int, low: int, high: int, why: str
) -> None:
    assert rules().price_band(BBCA, rp(reference), on) == (rp(low), rp(high)), why


def test_a_reference_below_the_minimum_price_is_refused() -> None:
    with pytest.raises(ValueError, match=r"^reference IDR 40 is below the minimum price, Rp50$"):
        rules().price_band(BBCA, rp(40), TODAY)


@given(
    reference=st.integers(min_value=50, max_value=1_000_000),
    on=st.sampled_from([date(2021, 1, 4), date(2023, 6, 5), date(2023, 9, 4), TODAY]),
)
def test_band_edges_are_the_widest_valid_prices_inside_the_band(reference: int, on: date) -> None:
    low, high = rules().price_band(BBCA, rp(reference), on)
    tables = RuleTables.shipped()
    ticks, band = tables.ticks.on(on), tables.bands.on(on)
    bottom, top = band.limits(reference)
    assert ticks.is_valid(low.amount)
    assert ticks.is_valid(high.amount)
    assert low.amount >= max(bottom, Decimal(band.min_price))
    assert high.amount <= top
    assert not any(ticks.is_valid(p) for p in range(high.amount + 1, math.floor(top) + 1))
    floor_price = max(math.ceil(bottom), band.min_price)
    assert not any(ticks.is_valid(p) for p in range(floor_price, low.amount))


def test_costs_use_the_chosen_broker_preset() -> None:
    ajaib = IdxMarketRules(broker_fees="ajaib")
    assert ajaib.costs(Side.BUY, rp(10_000_000), TODAY).total == rp(15_130)
    assert rules().costs(Side.BUY, rp(10_000_000), TODAY).total == rp(20_980)
    with pytest.raises(ValueError, match="no broker fee preset named 'ipot'"):
        IdxMarketRules(broker_fees="ipot")


def test_daily_costs_are_the_stamp_duty() -> None:
    assert rules().daily_costs(rp(1), date(2021, 1, 4)) == rp(10_000)
    assert rules().daily_costs(rp(10_000_000), date(2022, 1, 12)) == rp(0)


@pytest.mark.parametrize(
    ("trade", "settles"),
    [
        (date(2026, 9, 24), date(2026, 9, 28)),  # Thursday: across the weekend
        (date(2026, 3, 17), date(2026, 3, 26)),  # across Eid al-Fitr's five holidays
        (date(2026, 12, 29), date(2027, 1, 4)),  # across the year-end holidays
        (date(2021, 1, 4), date(2021, 1, 6)),  # the first verified trading day
    ],
)
def test_settlement_is_two_trading_days_later(trade: date, settles: date) -> None:
    assert rules().settlement_date(trade) == settles


def test_nothing_settles_from_a_non_trading_day() -> None:
    with pytest.raises(ValueError, match=r"^2026-09-26 is not an IDX trading day"):
        rules().settlement_date(date(2026, 9, 26))


def test_dividend_tax_and_trading_days() -> None:
    assert rules().dividend_tax(rp(1_000), reinvested_by_deadline=False, on=TODAY) == rp(100)
    assert rules().is_trading_day(date(2021, 1, 4))
    assert not rules().is_trading_day(date(2026, 12, 31))
