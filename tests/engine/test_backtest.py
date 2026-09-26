"""backtest: the pre-flight checks, the fetch, refused days, halts and the baseline (M3 spec §7)."""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from steadyhand.backtest import (
    BacktestResult,
    BacktestSettings,
    Market,
    NoTradingDaysError,
    UniverseCoverageError,
    backtest,
)
from steadyhand.data import DataUnavailableError, UnavailableDaysError
from steadyhand.engine import DataValidationError, EngineSettings
from steadyhand.market import UnsupportedDateError
from steadyhand.money import IDR, Currency, Money
from steadyhand.risk import RiskLimits
from steadyhand.strategies import BuyAndHold, Decision, Memory, Strategy
from steadyhand.types import Bar, CashDividend, CorporateAction, Instrument
from steadyhand.view import MarketView, PortfolioView
from steadyhand_idx import IdxMarketRules

BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
# The trading days from Monday 30 June to Friday 11 July 2025, by the shipped IDX calendar.
DAYS = (
    date(2025, 6, 30),
    date(2025, 7, 1),
    date(2025, 7, 2),
    date(2025, 7, 3),
    date(2025, 7, 4),
    date(2025, 7, 7),
    date(2025, 7, 8),
    date(2025, 7, 9),
    date(2025, 7, 10),
    date(2025, 7, 11),
)
START, END = DAYS[0], DAYS[-1]


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def settings(contribution: int | None = None) -> BacktestSettings:
    """Half the portfolio per stock, so two stocks can be fully invested."""
    limits = RiskLimits(max_weight=Decimal("0.5"))
    top_up = None if contribution is None else rp(contribution)
    return BacktestSettings(
        rp(100_000_000), EngineSettings(limits=limits, monthly_contribution=top_up)
    )


def bar(stock: Instrument, day: date, close: int, open_: int | None = None) -> Bar:
    start = close if open_ is None else open_
    high, low = rp(max(start, close)), rp(min(start, close))
    return Bar(stock, day, rp(start), high, low, rp(close), 10**7)


def flat(stock: Instrument, close: int, days: Sequence[date] = DAYS) -> list[Bar]:
    return [bar(stock, day, close) for day in days]


class _Source:
    """An in-memory data source that records every request and can refuse days, as Yahoo does."""

    def __init__(
        self,
        bars: Sequence[Bar],
        actions: Sequence[CorporateAction] = (),
        refused: Mapping[Instrument, Sequence[date]] | None = None,
        broken: frozenset[Instrument] = frozenset(),
    ) -> None:
        self._bars = bars
        self._actions = actions
        self._refused = {} if refused is None else refused
        self._broken = broken
        self.requests: list[tuple[str, str, date, date]] = []

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        self._check("bars", instrument, start, end)
        return [b for b in self._bars if b.instrument == instrument and start <= b.day <= end]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        self._check("actions", instrument, start, end)
        return [
            a for a in self._actions if a.instrument == instrument and start <= a.ex_date <= end
        ]

    def _check(self, kind: str, instrument: Instrument, start: date, end: date) -> None:
        self.requests.append((kind, instrument.symbol, start, end))
        if instrument in self._broken:
            msg = f"{instrument.symbol}: no data"
            raise DataUnavailableError(msg)
        days = [day for day in self._refused.get(instrument, ()) if start <= day <= end]
        if days:
            msg = f"{instrument.symbol}: refused"
            raise UnavailableDaysError(msg, days)


class _Universe:
    """Members from each listed date on, with exclusions and gap warnings to pass through."""

    def __init__(
        self,
        lists: Sequence[tuple[date, frozenset[Instrument]]],
        excluded: Mapping[Instrument, str] | None = None,
        warnings: Sequence[str] = (),
    ) -> None:
        self._lists = lists
        self._excluded = {} if excluded is None else excluded
        self._warnings = tuple(warnings)
        self.asked: list[tuple[date, date]] = []

    def members_on(self, day: date) -> frozenset[Instrument]:
        found = [members for start, members in self._lists if start <= day]
        if not found:
            msg = f"no members on {day.isoformat()}"
            raise LookupError(msg)
        return found[-1]

    def excluded_on(self, day: date) -> Mapping[Instrument, str]:
        return self._excluded

    def first_day(self) -> date:
        return self._lists[0][0]

    def survivorship_warnings(self, start: date, end: date) -> Sequence[str]:
        self.asked.append((start, end))
        return self._warnings


class _Fixed:
    """A strategy that always asks for the same weights."""

    def __init__(self, weights: Mapping[Instrument, Decimal]) -> None:
        self._weights = weights

    @property
    def name(self) -> str:
        return "fixed"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        return Decision(self._weights)


def pair() -> _Universe:
    return _Universe([(START, frozenset({BBCA, BBRI}))])


def calm() -> list[Bar]:
    return flat(BBCA, 9_000) + flat(BBRI, 4_000)


def market(source: _Source, universe: _Universe | None = None) -> Market:
    return Market(pair() if universe is None else universe, source, rules())


def run(
    source: _Source,
    universe: _Universe | None = None,
    strategy: Strategy | None = None,
    chosen: BacktestSettings | None = None,
) -> BacktestResult:
    return backtest(
        _Fixed({BBCA: Decimal("0.5")}) if strategy is None else strategy,
        market(source, universe),
        START,
        END,
        settings() if chosen is None else chosen,
    )


def test_the_strategy_and_the_baseline_each_run_every_trading_day() -> None:
    result = run(_Source(calm()))
    assert (result.start, result.end) == (START, END)
    assert result.run.strategy == "fixed"
    assert result.baseline is not None
    assert result.baseline.strategy == "buy-and-hold"
    assert [report.day for report in result.run.reports] == list(DAYS)
    assert [report.day for report in result.baseline.reports] == list(DAYS)
    assert result.run.final.last_day == END
    assert result.baseline.final.last_day == END
    assert {order.instrument for order in result.run.reports[0].queued} == {BBCA}
    assert {order.instrument for order in result.baseline.reports[0].queued} == {BBCA, BBRI}


def test_both_runs_share_the_settings() -> None:
    result = run(_Source(calm()), chosen=settings(contribution=5_000_000))
    assert result.baseline is not None
    for outcome in (result.run, result.baseline):
        deposits = {report.day: report.deposit for report in outcome.reports}
        assert deposits[date(2025, 7, 1)] == rp(5_000_000)
        assert sum(amount.amount for amount in deposits.values()) == 5_000_000
        # At the default 10% cap these day-one buys would be cut; at 50% they are not.
        assert outcome.reports[0].cuts == ()


def test_a_buy_and_hold_backtest_is_its_own_baseline() -> None:
    result = run(_Source(calm()), strategy=BuyAndHold())
    assert result.run.strategy == "buy-and-hold"
    assert result.baseline is None


def test_a_start_the_rules_do_not_cover_is_refused_before_anything_is_fetched() -> None:
    source = _Source(calm())
    with pytest.raises(UnsupportedDateError, match=r"; 2020-12-30 is earlier$"):
        backtest(BuyAndHold(), market(source), date(2020, 12, 30), END, settings())
    assert source.requests == []


def test_a_start_before_the_universe_is_refused_naming_its_first_day() -> None:
    source = _Source(calm())
    late = _Universe([(date(2025, 7, 1), frozenset({BBCA}))])
    with pytest.raises(
        UniverseCoverageError,
        match=(
            r"^the backtest starts on 2025-06-30, but the universe's membership is only known "
            r"from 2025-07-01; start on 2025-07-01 or later$"
        ),
    ):
        run(source, late)
    assert source.requests == []


def test_an_end_the_calendar_does_not_cover_is_refused() -> None:
    with pytest.raises(
        UnsupportedDateError,
        match=r"^holidays\.toml has no IDX holidays for \d{4}, so its trading days are unknown",
    ):
        backtest(BuyAndHold(), market(_Source([])), START, date(2099, 1, 5), settings())


@pytest.mark.parametrize(
    ("start", "end", "error", "message"),
    [
        (
            END,
            START,
            ValueError,
            r"^the backtest ends on 2025-06-30, before it starts on 2025-07-11$",
        ),
        (
            date(2025, 7, 5),
            date(2025, 7, 6),
            NoTradingDaysError,
            r"^there is no trading day from 2025-07-05 to 2025-07-06$",
        ),
    ],
)
def test_a_range_must_run_forwards_and_hold_a_trading_day(
    start: date, end: date, error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        backtest(BuyAndHold(), market(_Source(calm())), start, end, settings())


def test_a_market_checks_its_parts() -> None:
    with pytest.raises(TypeError, match=r"^universe must be a Universe, got NoneType$"):
        Market(None, _Source([]), rules())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^source must be a DataSource, got NoneType$"):
        Market(pair(), None, rules())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^rules must be a MarketRules, got NoneType$"):
        Market(pair(), _Source([]), None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^market must be a Market, got NoneType$"):
        backtest(BuyAndHold(), None, START, END, settings())  # type: ignore[arg-type]


def test_the_capital_is_positive_and_in_the_markets_currency() -> None:
    with pytest.raises(ValueError, match=r"^the starting capital must be positive, got IDR 0$"):
        BacktestSettings(rp(0))
    with pytest.raises(TypeError, match=r"^capital must be a Money, got int$"):
        BacktestSettings(100)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^engine must be an EngineSettings, got NoneType$"):
        BacktestSettings(rp(1), None)  # type: ignore[arg-type]
    dollars = BacktestSettings(Money(100_000, Currency("USD", 2)))
    with pytest.raises(ValueError, match=r"^the capital is in USD, but the market trades in IDR$"):
        backtest(BuyAndHold(), market(_Source(calm())), START, END, dollars)
    with pytest.raises(TypeError, match=r"^settings must be a BacktestSettings, got NoneType$"):
        backtest(BuyAndHold(), market(_Source(calm())), START, END, None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^start must be a date, got str$"):
        backtest(BuyAndHold(), market(_Source(calm())), "2025-06-30", END, settings())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^end must be a date, got str$"):
        backtest(BuyAndHold(), market(_Source(calm())), START, "2025-07-11", settings())  # type: ignore[arg-type]


def test_every_stock_the_universe_holds_on_any_day_is_fetched_for_the_whole_window() -> None:
    joins = date(2025, 7, 7)
    universe = _Universe([(START, frozenset({BBCA})), (joins, frozenset({BBCA, TLKM}))])
    source = _Source(flat(BBCA, 9_000) + flat(TLKM, 3_000))
    result = run(source, universe, strategy=_Fixed({TLKM: Decimal("0.5")}))
    assert source.requests == [
        ("bars", "BBCA", START, END),
        ("actions", "BBCA", START, END),
        ("bars", "TLKM", START, END),
        ("actions", "TLKM", START, END),
    ]
    queued = [{order.instrument for order in report.queued} for report in result.run.reports]
    assert queued[5:] == [{TLKM}, set(), set(), set(), set()]
    assert all(not found for found in queued[:5])
    assert [rejected.reason for rejected in result.run.reports[0].rejected] == [
        "not in the universe on 2025-06-30"
    ]


def test_refused_days_are_fetched_around_and_the_stock_sits_them_out() -> None:
    refused = (date(2025, 7, 3), date(2025, 7, 4), date(2025, 7, 7), date(2025, 7, 10))
    clean = [day for day in DAYS if day not in refused]
    # BBRI reopens on 8 July at 5,200, outside the band around its last clean close of 4,000:
    # after refused days that close says nothing, so the band check must skip it.
    bbri = [bar(BBRI, day, 4_000) for day in clean if day < date(2025, 7, 8)] + [
        bar(BBRI, day, 5_200) for day in clean if day >= date(2025, 7, 8)
    ]
    source = _Source(flat(BBCA, 9_000) + bbri, refused={BBRI: refused})
    universe = _Universe([(START, frozenset({BBCA, BBRI}))], warnings=["a gap"])
    result = run(source, universe, strategy=BuyAndHold())
    assert source.requests == [
        ("bars", "BBCA", START, END),
        ("actions", "BBCA", START, END),
        ("bars", "BBRI", START, END),
        ("bars", "BBRI", START, date(2025, 7, 2)),
        ("actions", "BBRI", START, date(2025, 7, 2)),
        ("bars", "BBRI", date(2025, 7, 8), date(2025, 7, 9)),
        ("actions", "BBRI", date(2025, 7, 8), date(2025, 7, 9)),
        ("bars", "BBRI", END, END),
        ("actions", "BBRI", END, END),
    ]
    assert universe.asked == [(START, END)]
    assert result.warnings == (
        "a gap",
        (
            "BBRI: the data source refused 4 day(s) (2025-07-03 to 2025-07-07, 2025-07-10), so it "
            "was not traded on them, and a holding was valued at its last clean close. A dividend "
            "whose ex-date falls on a refused day is unknown and was not credited."
        ),
    )
    reports = {report.day: report for report in result.run.reports}
    held = {p.instrument: p.quantity for p in result.run.final.holdings.portfolio.positions}
    for day in refused:
        assert all(order.instrument != BBRI for order in reports[day].queued)
        assert all(fill.order.instrument != BBRI for fill in reports[day].fills)
    bbca = next(
        fill.quantity for fill in reports[date(2025, 7, 1)].fills if fill.order.instrument == BBCA
    )
    bbri_held = next(
        fill.quantity for fill in reports[date(2025, 7, 1)].fills if fill.order.instrument == BBRI
    )
    assert reports[date(2025, 7, 3)].holdings_value == rp(9_000 * bbca + 4_000 * bbri_held)
    assert reports[date(2025, 7, 8)].holdings_value == rp(9_000 * bbca + 5_200 * bbri_held)
    assert held[BBRI] == bbri_held


class _OutOfWindow(_Source):
    """A source whose first answer for BBRI refuses a day after the window, contradicting the
    request, and which answers normally after that. Retrying would hide the contradiction."""

    def __init__(self, bars: Sequence[Bar]) -> None:
        super().__init__(bars)
        self._refused_once = False

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        if instrument == BBRI and not self._refused_once:
            self._refused_once = True
            msg = "BBRI: refused"
            raise UnavailableDaysError(msg, [date(2025, 8, 1)])
        return super().bars(instrument, start, end)


def test_a_refusal_naming_no_day_in_the_window_stops_the_run() -> None:
    with pytest.raises(UnavailableDaysError, match=r"^BBRI: refused$"):
        run(_OutOfWindow(calm()))


def test_refusals_on_the_first_and_last_days_leave_one_range_between() -> None:
    source = _Source(calm(), refused={BBRI: (START, END)})
    result = run(source, strategy=BuyAndHold())
    assert [r for r in source.requests if r[1] == "BBRI"] == [
        ("bars", "BBRI", START, END),
        ("bars", "BBRI", DAYS[1], DAYS[-2]),
        ("actions", "BBRI", DAYS[1], DAYS[-2]),
    ]
    assert result.warnings[0].startswith(
        "BBRI: the data source refused 2 day(s) (2025-06-30, 2025-07-11),"
    )
    # Refused on day one, BBRI is not buyable then, so buy-and-hold never adds it to its set.
    assert result.run.final.memory == {"set": "IDX:BBCA"}


def test_any_other_unavailable_data_stops_the_run() -> None:
    with pytest.raises(DataUnavailableError, match=r"^BBRI: no data$"):
        run(_Source(calm(), broken=frozenset({BBRI})))


def test_a_close_outside_the_band_stops_the_backtest() -> None:
    jumped = flat(BBCA, 9_000, DAYS[:3]) + flat(BBCA, 12_000, DAYS[3:]) + flat(BBRI, 4_000)
    with pytest.raises(
        DataValidationError,
        match=r"^BBCA on 2025-07-03: the close IDR 12,000 is outside the band IDR 7,650 to",
    ):
        run(_Source(jumped))


def test_a_halt_lasts_to_the_end_of_the_run_and_is_recorded() -> None:
    # Fully invested half and half; BBCA's 15% fall on 7 July takes the portfolio past 5%.
    fall = flat(BBCA, 9_000, DAYS[:5]) + flat(BBCA, 7_650, DAYS[5:]) + flat(BBRI, 4_000)
    result = run(_Source(fall), strategy=BuyAndHold())
    assert result.run.halt is not None
    assert result.run.halt.day == date(2025, 7, 7)
    assert result.run.halt.cause == (
        "daily loss limit: the unit value fell 7.46%, the limit is 5.00%"
    )
    reports = {report.day: report for report in result.run.reports}
    assert reports[date(2025, 7, 7)].halt == result.run.halt
    assert all(report.queued == () for day, report in reports.items() if day >= date(2025, 7, 7))
    assert all(report.halt is None for day, report in reports.items() if day != date(2025, 7, 7))


def test_exclusions_and_corporate_actions_reach_their_days() -> None:
    universe = _Universe([(START, frozenset({BBCA, BBRI, TLKM}))], {TLKM: "Special Monitoring"})
    dividend = CashDividend(BBCA, date(2025, 7, 8), Decimal(50))
    source = _Source(calm() + flat(TLKM, 3_000), [dividend])
    result = run(source, universe, strategy=BuyAndHold())
    assert {order.instrument for order in result.run.reports[0].queued} == {BBCA, BBRI}
    entitled = {report.day: report.entitled for report in result.run.reports}
    held = next(
        fill.quantity for fill in result.run.reports[1].fills if fill.order.instrument == BBCA
    )
    assert [(e.instrument, e.gross) for e in entitled[date(2025, 7, 8)]] == [(BBCA, rp(50 * held))]
    assert all(not found for day, found in entitled.items() if day != date(2025, 7, 8))


def test_a_run_gathers_every_days_warnings_in_order() -> None:
    gap = date(2025, 7, 8)
    source = _Source(flat(BBCA, 9_000) + [b for b in flat(BBRI, 4_000) if b.day != gap])
    result = run(source, strategy=BuyAndHold())
    assert result.run.warnings == (
        (
            "BBRI has no bar on 2025-07-08, so it is not traded; it is valued at its last close, "
            "IDR 4,000"
        ),
    )
    assert result.warnings == ()
