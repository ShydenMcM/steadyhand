"""backtest: the pre-flight checks, the fetch, refused days, halts, the baseline (M3 spec §7), and
the income reports and income impact when a goal is set (M4 spec §8)."""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from steadyhand.backtest import (
    BacktestResult,
    BacktestSettings,
    IncomeImpact,
    Market,
    NoTradingDaysError,
    UniverseCoverageError,
    backtest,
    compare,
    day_inputs,
)
from steadyhand.corporate import Entitlement
from steadyhand.data import DataUnavailableError, UnavailableDaysError
from steadyhand.engine import DataValidationError, EngineSettings
from steadyhand.income import IncomeGoal
from steadyhand.market import UnsupportedDateError
from steadyhand.metrics import measure
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import (
    DATA_BAR_MISSING,
    DATA_BAR_REFUSED,
    DATA_DIVIDENDS_HISTORY_REFUSED,
    FILL_NO_BAR,
    RISK_HALT_DAILY_LOSS,
    TRADE_NOT_IN_UNIVERSE,
    TRADE_REFUSED,
    Note,
)
from steadyhand.risk import RiskLimits
from steadyhand.strategies import BuyAndHold, Decision, Memory, Strategy
from steadyhand.types import Bar, CashDividend, CorporateAction, Instrument
from steadyhand.view import MarketView, PastDividend, PortfolioView
from steadyhand_idx import UNIVERSE_SURVIVORSHIP_GAP, IdxMarketRules
from steadyhand_idx.notes import DATA_PRICES_RESTORED

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
GAP = Note(UNIVERSE_SURVIVORSHIP_GAP, "a gap")
RESTORED = Note(DATA_PRICES_RESTORED, "restored")


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
        notes: Sequence[Note] = (),
    ) -> None:
        self._bars = bars
        self._actions = actions
        self._refused = {} if refused is None else refused
        self._broken = broken
        self._notes = notes
        self.requests: list[tuple[str, str, date, date]] = []
        self.noted: list[tuple[tuple[str, ...], date, date]] = []

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

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> Sequence[Note]:
        self.noted.append((tuple(i.symbol for i in instruments), start, end))
        return self._notes

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
        warnings: Sequence[Note] = (),
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

    def survivorship_warnings(self, start: date, end: date) -> Sequence[Note]:
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


@pytest.fixture(scope="module")
def contributed() -> BacktestResult:
    """A run and its baseline, with a monthly contribution."""
    return run(_Source(calm()), chosen=settings(contribution=5_000_000))


@pytest.mark.parametrize("which", ["run", "baseline"])
def test_each_run_carries_its_metrics(contributed: BacktestResult, which: str) -> None:
    outcome = getattr(contributed, which)
    assert outcome is not None
    assert outcome.metrics == measure(outcome.reports, outcome.final)
    assert outcome.metrics.deposited == rp(105_000_000)
    assert outcome.metrics.final_value == outcome.reports[-1].value


def test_the_run_and_its_baseline_measure_differently(contributed: BacktestResult) -> None:
    assert contributed.baseline is not None
    assert contributed.run.metrics != contributed.baseline.metrics


@pytest.mark.parametrize("which", ["run", "baseline"])
def test_both_runs_share_the_settings(contributed: BacktestResult, which: str) -> None:
    outcome = getattr(contributed, which)
    assert outcome is not None
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
    assert all(  # runtime population: the orders queued on the days before TLKM joined
        not found for found in queued[:5]
    )
    assert [rejected.reason for rejected in result.run.reports[0].rejected] == [
        Note(TRADE_NOT_IN_UNIVERSE, "not in the universe on 2025-06-30")
    ]


REFUSED = (date(2025, 7, 3), date(2025, 7, 4), date(2025, 7, 7), date(2025, 7, 10))


def refused_market() -> tuple[_Source, _Universe]:
    """BBCA and BBRI, with the source refusing BBRI on the four ``REFUSED`` days."""
    clean = [day for day in DAYS if day not in REFUSED]
    # BBRI reopens on 8 July at 5,200, outside the band around its last clean close of 4,000:
    # after refused days that close says nothing, so the band check must skip it.
    bbri = [bar(BBRI, day, 4_000) for day in clean if day < date(2025, 7, 8)] + [
        bar(BBRI, day, 5_200) for day in clean if day >= date(2025, 7, 8)
    ]
    source = _Source(flat(BBCA, 9_000) + bbri, refused={BBRI: REFUSED})
    return source, _Universe([(START, frozenset({BBCA, BBRI}))], warnings=[GAP])


@pytest.fixture(scope="module")
def refused_run() -> tuple[_Source, _Universe, BacktestResult]:
    """A buy-and-hold run in which the source refuses BBRI on the four ``REFUSED`` days."""
    source, universe = refused_market()
    return source, universe, run(source, universe, strategy=BuyAndHold())


@pytest.mark.parametrize("day", REFUSED, ids=str)
def test_a_refused_stock_is_valued_at_its_last_clean_close(
    refused_run: tuple[_Source, _Universe, BacktestResult], day: date
) -> None:
    _, _, result = refused_run
    reports = {report.day: report for report in result.run.reports}
    held = {fill.order.instrument: fill.quantity for fill in reports[date(2025, 7, 1)].fills}
    # Valued at its last clean close: 4,000 before it reopens on 8 July, 5,200 after. Buy-and-hold
    # queues nothing after its first day, so this is what each refused day can be seen to get wrong.
    close = 4_000 if day < date(2025, 7, 8) else 5_200
    assert reports[day].holdings_value == rp(9_000 * held[BBCA] + close * held[BBRI])


class _Churn:
    """A strategy that asks every day for the opposite of the BBRI it holds, so that it has a
    BBRI order to make on every day, a refused one included (#184)."""

    @property
    def name(self) -> str:
        return "churn"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        bbri = Decimal("0.5") if portfolio.weight(BBRI) < Decimal("0.35") else Decimal("0.2")
        return Decision({BBCA: Decimal("0.3"), BBRI: bbri})


@pytest.fixture(scope="module")
def churned_run() -> BacktestResult:
    """The refused days of ``refused_run`` under a strategy that wants BBRI traded every day."""
    source, universe = refused_market()
    return run(source, universe, strategy=_Churn())


@pytest.mark.parametrize("day", REFUSED, ids=str)
def test_the_stock_is_never_queued_on_a_refused_day(churned_run: BacktestResult, day: date) -> None:
    report = next(report for report in churned_run.run.reports if report.day == day)
    # The strategy asks for BBRI and is told the source refused the day ...
    refused = Note(TRADE_REFUSED, f"the data source refused {day.isoformat()}")
    assert refused in [r.reason for r in report.rejected if r.order.instrument == BBRI]
    # ... so no BBRI order waits for the next open.
    assert all(  # runtime population: the orders this day's report queued
        order.instrument != BBRI for order in report.queued
    )


@pytest.mark.parametrize(
    ("day", "waiting"),
    [
        # A BBRI order queued on a clean day meets a refused open ...
        pytest.param(date(2025, 7, 3), 1, id="2025-07-03"),
        # ... while after a refused day none can be waiting, so a fill here would need an order
        # queued on a refused day as well, which the test above refuses.
        pytest.param(date(2025, 7, 4), 0, id="2025-07-04"),
        pytest.param(date(2025, 7, 7), 0, id="2025-07-07"),
        pytest.param(date(2025, 7, 10), 1, id="2025-07-10"),
    ],
)
def test_the_stock_never_fills_on_a_refused_day(
    churned_run: BacktestResult, day: date, waiting: int
) -> None:
    reports = churned_run.run.reports
    index = next(i for i, report in enumerate(reports) if report.day == day)
    orders = [order for order in reports[index - 1].queued if order.instrument == BBRI]
    assert len(orders) == waiting
    # Each BBRI order waiting for this open reaches the broker and is turned away for want of a
    # bar ...
    report = reports[index]
    assert [r.order for r in report.rejected if r.reason.key == FILL_NO_BAR] == orders
    # ... and none of them fills.
    assert all(  # runtime population: the fills this day's report holds
        fill.order.instrument != BBRI for fill in report.fills
    )


def test_refused_days_are_fetched_around_and_the_stock_sits_them_out(
    refused_run: tuple[_Source, _Universe, BacktestResult],
) -> None:
    source, universe, result = refused_run
    assert source.requests == [
        ("bars", "BBCA", START, END),
        ("actions", "BBCA", START, END),
        ("bars", "BBRI", START, END),
        # Its actions over the whole run, for its history: this source refuses those too.
        ("actions", "BBRI", START, END),
        ("bars", "BBRI", START, date(2025, 7, 2)),
        ("actions", "BBRI", START, date(2025, 7, 2)),
        ("bars", "BBRI", date(2025, 7, 8), date(2025, 7, 9)),
        ("actions", "BBRI", date(2025, 7, 8), date(2025, 7, 9)),
        ("bars", "BBRI", END, END),
        ("actions", "BBRI", END, END),
    ]
    assert universe.asked == [(START, END)]
    assert result.warnings == (
        GAP,
        Note(
            DATA_BAR_REFUSED,
            "BBRI: the data source refused 4 day(s) (2025-07-03 to 2025-07-07, 2025-07-10), so it "
            "was not traded on them, and a holding was valued at its last clean close. A dividend "
            "whose ex-date falls on a refused day is unknown and was not credited.",
        ),
    )
    reports = {report.day: report for report in result.run.reports}
    held = {p.instrument: p.quantity for p in result.run.final.holdings.portfolio.positions}
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
        ("actions", "BBRI", START, END),
        ("bars", "BBRI", DAYS[1], DAYS[-2]),
        ("actions", "BBRI", DAYS[1], DAYS[-2]),
    ]
    assert result.warnings[0].key == DATA_BAR_REFUSED
    assert result.warnings[0].text.startswith(
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
    # Fully invested half and half by a strategy that rebalances to half and half every day, so
    # it would trade again after the fall were the halt not to stop it (#184). BBCA's 15% fall
    # on 7 July takes the portfolio past 5%.
    fall = flat(BBCA, 9_000, DAYS[:5]) + flat(BBCA, 7_650, DAYS[5:]) + flat(BBRI, 4_000)
    result = run(_Source(fall), strategy=_Fixed({BBCA: Decimal("0.5"), BBRI: Decimal("0.5")}))
    assert result.run.halt is not None
    assert result.run.halt.day == date(2025, 7, 7)
    assert result.run.halt.cause == Note(
        RISK_HALT_DAILY_LOSS, "daily loss limit: the unit value fell 7.46%, the limit is 5.00%"
    )
    reports = {report.day: report for report in result.run.reports}
    assert reports[date(2025, 7, 7)].halt == result.run.halt
    assert all(  # runtime population: the run's reports
        report.queued == () for day, report in reports.items() if day >= date(2025, 7, 7)
    )
    assert all(  # runtime population: the run's reports
        report.halt is None for day, report in reports.items() if day != date(2025, 7, 7)
    )


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
    assert all(  # runtime population: the run's reports
        not found for day, found in entitled.items() if day != date(2025, 7, 8)
    )


def test_a_run_gathers_every_days_warnings_in_order() -> None:
    gap = date(2025, 7, 8)
    source = _Source(flat(BBCA, 9_000) + [b for b in flat(BBRI, 4_000) if b.day != gap])
    result = run(source, strategy=BuyAndHold())
    assert result.run.warnings == (
        Note(
            DATA_BAR_MISSING,
            "BBRI has no bar on 2025-07-08, so it is not traded; it is valued at its last close, "
            "IDR 4,000",
        ),
    )
    assert result.warnings == ()


# Dividends from before the run, which only an income report's history fetch reaches.
EARLIER: list[CorporateAction] = [
    CashDividend(BBCA, date(2025, 4, 21), Decimal(100)),
    CashDividend(BBRI, date(2025, 3, 20), Decimal(50)),
]
# Five years before the last day, Friday 11 July 2025.
HISTORY_FROM = date(2020, 7, 11)


def with_goal(contribution: int | None = None, lag: int = 14) -> BacktestSettings:
    limits = RiskLimits(max_weight=Decimal("0.5"))
    top_up = None if contribution is None else rp(contribution)
    engine = EngineSettings(limits=limits, monthly_contribution=top_up, pay_lag_trading_days=lag)
    return BacktestSettings(rp(100_000_000), engine, IncomeGoal(rp(1_000_000)))


def monthly_take_home(gross: int) -> int:
    """A year's gross less 10% tax, rounded up, over 12 months, rounded down."""
    return (gross - -(-gross // 10)) // 12


def test_without_a_goal_there_is_no_income_report_and_no_history_fetch() -> None:
    source = _Source(calm(), EARLIER)
    result = run(source)
    assert result.baseline is not None
    assert (result.run.income, result.baseline.income, result.income_impact) == (None, None, None)
    assert [request for request in source.requests if request[2] < START] == []


def test_with_a_goal_each_run_reports_its_income_from_five_years_of_history() -> None:
    source = _Source(calm(), EARLIER)
    result = run(source, chosen=with_goal(lag=3))
    assert result.baseline is not None
    # The strategy ends holding BBCA; the baseline BBCA and BBRI. Each is asked for once a run.
    assert [request for request in source.requests if request[2] < START] == [
        ("actions", "BBCA", HISTORY_FROM, END),
        ("actions", "BBCA", HISTORY_FROM, END),
        ("actions", "BBRI", HISTORY_FROM, END),
    ]
    ours, theirs = result.run.income, result.baseline.income
    assert ours is not None
    assert theirs is not None
    assert ours.as_of == theirs.as_of == END
    held = {p.instrument: p.quantity for p in result.baseline.final.holdings.portfolio.positions}
    shares = result.run.final.holdings.portfolio.positions[0].quantity
    # Three trading days after Monday 21 April 2025 is Thursday 24 April, with the run's lag.
    assert ours.run_rate.holdings[0].dividends == (
        Entitlement(BBCA, date(2025, 4, 21), date(2025, 4, 24), rp(100 * shares)),
    )
    baseline_gross = 100 * held[BBCA] + 50 * held[BBRI]
    assert theirs.run_rate.annual_gross == rp(baseline_gross)
    # Neither run was paid a dividend, so only the run-rates differ.
    assert result.income_impact == IncomeImpact(
        rp(0), rp(monthly_take_home(100 * shares) - monthly_take_home(baseline_gross))
    )


def test_the_income_report_projects_with_the_engines_contribution() -> None:
    result = run(_Source(calm(), EARLIER), chosen=with_goal(contribution=5_000_000))
    assert result.run.income is not None
    assert result.run.income.projection.contribution == rp(5_000_000)


def test_a_buy_and_hold_backtest_with_a_goal_has_no_income_impact() -> None:
    result = run(_Source(calm(), EARLIER), strategy=BuyAndHold(), chosen=with_goal())
    assert result.baseline is None
    assert result.run.income is not None
    assert result.income_impact is None


class _NoHistory(_Source):
    """A source with the run's own days and nothing before them."""

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        if start < START:
            msg = f"{instrument.symbol}: no history before {START.isoformat()}"
            raise DataUnavailableError(msg)
        return super().corporate_actions(instrument, start, end)


def test_history_the_source_cannot_give_stops_the_backtest() -> None:
    with pytest.raises(DataUnavailableError, match=r"^BBCA: no history before 2025-06-30$"):
        run(_NoHistory(calm()), chosen=with_goal())


def test_a_goal_is_an_income_goal_in_the_capitals_currency() -> None:
    with pytest.raises(TypeError, match=r"^goal must be an IncomeGoal, got Money$"):
        BacktestSettings(rp(1), EngineSettings(), rp(1))  # type: ignore[arg-type]
    dollars = IncomeGoal(Money(100, Currency("USD", 2)))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        BacktestSettings(rp(1), EngineSettings(), dollars)


def test_compare_runs_each_strategy_in_the_order_named_then_the_baseline() -> None:
    fixed = _Fixed({BBCA: Decimal("0.5")})
    result = compare([fixed], market(_Source(calm())), START, END, settings())
    alone = run(_Source(calm()), strategy=fixed)
    assert [each.strategy for each in result.runs] == ["fixed", "buy-and-hold"]
    assert result.runs == (alone.run, alone.baseline)
    assert (result.start, result.end, result.warnings) == (START, END, alone.warnings)


def test_a_named_baseline_runs_once_where_it_was_named() -> None:
    fixed = _Fixed({BBCA: Decimal("0.5")})
    result = compare([BuyAndHold(), fixed], market(_Source(calm())), START, END, settings())
    assert [each.strategy for each in result.runs] == ["buy-and-hold", "fixed"]


def test_compare_fetches_the_window_once_for_every_strategy() -> None:
    source = _Source(calm())
    compare([_Fixed({BBCA: Decimal("0.5")})], market(source), START, END, settings())
    assert [request for request in source.requests if request[0] == "bars"] == [
        ("bars", "BBCA", START, END),
        ("bars", "BBRI", START, END),
    ]


def test_compare_gives_every_run_its_income_report_when_there_is_a_goal() -> None:
    chosen = replace(settings(), goal=IncomeGoal(rp(1_000_000)))
    fixed = _Fixed({BBCA: Decimal("0.5")})
    result = compare([fixed], market(_Source(calm())), START, END, chosen)
    assert len(result.runs) == 2  # the strategy and the baseline
    assert all(  # runtime population: the runs compare returned
        each.income is not None for each in result.runs
    )
    assert compare([fixed], market(_Source(calm())), START, END, settings()).runs[0].income is None


def test_compare_needs_each_strategy_named_once() -> None:
    fixed = _Fixed({BBCA: Decimal("0.5")})
    with pytest.raises(ValueError, match=r"^name at least one strategy to compare$"):
        compare([], market(_Source(calm())), START, END, settings())
    with pytest.raises(ValueError, match=r"^fixed is named twice; name each strategy once$"):
        compare([fixed, BuyAndHold(), fixed], market(_Source(calm())), START, END, settings())
    with pytest.raises(TypeError, match="strategy"):
        compare(["fixed"], market(_Source(calm())), START, END, settings())  # type: ignore[list-item]


def test_compare_checks_its_window_as_backtest_does() -> None:
    with pytest.raises(ValueError, match=r"^the backtest ends on 2025-06-30, before it starts on"):
        compare([BuyAndHold()], market(_Source(calm())), END, START, settings())


class _Reader:
    """A strategy that records, each day, BBCA's dividends and whether BBCA's and BBRI's
    histories are complete, and asks for the weights it is given, nothing by default."""

    def __init__(self, weights: Mapping[Instrument, Decimal] | None = None) -> None:
        self.seen: dict[date, tuple[tuple[PastDividend, ...], bool, bool]] = {}
        self._weights = {} if weights is None else dict(weights)

    @property
    def name(self) -> str:
        return "reader"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        self.seen[view.today] = (
            view.dividends(BBCA),
            view.history_complete(BBCA),
            view.history_complete(BBRI),
        )
        return Decision(dict(self._weights))


class _Delisted(_Source):
    """A source with nothing at all for BBRI before the run, as Yahoo answers for a delisted
    stock (M6 spec §11): a plain ``DataUnavailableError``, naming no day."""

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        if instrument == BBRI and end < START:
            self.requests.append(("actions", instrument.symbol, start, end))
            msg = "BBRI.JK: the request to Yahoo failed: HTTP Error 404"
            raise DataUnavailableError(msg)
        return super().corporate_actions(instrument, start, end)


LOOKED_BACK: list[CorporateAction] = [
    CashDividend(BBCA, date(2022, 12, 30), Decimal(90)),
    CashDividend(BBCA, date(2023, 3, 1), Decimal(100)),
    CashDividend(BBCA, date(2025, 7, 2), Decimal(25)),
]
# Two years back from Monday 30 June 2025: from 1 January 2023 to the day before the first day.
SINCE, UNTIL = date(2023, 1, 1), date(2025, 6, 29)


def looking_back(years: int = 2) -> BacktestSettings:
    return replace(settings(), lookback_years=years)


def test_a_look_back_fetches_actions_from_1_january_and_bars_from_the_first_day() -> None:
    source = _Source(calm(), LOOKED_BACK)
    reader = _Reader()
    result = run(source, strategy=reader, chosen=looking_back())
    assert source.requests == [
        ("bars", "BBCA", START, END),
        ("actions", "BBCA", START, END),
        ("bars", "BBRI", START, END),
        ("actions", "BBRI", START, END),
        ("actions", "BBCA", SINCE, UNTIL),
        ("actions", "BBRI", SINCE, UNTIL),
    ]
    # 30 December 2022 is before the look-back; the run's own dividend shows from its ex-date.
    assert reader.seen[START] == ((PastDividend(date(2023, 3, 1), Decimal(100)),), True, True)
    assert reader.seen[END][0] == (
        PastDividend(date(2023, 3, 1), Decimal(100)),
        PastDividend(date(2025, 7, 2), Decimal(25)),
    )
    assert result.warnings == ()


def test_a_refused_look_back_warns_once_and_the_run_goes_on_without_that_history() -> None:
    source = _Source(calm(), LOOKED_BACK, refused={BBRI: [date(2024, 5, 6)]})
    reader = _Reader()
    result = run(source, strategy=reader, chosen=looking_back())
    assert [report.day for report in result.run.reports] == list(DAYS)
    assert result.warnings == (
        Note(
            DATA_DIVIDENDS_HISTORY_REFUSED,
            "BBRI: the data source refused its corporate actions from 2023-01-01 to 2025-06-29, "
            "before the run (BBRI: refused), so its dividend history is incomplete for any "
            "strategy that reads it.",
        ),
    )
    assert reader.seen[START][1:] == (True, False)
    assert reader.seen[END][1:] == (True, False)


def test_a_look_back_the_source_has_nothing_for_is_refused_history_too() -> None:
    source = _Delisted(calm())
    reader = _Reader()
    result = run(source, strategy=reader, chosen=looking_back(1))
    assert [warning.key for warning in result.warnings] == [DATA_DIVIDENDS_HISTORY_REFUSED]
    assert result.warnings[0].text.startswith(
        "BBRI: the data source refused its corporate actions from 2024-01-01 to 2025-06-29, "
        "before the run (BBRI.JK: the request to Yahoo failed: HTTP Error 404)"
    )
    assert reader.seen[END][1:] == (True, False)


def test_a_refusal_in_the_runs_own_days_keeps_its_rules_beside_a_look_back() -> None:
    source = _Source(calm(), refused={BBRI: [date(2025, 7, 3)]})
    result = run(source, chosen=looking_back())
    assert [warning.key for warning in result.warnings] == [DATA_BAR_REFUSED]
    assert ("actions", "BBRI", SINCE, UNTIL) in source.requests


class _Unpriced(_Source):
    """A source that reads corporate actions without prices, as the IDX source does (M6 plan
    scope decision 14): it refuses a stock's bars on its refused days, never its actions."""

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        self.requests.append(("actions", instrument.symbol, start, end))
        return [
            a for a in self._actions if a.instrument == instrument and start <= a.ex_date <= end
        ]


REFUSED_DIVIDEND = CashDividend(BBCA, date(2025, 7, 3), Decimal(40))
"""A BBCA dividend whose ex-date is one of its refused days."""


@pytest.mark.parametrize("years", [0, 2])
def test_a_dividend_on_a_refused_day_reaches_the_history_when_read_without_prices(
    years: int,
) -> None:
    refused = {BBCA: [date(2025, 7, 3), date(2025, 7, 4)]}
    source = _Unpriced(calm(), [*LOOKED_BACK, REFUSED_DIVIDEND], refused=refused)
    # The reader holds BBCA from 1 July and a dividend is paid the next trading day, so the
    # engine would credit the refused day's dividend inside the run were it to credit it (#184).
    reader = _Reader({BBCA: Decimal("0.5")})
    chosen = looking_back(years)
    next_day = replace(chosen, engine=replace(chosen.engine, pay_lag_trading_days=1))
    result = run(source, strategy=reader, chosen=next_day)
    assert ("actions", "BBCA", START, END) in source.requests
    # The strategy sees it from its ex-date, and BBCA's history is complete ...
    before, on = reader.seen[date(2025, 7, 2)], reader.seen[date(2025, 7, 3)]
    assert REFUSED_DIVIDEND.ex_date not in [dividend.ex_date for dividend in before[0]]
    assert on[0][-1] == PastDividend(date(2025, 7, 3), Decimal(40))
    assert on[1:] == (True, True)
    # ... while the engine still credits nothing on a refused day, as its warning says: the
    # dividend that went ex on clean 2 July is entitled that day and paid the next, refused or
    # not, while the refused day's own dividend is neither.
    assert [(r.day, e.ex_date) for r in result.run.reports for e in r.entitled] == [
        (date(2025, 7, 2), date(2025, 7, 2))
    ]
    assert [(r.day, e.ex_date) for r in result.run.reports for e in r.paid] == [
        (date(2025, 7, 3), date(2025, 7, 2))
    ]
    assert all(  # runtime population: the dividends the run's reports paid
        e.ex_date != REFUSED_DIVIDEND.ex_date for r in result.run.reports for e in r.paid
    )
    assert [warning.key for warning in result.warnings] == [DATA_BAR_REFUSED]


class _Failing(_Source):
    """A source whose read of BBCA's actions over the whole run fails outright, as Yahoo's does:
    a plain ``DataUnavailableError``, naming no day."""

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        if (instrument, start, end) == (BBCA, START, END):
            self.requests.append(("actions", instrument.symbol, start, end))
            msg = "BBCA.JK: no data from Yahoo: the request to Yahoo failed: timeout"
            raise DataUnavailableError(msg)
        return super().corporate_actions(instrument, start, end)


@pytest.mark.parametrize("source_type", [_Source, _Failing], ids=["days refused", "read failed"])
def test_a_source_that_refuses_the_actions_too_leaves_that_history_incomplete(
    source_type: type[_Source],
) -> None:
    refused = {BBCA: [date(2025, 7, 3), date(2025, 7, 4)]}
    source = source_type(calm(), [*LOOKED_BACK, REFUSED_DIVIDEND], refused=refused)
    reader = _Reader()
    result = run(source, strategy=reader, chosen=looking_back())
    # Only the clean days' actions are known, so BBCA's history is incomplete from the start.
    assert reader.seen[START][1:] == (False, True)
    assert reader.seen[END][0][-1] == PastDividend(date(2025, 7, 2), Decimal(25))
    assert [warning.key for warning in result.warnings] == [DATA_BAR_REFUSED]


def test_the_source_s_data_notes_cover_the_window_and_follow_the_universe_s() -> None:
    source = _Source(calm(), notes=[RESTORED])
    result = run(source, _Universe([(START, frozenset({BBCA, BBRI}))], warnings=[GAP]))
    assert source.noted == [(("BBCA", "BBRI"), START, END)]
    assert result.warnings == (GAP, RESTORED)


def test_the_source_s_data_notes_reach_back_over_the_look_back() -> None:
    source = _Source(calm(), LOOKED_BACK, notes=[RESTORED])
    result = run(source, chosen=looking_back())
    assert source.noted == [(("BBCA", "BBRI"), SINCE, END)]
    assert result.warnings == (RESTORED,)
    compared = _Source(calm(), LOOKED_BACK, notes=[RESTORED])
    comparison = compare([_Reader()], market(compared), START, END, looking_back(1))
    assert compared.noted == [(("BBCA", "BBRI"), date(2024, 1, 1), END)]
    assert comparison.warnings == (RESTORED,)


def test_compare_fetches_the_look_back_once_for_every_strategy() -> None:
    source = _Source(calm(), LOOKED_BACK)
    reader = _Reader()
    compare([_Fixed({BBCA: Decimal("0.5")}), reader], market(source), START, END, looking_back(1))
    assert [request for request in source.requests if request[2] < START] == [
        ("actions", "BBCA", date(2024, 1, 1), UNTIL),
        ("actions", "BBRI", date(2024, 1, 1), UNTIL),
    ]
    assert reader.seen[START][0] == ()


def test_day_inputs_give_every_day_the_look_back() -> None:
    source = _Source(calm(), LOOKED_BACK, refused={BBRI: [date(2024, 5, 6)]})
    inputs = day_inputs(market(source), START, END, 2)
    assert all(  # runtime population: the inputs day_inputs returned
        day.past_actions is inputs[0].past_actions for day in inputs
    )
    history = inputs[0].past_actions
    assert history.dividends(BBCA, START) == (PastDividend(date(2023, 3, 1), Decimal(100)),)
    assert history.incomplete == frozenset({BBRI})
    assert day_inputs(market(_Source(calm())), START, END)[0].past_actions.incomplete == frozenset()
    with pytest.raises(ValueError, match=r"^lookback_years must be at least 0, got -1$"):
        day_inputs(market(source), START, END, -1)


def test_the_look_back_is_a_whole_number_of_years() -> None:
    with pytest.raises(ValueError, match=r"^lookback_years must be at least 0, got -1$"):
        BacktestSettings(rp(1), lookback_years=-1)
    with pytest.raises(TypeError, match=r"^lookback_years must be an int, got bool$"):
        BacktestSettings(rp(1), lookback_years=True)
