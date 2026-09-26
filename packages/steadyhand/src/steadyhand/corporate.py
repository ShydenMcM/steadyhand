"""Corporate actions on their ex-date, before anything fills (core spec §5 step 2, M3 spec §4).

In order: splits change the share count, cash dividends create entitlements for what was held
at the previous close, entitlements due today are paid (and taxed), and any other action on a
held stock freezes it for the rest of the run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.market import MarketRules
from steadyhand.money import CurrencyMismatchError, Money, Rounding
from steadyhand.outcomes import Rejected
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import CashDividend, CorporateAction, Instrument, Order, OtherAction, Split

PAY_LAG_TRADING_DAYS = 14
"""Trading days from ex-date to the modelled pay date: the 90th percentile of 47 KSEI-scheduled
dividends in 2025-2026 (core spec §5 step 2, docs/research/t-pay.md §4)."""


@dataclass(frozen=True, slots=True)
class Entitlement:
    """A cash dividend earned on ``ex_date`` by the shares then held, paid on ``pay_date``."""

    instrument: Instrument
    ex_date: date
    pay_date: date
    gross: Money

    def __post_init__(self) -> None:
        require_type(self.instrument, Instrument, "instrument")
        require_date(self.ex_date, "ex_date")
        require_date(self.pay_date, "pay_date")
        require_type(self.gross, Money, "gross")
        if self.pay_date <= self.ex_date:
            msg = f"{self.instrument.symbol}: paid {self.pay_date}, not after its ex-date"
            raise ValueError(msg)
        if self.gross.currency != self.instrument.currency:
            raise CurrencyMismatchError(self.instrument.currency, self.gross.currency)
        if self.gross.amount <= 0:
            msg = f"{self.instrument.symbol}: an entitlement must be positive, got {self.gross}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Holdings:
    """The portfolio and what the engine keeps about its stocks from one day to the next.

    ``pending`` holds the orders queued for the next open, ``frozen`` each frozen stock with
    its reason, and ``last_closes`` the last close of each held stock, which values it on a
    day with no bar.
    """

    portfolio: Portfolio
    pending: tuple[Order, ...] = ()
    entitlements: tuple[Entitlement, ...] = ()
    frozen: Mapping[Instrument, str] = field(default_factory=dict)
    last_closes: Mapping[Instrument, Money] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_type(self.portfolio, Portfolio, "portfolio")
        for order in self.pending:
            require_type(order, Order, "pending order")
        for entitlement in self.entitlements:
            require_type(entitlement, Entitlement, "entitlement")


@dataclass(frozen=True, slots=True)
class CorporateOutcome:
    """The holdings after today's actions, and what the day's report says about them."""

    holdings: Holdings
    cancelled: tuple[Rejected, ...]
    entitled: tuple[Entitlement, ...]
    paid: tuple[Entitlement, ...]
    tax: Money
    frozen: tuple[tuple[Instrument, str], ...]
    warnings: tuple[str, ...]


def apply_actions(
    holdings: Holdings,
    actions: Sequence[CorporateAction],
    day: date,
    rules: MarketRules,
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS,
) -> CorporateOutcome:
    """Apply *actions*, every one of them with its ex-date on *day*, to *holdings*."""
    require_int(pay_lag_trading_days, "pay_lag_trading_days", minimum=1)
    for action in actions:
        if action.ex_date != day:
            msg = f"{action.instrument.symbol}: an action dated {action.ex_date} applied on {day}"
            raise ValueError(msg)
    run = _Actions(holdings, day)
    for action in actions:
        if isinstance(action, Split):
            run.split(action)
    for action in actions:
        if isinstance(action, CashDividend):
            run.entitle(action, _add_trading_days(rules, day, pay_lag_trading_days))
    run.pay(rules)
    for action in actions:
        if isinstance(action, OtherAction):
            run.freeze(action)
    return run.outcome()


class _Actions:
    """One day's actions in progress. Dividends are earned on the shares held at the previous
    close, which is ``holdings.portfolio`` as it came in, before today's splits."""

    def __init__(self, holdings: Holdings, day: date) -> None:
        self._before = holdings.portfolio
        self._portfolio = holdings.portfolio
        self._day = day
        self._pending = list(holdings.pending)
        self._entitlements = list(holdings.entitlements)
        self._frozen = dict(holdings.frozen)
        self._closes = dict(holdings.last_closes)
        self._cancelled: list[Rejected] = []
        self._entitled: list[Entitlement] = []
        self._paid: list[Entitlement] = []
        self._tax = Money.zero(holdings.portfolio.currency)
        self._newly_frozen: list[tuple[Instrument, str]] = []
        self._warnings: list[str] = []

    def split(self, split: Split) -> None:
        stock = split.instrument
        held = self._portfolio.position(stock)
        if held is not None:
            self._portfolio = self._portfolio.apply_split(split)
            if held.quantity * split.new_shares % split.old_shares:
                after = self._portfolio.position(stock)
                kept = 0 if after is None else after.quantity
                self._warnings.append(
                    f"{stock.symbol}: the {split.new_shares}-for-{split.old_shares} split on "
                    f"{self._day.isoformat()} turned {held.quantity} shares into {kept}; the "
                    "fraction of a share left over is dropped (cash in lieu is not modelled)"
                )
        close = self._closes.get(stock)
        if close is not None:
            scaled = close.amount * split.old_shares // split.new_shares
            self._closes[stock] = Money(scaled, close.currency)
        for order in [order for order in self._pending if order.instrument == stock]:
            self._pending.remove(order)
            self._cancelled.append(Rejected(order, "split on ex-date"))

    def entitle(self, dividend: CashDividend, pay_date: date) -> None:
        held = self._before.position(dividend.instrument)
        if held is None:
            return
        unit = Money(10**self._before.currency.minor_units, self._before.currency)
        gross = unit.times(dividend.per_share * held.quantity, Rounding.DOWN)
        if gross.amount > 0:
            entitlement = Entitlement(dividend.instrument, self._day, pay_date, gross)
            self._entitlements.append(entitlement)
            self._entitled.append(entitlement)

    def pay(self, rules: MarketRules) -> None:
        for entitlement in [e for e in self._entitlements if e.pay_date <= self._day]:
            self._entitlements.remove(entitlement)
            self._portfolio = self._portfolio.credit_dividend(entitlement.gross, self._day)
            tax = rules.dividend_tax(entitlement.gross, reinvested_by_deadline=False, on=self._day)
            if tax.amount > 0:
                self._portfolio = self._portfolio.charge(MovementKind.TAX, tax, self._day)
                self._tax += tax
            self._paid.append(entitlement)

    def freeze(self, action: OtherAction) -> None:
        stock = action.instrument
        if self._portfolio.position(stock) is not None and stock not in self._frozen:
            self._frozen[stock] = action.description
            self._newly_frozen.append((stock, action.description))

    def outcome(self) -> CorporateOutcome:
        holdings = Holdings(
            self._portfolio,
            tuple(self._pending),
            tuple(self._entitlements),
            self._frozen,
            self._closes,
        )
        return CorporateOutcome(
            holdings,
            tuple(self._cancelled),
            tuple(self._entitled),
            tuple(self._paid),
            self._tax,
            tuple(self._newly_frozen),
            tuple(self._warnings),
        )


def _add_trading_days(rules: MarketRules, day: date, count: int) -> date:
    current = day
    for _ in range(count):
        current += timedelta(days=1)
        while not rules.is_trading_day(current):
            current += timedelta(days=1)
    return current
