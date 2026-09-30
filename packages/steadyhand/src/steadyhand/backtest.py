"""The backtester: a strategy and the ``buy-and-hold`` baseline over a range of days (M3 spec §7).

``backtest`` checks the range before day one, fetches every bar and corporate action the run can
need, and with a look-back the corporate actions of the years before it (M6 spec §4.3), then
repeats ``run_day`` over the trading days: once for the strategy and once, with the same
settings, for the baseline. Nothing is guessed: a start the rules or the universe do not
cover stops the run with an error that names the first date that would work. With an income goal
set, each run also gets an income report on its last day, from dividend history fetched then.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.data import DataSource, DataUnavailableError, UnavailableDaysError
from steadyhand.engine import DayInputs, DayReport, EngineSettings, EngineState, run_day
from steadyhand.income import (
    HISTORY_YEARS,
    IncomeGoal,
    IncomeReport,
    IncomeSettings,
    income_report,
    years_before,
)
from steadyhand.market import MarketRules
from steadyhand.metrics import Metrics, measure
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import DATA_BAR_REFUSED, DATA_DIVIDENDS_HISTORY_REFUSED, Note
from steadyhand.risk import Halt
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Strategy
from steadyhand.types import Bar, CorporateAction, Instrument
from steadyhand.universe import Universe
from steadyhand.view import ActionHistory, PriceHistory


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
    """The capital a run starts with, how the engine runs each day, an optional income goal, and
    how many calendar years of corporate actions before the first day to fetch.

    Both runs share them. With a ``goal``, each run's result carries an income report. The
    caller sets ``lookback_years`` from the registered strategy's (M6 spec §4.3), so the engine
    never reads the registry.
    """

    capital: Money
    engine: EngineSettings = field(default_factory=EngineSettings)
    goal: IncomeGoal | None = None
    lookback_years: int = 0

    def __post_init__(self) -> None:
        require_type(self.capital, Money, "capital")
        require_type(self.engine, EngineSettings, "engine")
        require_int(self.lookback_years, "lookback_years", minimum=0)
        if self.capital.amount <= 0:
            msg = f"the starting capital must be positive, got {self.capital}"
            raise ValueError(msg)
        if self.goal is not None:
            require_type(self.goal, IncomeGoal, "goal")
            if self.goal.monthly_target.currency != self.capital.currency:
                raise CurrencyMismatchError(
                    self.capital.currency, self.goal.monthly_target.currency
                )


@dataclass(frozen=True, slots=True)
class RunResult:
    """One strategy's run: every day's report, in order, the state after the last day, what the
    run achieved (M3 spec §8), and its income report when the settings set a goal (M4 spec §8)."""

    strategy: str
    reports: tuple[DayReport, ...]
    final: EngineState
    metrics: Metrics
    income: IncomeReport | None = None

    @property
    def halt(self) -> Halt | None:
        """The halt that stopped ordering, which lasts to the end of the run (decision 4)."""
        return self.final.halt

    @property
    def warnings(self) -> tuple[Note, ...]:
        """Every day's warnings, in day order."""
        return tuple(warning for report in self.reports for warning in report.warnings)


@dataclass(frozen=True, slots=True)
class IncomeImpact:
    """The strategy's monthly take-home income minus the baseline's (core spec §7).

    ``received`` compares the monthly averages over the trailing year and ``run_rate`` the
    run-rates. Each is negative when the strategy earns less than ``buy-and-hold``.
    """

    received: Money
    run_rate: Money


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """The strategy's run and, unless the strategy is the baseline, the baseline's.

    ``warnings`` are about the data both runs share: gaps in the universe's membership record,
    and each stock whose data source refused some of its days. ``income_impact`` is set when
    there is a goal and a baseline.
    """

    start: date
    end: date
    run: RunResult
    baseline: RunResult | None
    warnings: tuple[Note, ...]
    income_impact: IncomeImpact | None = None


@dataclass(frozen=True, slots=True)
class Comparison:
    """Several strategies run over one window (M5 spec §5.4).

    ``runs`` holds each strategy's run in the order they were named, then the baseline's unless
    it was named. ``warnings`` are about the data every run shares, as in ``BacktestResult``.
    """

    start: date
    end: date
    runs: tuple[RunResult, ...]
    warnings: tuple[Note, ...]


@dataclass(frozen=True, slots=True)
class _Window:
    """Everything both runs read: the trading days, the universe on each, and the fetched data.

    ``past`` holds every corporate action fetched, the look-back's and a refused stock's refused
    days' included; ``lookback`` is the look-back's first and last day, and ``history_refused``
    why the source refused a stock's.
    """

    days: tuple[date, ...]
    members: Mapping[date, frozenset[Instrument]]
    excluded: Mapping[date, Mapping[Instrument, str]]
    history: PriceHistory
    actions: Mapping[date, tuple[CorporateAction, ...]]
    refused: Mapping[Instrument, tuple[date, ...]]
    past: ActionHistory
    lookback: tuple[date, date] | None
    history_refused: Mapping[Instrument, str]


def backtest(
    strategy: Strategy, market: Market, start: date, end: date, settings: BacktestSettings
) -> BacktestResult:
    """Run *strategy* and the baseline from *start* to *end*, both inclusive (M3 spec §7.1)."""
    window = _window(market, start, end, settings)
    inputs = _inputs(window)
    run = _complete(_run(strategy, inputs, market.rules, settings), market, settings)
    baseline = BuyAndHold()
    compared = (
        None
        if strategy.name == baseline.name
        else _complete(_run(baseline, inputs, market.rules, settings), market, settings)
    )
    warnings = _data_warnings(market, window, start, end)
    return BacktestResult(start, end, run, compared, warnings, _impact(run, compared))


def compare(
    strategies: Sequence[Strategy],
    market: Market,
    start: date,
    end: date,
    settings: BacktestSettings,
) -> Comparison:
    """Run each of *strategies*, and the baseline unless it is one of them, over one window
    fetched once (M5 spec §5.4). The caller sets the longest look-back among them."""
    for strategy in strategies:
        require_type(strategy, Strategy, "strategy")
    names = [strategy.name for strategy in strategies]
    if not names:
        msg = "name at least one strategy to compare"
        raise ValueError(msg)
    twice = sorted({name for name in names if names.count(name) > 1})
    if twice:
        msg = f"{twice[0]} is named twice; name each strategy once"
        raise ValueError(msg)
    window = _window(market, start, end, settings)
    inputs = _inputs(window)
    baseline = BuyAndHold()
    everyone = (*strategies, *(() if baseline.name in names else (baseline,)))
    runs = tuple(
        _complete(_run(strategy, inputs, market.rules, settings), market, settings)
        for strategy in everyone
    )
    return Comparison(start, end, runs, _data_warnings(market, window, start, end))


def day_inputs(
    market: Market, start: date, end: date, lookback_years: int = 0
) -> tuple[DayInputs, ...]:
    """Every trading day's inputs from *start* to *end*, both inclusive, oldest first.

    This is a backtest's fetch step, public so that paper trading builds each day exactly as a
    backtest over the same range does (M5 spec §6.2). ``refused`` and ``resumed`` depend on the
    days before the one run, so a caller that runs only the later days still fetches from the
    first, and the look-back reaches back from *start* as a backtest's does (M6 spec §4.3).
    """
    require_type(market, Market, "market")
    require_date(start, "start")
    require_date(end, "end")
    require_int(lookback_years, "lookback_years", minimum=0)
    if end < start:
        msg = f"the range ends on {end.isoformat()}, before it starts on {start.isoformat()}"
        raise ValueError(msg)
    return _inputs(_fetch(market, _days(market, start, end), lookback_years))


def _window(market: Market, start: date, end: date, settings: BacktestSettings) -> _Window:
    """Check a run's arguments, then fetch what every strategy over them reads."""
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
    return _fetch(market, _days(market, start, end), settings.lookback_years)


def _days(market: Market, start: date, end: date) -> tuple[date, ...]:
    """The trading days from *start* to *end*, once the rules and the universe cover them."""
    rules = market.rules
    rules.require_supported(start)
    first = market.universe.first_day()
    if start < first:
        raise UniverseCoverageError(start, first)
    days = tuple(day for day in _calendar_days(start, end) if rules.is_trading_day(day))
    if not days:
        msg = f"there is no trading day from {start.isoformat()} to {end.isoformat()}"
        raise NoTradingDaysError(msg)
    return days


def _complete(run: RunResult, market: Market, settings: BacktestSettings) -> RunResult:
    """*run*, with its income report when the settings set a goal."""
    if settings.goal is None:
        return run
    return replace(run, income=income_of(run.reports, run.final, market, settings, settings.goal))


def _data_warnings(market: Market, window: _Window, start: date, end: date) -> tuple[Note, ...]:
    return (
        *market.universe.survivorship_warnings(start, end),
        *_refused_warnings(window),
        *_history_warnings(window),
    )


def _calendar_days(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _fetch(market: Market, days: tuple[date, ...], lookback_years: int) -> _Window:
    """Fetch every stock the universe holds on any of *days*, over all of them (M3 spec §7.1).

    A stock whose source refuses some days is fetched again over the clean ranges around them;
    for its history, its actions over the whole run are read in a call of their own, which a
    source that reads them without prices answers for the refused days too. If the source
    refuses that call, those days' actions are unknown and the stock's history is incomplete.
    With a look-back, each stock's corporate actions from 1 January, *lookback_years* years
    before the first day, to the day before it are fetched in a call of their own: a refusal
    there is history the run can do without, so it marks the stock's history incomplete and the
    run goes on (M6 spec §4.3).
    """
    members = {day: market.universe.members_on(day) for day in days}
    excluded = {day: market.universe.excluded_on(day) for day in days}
    source = market.source
    start, end = days[0], days[-1]
    stocks = sorted(frozenset().union(*members.values()), key=lambda i: (i.market, i.symbol))
    bars: list[Bar] = []
    actions: list[CorporateAction] = []
    refused: dict[Instrument, tuple[date, ...]] = {}
    past: list[CorporateAction] = []
    unknown: set[Instrument] = set()
    for stock in stocks:
        try:
            found = (source.bars(stock, start, end), source.corporate_actions(stock, start, end))
        except UnavailableDaysError as error:
            named = tuple(day for day in error.days if start <= day <= end)
            if not named:
                raise
            refused[stock] = named
            whole = _unpriced_actions(source, stock, start, end)
            clean: list[CorporateAction] = []
            for low, high in _clean_ranges(days, frozenset(named)):
                bars += source.bars(stock, low, high)
                clean += source.corporate_actions(stock, low, high)
            actions += clean
            if whole is None:
                unknown.add(stock)
            past += clean if whole is None else whole
            continue
        bars += found[0]
        actions += found[1]
        past += found[1]
    by_day: dict[date, list[CorporateAction]] = {}
    for action in actions:
        by_day.setdefault(action.ex_date, []).append(action)
    grouped = {day: tuple(found) for day, found in by_day.items()}
    lookback = None
    history_refused: dict[Instrument, str] = {}
    if lookback_years:
        lookback = (date(start.year - lookback_years, 1, 1), start - timedelta(days=1))
        for stock in stocks:
            try:
                past += source.corporate_actions(stock, *lookback)
            except DataUnavailableError as error:
                history_refused[stock] = str(error)
    return _Window(
        days,
        members,
        excluded,
        PriceHistory(bars),
        grouped,
        refused,
        ActionHistory(past, {*history_refused, *unknown}),
        lookback,
        history_refused,
    )


def _unpriced_actions(
    source: DataSource, stock: Instrument, start: date, end: date
) -> Sequence[CorporateAction] | None:
    """A refused stock's actions from *start* to *end*, refused days included, or ``None`` when
    the source refuses them as well (M6 plan scope decision 13)."""
    try:
        return source.corporate_actions(stock, start, end)
    except DataUnavailableError:
        return None


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


def _inputs(window: _Window) -> tuple[DayInputs, ...]:
    """Each day of *window* as the engine takes it (M3 spec §7.1)."""
    inputs: list[DayInputs] = []
    for day in window.days:
        refused = frozenset(stock for stock, found in window.refused.items() if day in found)
        inputs.append(
            DayInputs(
                day,
                window.history,
                window.actions.get(day, ()),
                window.members[day],
                window.excluded[day],
                refused,
                _resumed(window, day) - refused,
                window.past,
            )
        )
    return tuple(inputs)


def _run(
    strategy: Strategy,
    inputs: Sequence[DayInputs],
    rules: MarketRules,
    settings: BacktestSettings,
) -> RunResult:
    state = EngineState.opening(settings.capital, inputs[0].day)
    reports: list[DayReport] = []
    for day in inputs:
        state, report = run_day(state, day, strategy, rules, settings.engine)
        reports.append(report)
    return RunResult(strategy.name, tuple(reports), state, measure(reports, state))


def income_of(
    reports: Sequence[DayReport],
    final: EngineState,
    market: Market,
    settings: BacktestSettings,
    goal: IncomeGoal,
) -> IncomeReport:
    """The income report of a run whose day reports, in order, are *reports* and whose state
    after the last is *final*, from each final holding's history as *market*'s source gives it.
    A backtest and a paper account's ``report --income`` both build theirs here.

    A source that cannot give the history raises, and the caller stops: an income report is
    never built on missing history (M4 spec §8).
    """
    as_of = reports[-1].day
    since = years_before(as_of, HISTORY_YEARS)
    history = {
        position.instrument: tuple(
            market.source.corporate_actions(position.instrument, since, as_of)
        )
        for position in final.holdings.portfolio.positions
    }
    engine = settings.engine
    plan = IncomeSettings(goal, engine.monthly_contribution, engine.pay_lag_trading_days)
    return income_report(reports, final, history, market.rules, plan)


def _impact(run: RunResult, baseline: RunResult | None) -> IncomeImpact | None:
    if baseline is None or run.income is None or baseline.income is None:
        return None
    ours, theirs = run.income.goal, baseline.income.goal
    return IncomeImpact(ours.received - theirs.received, ours.run_rate - theirs.run_rate)


def _resumed(window: _Window, day: date) -> frozenset[Instrument]:
    """Stocks with a refused day between their last bar and *day*: no usable previous close."""
    resumed: set[Instrument] = set()
    for stock, refused in window.refused.items():
        previous = window.history.before(stock, day)
        after = bisect_left(refused, previous.day) if previous is not None else 0
        if after < len(refused) and refused[after] < day:
            resumed.add(stock)
    return frozenset(resumed)


def _refused_warnings(window: _Window) -> list[Note]:
    """One warning per stock, naming each span of consecutive refused trading days."""
    warnings: list[Note] = []
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
            Note(
                DATA_BAR_REFUSED,
                f"{stock.symbol}: the data source refused {len(refused)} day(s) ({named}), so it "
                "was not traded on them, and a holding was valued at its last clean close. A "
                "dividend whose ex-date falls on a refused day is unknown and was not credited.",
            )
        )
    return warnings


def _history_warnings(window: _Window) -> list[Note]:
    """One warning per stock whose look-back the source refused, naming the range and why."""
    if window.lookback is None:
        return []
    since, until = (day.isoformat() for day in window.lookback)
    return [
        Note(
            DATA_DIVIDENDS_HISTORY_REFUSED,
            f"{stock.symbol}: the data source refused its corporate actions from {since} to "
            f"{until}, before the run ({window.history_refused[stock]}), so its dividend "
            "history is incomplete for any strategy that reads it.",
        )
        for stock in sorted(window.history_refused, key=lambda i: (i.market, i.symbol))
    ]
