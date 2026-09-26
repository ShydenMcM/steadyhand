"""One trading day, from yesterday's state to today's (core spec §5, M3 spec §3).

``run_day`` is pure: it takes the previous ``EngineState`` and the day's ``DayInputs`` and returns
a new state and a ``DayReport``, changing nothing in place. A backtest repeats it over the
trading days; M5 will save each new state in one transaction, so a crash leaves yesterday's
state and a second run of the same day is refused rather than repeated.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.broker.simulated import FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.corporate import PAY_LAG_TRADING_DAYS, Entitlement, Holdings, apply_actions
from steadyhand.market import MarketRules
from steadyhand.money import Money
from steadyhand.outcomes import Cut, Rejected
from steadyhand.portfolio import Portfolio
from steadyhand.risk import Halt, RiskLimits, RiskManager, UnitValue
from steadyhand.sizing import CompoundingSizer
from steadyhand.strategies.protocol import Memory, Strategy
from steadyhand.types import CorporateAction, Fill, Instrument, Order, Split
from steadyhand.view import MarketView, PortfolioView, PriceHistory, Tradable


class DataValidationError(ValueError):
    """Today's prices are impossible, so nothing trades (M3 spec §7.4). M5 exits with code 3."""

    def __init__(self, instrument: Instrument, day: date, check: str) -> None:
        super().__init__(f"{instrument.symbol} on {day.isoformat()}: {check}")


class DayOrderError(ValueError):
    """A day was run out of order: not after the last day run, or not a trading day."""


@dataclass(frozen=True, slots=True)
class EngineSettings:
    """How the engine runs a day. Every default is the core spec's."""

    fills: FillSettings = field(default_factory=FillSettings)
    limits: RiskLimits = field(default_factory=RiskLimits)
    monthly_contribution: Money | None = None
    """Cash deposited on the first trading day of each month, before the decision."""
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS

    def __post_init__(self) -> None:
        require_type(self.fills, FillSettings, "fills")
        require_type(self.limits, RiskLimits, "limits")
        if self.monthly_contribution is not None:
            require_type(self.monthly_contribution, Money, "monthly_contribution")
            if self.monthly_contribution.amount <= 0:
                msg = f"a monthly contribution must be positive, got {self.monthly_contribution}"
                raise ValueError(msg)
        require_int(self.pay_lag_trading_days, "pay_lag_trading_days", minimum=1)


@dataclass(frozen=True, slots=True)
class EngineState:
    """Everything the engine carries from one day to the next. M5 saves it."""

    holdings: Holdings
    units: UnitValue = field(default_factory=UnitValue)
    halt: Halt | None = None
    last_day: date | None = None
    memory: Memory = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_type(self.holdings, Holdings, "holdings")
        require_type(self.units, UnitValue, "units")
        if self.halt is not None:
            require_type(self.halt, Halt, "halt")
        if self.last_day is not None:
            require_date(self.last_day, "last_day")

    @classmethod
    def opening(cls, capital: Money, day: date) -> EngineState:
        """A run's first state: *capital* deposited on *day*, the first day to run."""
        portfolio = Portfolio.empty(capital.currency).deposit(capital, day)
        return cls(Holdings(portfolio), UnitValue().deposit(capital))


@dataclass(frozen=True, slots=True)
class DayInputs:
    """What the world supplies for one day.

    ``history`` holds every bar the run may use; today's bars are the ones dated ``day``.
    ``actions`` are the corporate actions with today's ex-date. ``members`` and ``excluded`` come
    from the universe. ``refused`` names the stocks whose data source refused today (M3 spec
    §7.3), and ``resumed`` those whose data is clean again today after refused days, which have
    no usable previous close for the band check.
    """

    day: date
    history: PriceHistory
    actions: tuple[CorporateAction, ...] = ()
    members: frozenset[Instrument] = frozenset()
    excluded: Mapping[Instrument, str] = field(default_factory=dict)
    refused: frozenset[Instrument] = frozenset()
    resumed: frozenset[Instrument] = frozenset()

    def __post_init__(self) -> None:
        require_date(self.day, "day")
        require_type(self.history, PriceHistory, "history")
        for name in ("members", "refused", "resumed"):
            require_type(getattr(self, name), frozenset, name)


@dataclass(frozen=True, slots=True)
class DayReport:
    """What happened on one day, for the report and the audit log (core spec §5 step 7)."""

    day: date
    fills: tuple[Fill, ...]
    rejected: tuple[Rejected, ...]
    cuts: tuple[Cut, ...]
    queued: tuple[Order, ...]
    entitled: tuple[Entitlement, ...]
    paid: tuple[Entitlement, ...]
    tax: Money
    daily_cost: Money
    deposit: Money
    frozen: tuple[tuple[Instrument, str], ...]
    halt: Halt | None
    settled: Money
    unsettled: Money
    holdings_value: Money
    value: Money
    warnings: tuple[str, ...]


def run_day(
    state: EngineState,
    inputs: DayInputs,
    strategy: Strategy,
    rules: MarketRules,
    settings: EngineSettings | None = None,
) -> tuple[EngineState, DayReport]:
    """Run *inputs.day*: validate, apply corporate actions, fill, value, decide and queue."""
    settings = EngineSettings() if settings is None else settings
    day = inputs.day
    if state.last_day is not None and day <= state.last_day:
        msg = f"{day.isoformat()} is not after the last day run, {state.last_day.isoformat()}"
        raise DayOrderError(msg)
    if not rules.is_trading_day(day):
        msg = f"{day.isoformat()} is not a trading day"
        raise DayOrderError(msg)
    history = inputs.history
    _validate(inputs, rules)

    holdings, newly_excluded = _freeze_excluded(state.holdings, inputs.excluded)
    corporate = apply_actions(holdings, inputs.actions, day, rules, settings.pay_lag_trading_days)
    holdings = corporate.holdings
    filled = _fill(holdings, inputs, rules, settings.fills)
    portfolio = filled.portfolio

    closes = _closes(portfolio, holdings.last_closes, history, day)
    holdings_value = portfolio.holdings_value(closes)
    units = state.units.revalue(portfolio.cash_balance() + holdings_value)
    risk = RiskManager(rules, settings.limits)
    new_halt = None if state.halt is not None else risk.halt(state.units, units, day)
    halt = state.halt or new_halt

    portfolio, units, deposit = _top_up(portfolio, units, settings.monthly_contribution, rules, day)
    value = portfolio.cash_balance() + holdings_value

    held = {position.instrument: position.quantity for position in portfolio.positions}
    tradable, warnings = _tradable(inputs, frozenset(held), holdings.frozen, closes)
    queued: tuple[Order, ...] = ()
    rejected = [*corporate.cancelled, *filled.rejected]
    cuts = list(filled.cuts)
    memory = state.memory
    if halt is None:
        spendable = max(portfolio.spendable_cash(day), Money.zero(portfolio.currency))
        worth = {stock: closes[stock] * quantity for stock, quantity in held.items()}
        seen = PortfolioView(value, spendable, worth)
        view = MarketView(history, day, tradable)
        decision = strategy.decide(view, seen, state.memory)
        prices = dict(closes)
        for stock in decision.weights:
            if stock not in prices and (close := view.last_close(stock)) is not None:
                prices[stock] = close
        sized = CompoundingSizer(rules).size(decision.weights, seen, held, prices, day)
        checked = risk.check(sized, seen, tradable, prices)
        queued = checked.orders
        rejected += checked.rejected
        cuts += checked.cuts
        memory = decision.memory

    new_holdings = Holdings(portfolio, queued, holdings.entitlements, holdings.frozen, closes)
    report = DayReport(
        day=day,
        fills=filled.fills,
        rejected=tuple(rejected),
        cuts=tuple(cuts),
        queued=queued,
        entitled=corporate.entitled,
        paid=corporate.paid,
        tax=corporate.tax,
        daily_cost=filled.daily_cost,
        deposit=deposit,
        frozen=(*newly_excluded, *corporate.frozen),
        halt=new_halt,
        settled=portfolio.settled_cash(day),
        unsettled=portfolio.unsettled_cash(day),
        holdings_value=holdings_value,
        value=value,
        warnings=(*corporate.warnings, *warnings),
    )
    return EngineState(new_holdings, units, halt, day, memory), report


def _fill(
    holdings: Holdings, inputs: DayInputs, rules: MarketRules, settings: FillSettings
) -> FillResult:
    """Fill yesterday's orders at today's open, each banded around its previous close."""
    day = inputs.day
    ordered = {order.instrument for order in holdings.pending}
    opening = Opening(
        day,
        {i: bar for i in ordered if (bar := inputs.history.on(i, day)) is not None},
        {i: bar.close for i in ordered if (bar := inputs.history.before(i, day)) is not None},
        holdings.frozen,
    )
    return SimulatedBroker(rules, settings).fill(holdings.portfolio, holdings.pending, opening)


def _validate(inputs: DayInputs, rules: MarketRules) -> None:
    """Refuse a close outside the band around the previous close, where that close applies."""
    day = inputs.day
    split = {action.instrument for action in inputs.actions if isinstance(action, Split)}
    exempt = split | inputs.resumed
    for instrument in sorted(inputs.history.instruments, key=lambda i: (i.market, i.symbol)):
        bar = inputs.history.on(instrument, day)
        previous = inputs.history.before(instrument, day)
        if bar is None or previous is None or instrument in exempt:
            continue
        low, high = rules.price_band(instrument, previous.close, day)
        if not low <= bar.close <= high:
            check = (
                f"the close {bar.close} is outside the band {low} to {high} around the "
                f"previous close {previous.close}"
            )
            raise DataValidationError(instrument, day, check)


def _freeze_excluded(
    holdings: Holdings, excluded: Mapping[Instrument, str]
) -> tuple[Holdings, tuple[tuple[Instrument, str], ...]]:
    """Freeze each held stock that is excluded today (core spec §6.1)."""
    frozen = dict(holdings.frozen)
    newly: list[tuple[Instrument, str]] = []
    for instrument in sorted(excluded, key=lambda i: (i.market, i.symbol)):
        if holdings.portfolio.position(instrument) is not None and instrument not in frozen:
            frozen[instrument] = f"excluded: {excluded[instrument]}"
            newly.append((instrument, frozen[instrument]))
    return replace(holdings, frozen=frozen), tuple(newly)


def _closes(
    portfolio: Portfolio, last: Mapping[Instrument, Money], history: PriceHistory, day: date
) -> dict[Instrument, Money]:
    """Each held stock's close today, or its last close when it has no bar today."""
    closes: dict[Instrument, Money] = {}
    for position in portfolio.positions:
        bar = history.on(position.instrument, day)
        close = bar.close if bar is not None else last.get(position.instrument)
        if close is not None:
            closes[position.instrument] = close
    return closes


def _tradable(
    inputs: DayInputs,
    held: frozenset[Instrument],
    frozen: Mapping[Instrument, str],
    closes: Mapping[Instrument, Money],
) -> tuple[Tradable, list[str]]:
    """Today's buyable and sellable stocks (M3 spec §6.4), and a warning for each missing bar."""
    day = inputs.day
    reasons: dict[Instrument, str] = {}
    for instrument in inputs.refused:
        reasons[instrument] = f"the data source refused {day.isoformat()}"
    for instrument, reason in frozen.items():
        reasons.setdefault(instrument, f"frozen: {reason}")
    for instrument, reason in inputs.excluded.items():
        reasons.setdefault(instrument, f"excluded: {reason}")
    warnings: list[str] = []
    for instrument in sorted(inputs.members | held, key=lambda i: (i.market, i.symbol)):
        if instrument in reasons or inputs.history.on(instrument, day) is not None:
            continue
        reasons[instrument] = f"no bar on {day.isoformat()}"
        warning = f"{instrument.symbol} has no bar on {day.isoformat()}, so it is not traded"
        if instrument in held:
            warning += f"; it is valued at its last close, {closes[instrument]}"
        warnings.append(warning)
    buyable = frozenset(inputs.members - reasons.keys())
    sellable = frozenset(held - reasons.keys())
    return Tradable(day, buyable, sellable, reasons), warnings


def _top_up(
    portfolio: Portfolio,
    units: UnitValue,
    contribution: Money | None,
    rules: MarketRules,
    day: date,
) -> tuple[Portfolio, UnitValue, Money]:
    """Deposit the monthly contribution on the month's first trading day (M3 spec §6.5)."""
    if contribution is None or not _first_trading_day_of_month(rules, day):
        return portfolio, units, Money.zero(portfolio.currency)
    return portfolio.deposit(contribution, day), units.deposit(contribution), contribution


def _first_trading_day_of_month(rules: MarketRules, day: date) -> bool:
    earlier = day.replace(day=1)
    while earlier < day:
        if rules.is_trading_day(earlier):
            return False
        earlier += timedelta(days=1)
    return True
