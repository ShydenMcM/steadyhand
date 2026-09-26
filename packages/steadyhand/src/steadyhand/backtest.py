"""The backtester: a strategy and the ``buy-and-hold`` baseline over a range of days (M3 spec §7).

``backtest`` checks the range before day one, fetches every bar and corporate action the run can
need, then repeats ``run_day`` over the trading days: once for the strategy and once, with the
same settings, for the baseline. Nothing is guessed: a start the rules or the universe do not
cover stops the run with an error that names the first date that would work.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from steadyhand._validate import require_date, require_type
from steadyhand.data import DataSource, UnavailableDaysError
from steadyhand.engine import DayInputs, DayReport, EngineSettings, EngineState, run_day
from steadyhand.market import MarketRules
from steadyhand.metrics import Metrics, measure
from steadyhand.money import Money
from steadyhand.risk import Halt
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Strategy
from steadyhand.types import Bar, CorporateAction, Instrument
from steadyhand.universe import Universe
from steadyhand.view import PriceHistory


class UniverseCoverageError(LookupError):
    """The backtest starts before the universe's first known membership (M3 spec, decision 3)."""

    def __init__(self, start: date, first: date) -> None:
        super().__init__(
            f"the backtest starts on {start.isoformat()}, but the universe's membership is only "
            f"known from {first.isoformat()}; start on {first.isoformat()} or later"
        )


class NoTradingDaysError(ValueError):
    """The range holds no trading day, so there is nothing to run."""


@dataclass(frozen=True, slots=True)
class Market:
    """Where a backtest's world comes from: the stocks it may hold, their data, and the rules."""

    universe: Universe
    source: DataSource
    rules: MarketRules

    def __post_init__(self) -> None:
        require_type(self.universe, Universe, "universe")
        require_type(self.source, DataSource, "source")
        require_type(self.rules, MarketRules, "rules")


@dataclass(frozen=True, slots=True)
class BacktestSettings:
    """The capital a run starts with, and how the engine runs each day. Both runs share them."""

    capital: Money
    engine: EngineSettings = field(default_factory=EngineSettings)

    def __post_init__(self) -> None:
        require_type(self.capital, Money, "capital")
        require_type(self.engine, EngineSettings, "engine")
        if self.capital.amount <= 0:
            msg = f"the starting capital must be positive, got {self.capital}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RunResult:
    """One strategy's run: every day's report, in order, the state after the last day, and what
    the run achieved (M3 spec §8)."""

    strategy: str
    reports: tuple[DayReport, ...]
    final: EngineState
    metrics: Metrics

    @property
    def halt(self) -> Halt | None:
        """The halt that stopped ordering, which lasts to the end of the run (decision 4)."""
        return self.final.halt

    @property
    def warnings(self) -> tuple[str, ...]:
        """Every day's warnings, in day order."""
        return tuple(warning for report in self.reports for warning in report.warnings)


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """The strategy's run and, unless the strategy is the baseline, the baseline's.

    ``warnings`` are about the data both runs share: gaps in the universe's membership record,
    and each stock whose data source refused some of its days.
    """

    start: date
    end: date
    run: RunResult
    baseline: RunResult | None
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Window:
    """Everything both runs read: the trading days, the universe on each, and the fetched data."""

    days: tuple[date, ...]
    members: Mapping[date, frozenset[Instrument]]
    excluded: Mapping[date, Mapping[Instrument, str]]
    history: PriceHistory
    actions: Mapping[date, tuple[CorporateAction, ...]]
    refused: Mapping[Instrument, tuple[date, ...]]


def backtest(
    strategy: Strategy, market: Market, start: date, end: date, settings: BacktestSettings
) -> BacktestResult:
    """Run *strategy* and the baseline from *start* to *end*, both inclusive (M3 spec §7.1)."""
    require_type(market, Market, "market")
    require_date(start, "start")
    require_date(end, "end")
    require_type(settings, BacktestSettings, "settings")
    if end < start:
        msg = f"the backtest ends on {end.isoformat()}, before it starts on {start.isoformat()}"
        raise ValueError(msg)
    rules = market.rules
    if settings.capital.currency != rules.currency:
        msg = (
            f"the capital is in {settings.capital.currency.code}, "
            f"but the market trades in {rules.currency.code}"
        )
        raise ValueError(msg)
    rules.require_supported(start)
    first = market.universe.first_day()
    if start < first:
        raise UniverseCoverageError(start, first)
    days = tuple(day for day in _calendar_days(start, end) if rules.is_trading_day(day))
    if not days:
        msg = f"there is no trading day from {start.isoformat()} to {end.isoformat()}"
        raise NoTradingDaysError(msg)
    window = _fetch(market, days)
    run = _run(strategy, window, rules, settings)
    baseline = BuyAndHold()
    compared = None if strategy.name == baseline.name else _run(baseline, window, rules, settings)
    warnings = (*market.universe.survivorship_warnings(start, end), *_refused_warnings(window))
    return BacktestResult(start, end, run, compared, warnings)


def _calendar_days(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _fetch(market: Market, days: tuple[date, ...]) -> _Window:
    """Fetch every stock the universe holds on any of *days*, over all of them (M3 spec §7.1).

    A stock whose source refuses some days is fetched again over the clean ranges around them.
    """
    members = {day: market.universe.members_on(day) for day in days}
    excluded = {day: market.universe.excluded_on(day) for day in days}
    source = market.source
    start, end = days[0], days[-1]
    bars: list[Bar] = []
    actions: list[CorporateAction] = []
    refused: dict[Instrument, tuple[date, ...]] = {}
    for stock in sorted(frozenset().union(*members.values()), key=lambda i: (i.market, i.symbol)):
        try:
            found = (source.bars(stock, start, end), source.corporate_actions(stock, start, end))
        except UnavailableDaysError as error:
            named = tuple(day for day in error.days if start <= day <= end)
            if not named:
                raise
            refused[stock] = named
            for low, high in _clean_ranges(days, frozenset(named)):
                bars += source.bars(stock, low, high)
                actions += source.corporate_actions(stock, low, high)
            continue
        bars += found[0]
        actions += found[1]
    by_day: dict[date, list[CorporateAction]] = {}
    for action in actions:
        by_day.setdefault(action.ex_date, []).append(action)
    grouped = {day: tuple(found) for day, found in by_day.items()}
    return _Window(days, members, excluded, PriceHistory(bars), grouped, refused)


def _clean_ranges(days: Sequence[date], refused: frozenset[date]) -> Iterator[tuple[date, date]]:
    """Each run of consecutive trading days holding no refused day, as its first and last day.

    Built from trading days, so a range that holds only a weekend or a holiday is never asked for.
    """
    run: list[date] = []
    for day in days:
        if day not in refused:
            run.append(day)
        elif run:
            yield run[0], run[-1]
            run = []
    if run:
        yield run[0], run[-1]


def _run(
    strategy: Strategy, window: _Window, rules: MarketRules, settings: BacktestSettings
) -> RunResult:
    state = EngineState.opening(settings.capital, window.days[0])
    reports: list[DayReport] = []
    for day in window.days:
        refused = frozenset(stock for stock, found in window.refused.items() if day in found)
        inputs = DayInputs(
            day,
            window.history,
            window.actions.get(day, ()),
            window.members[day],
            window.excluded[day],
            refused,
            _resumed(window, day) - refused,
        )
        state, report = run_day(state, inputs, strategy, rules, settings.engine)
        reports.append(report)
    return RunResult(strategy.name, tuple(reports), state, measure(reports, state))


def _resumed(window: _Window, day: date) -> frozenset[Instrument]:
    """Stocks with a refused day between their last bar and *day*: no usable previous close."""
    resumed: set[Instrument] = set()
    for stock, refused in window.refused.items():
        previous = window.history.before(stock, day)
        after = bisect_left(refused, previous.day) if previous is not None else 0
        if after < len(refused) and refused[after] < day:
            resumed.add(stock)
    return frozenset(resumed)


def _refused_warnings(window: _Window) -> list[str]:
    """One warning per stock, naming each span of consecutive refused trading days."""
    warnings: list[str] = []
    for stock in sorted(window.refused, key=lambda i: (i.market, i.symbol)):
        refused = window.refused[stock]
        spans: list[list[date]] = []
        for day in refused:
            if (
                spans
                and bisect_left(window.days, day) == bisect_left(window.days, spans[-1][-1]) + 1
            ):
                spans[-1].append(day)
            else:
                spans.append([day])
        named = ", ".join(
            span[0].isoformat()
            if len(span) == 1
            else f"{span[0].isoformat()} to {span[-1].isoformat()}"
            for span in spans
        )
        warnings.append(
            f"{stock.symbol}: the data source refused {len(refused)} day(s) ({named}), so it was "
            "not traded on them, and a holding was valued at its last clean close. A dividend "
            "whose ex-date falls on a refused day is unknown and was not credited."
        )
    return warnings
