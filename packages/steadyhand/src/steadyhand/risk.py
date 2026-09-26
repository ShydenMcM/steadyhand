"""Risk controls: what may be ordered, and when all ordering stops (core spec §6.1, M3 §6.3).

Losses are read from a fund-style unit value, not the portfolio's value, so a top-up never
looks like a gain and never hides a loss: a deposit buys units at today's price per unit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_date, require_int, require_type
from steadyhand.market import MarketRules
from steadyhand.money import Money, Rounding
from steadyhand.outcomes import Cut, Rejected
from steadyhand.types import Instrument, Order, Side
from steadyhand.view import PortfolioView, Tradable


def _percent(rate: Decimal) -> str:
    return f"{(rate * 100).quantize(Decimal('0.01'), rounding=ROUND_FLOOR)}%"


def _rate(value: object, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        msg = f"{name} must be a finite Decimal, got {value!r}"
        raise TypeError(msg)


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Every limit the risk manager applies. The defaults are core spec §6.1's."""

    max_weight: Decimal = Decimal("0.10")
    """The most one stock may be of the portfolio's value. A buy is cut to it."""
    min_lots: int = 1
    """The smallest buy, in lots. A smaller buy is dropped."""
    daily_loss: Decimal = Decimal("0.05")
    """A fall in the unit value this large in one day halts ordering."""
    max_drawdown: Decimal = Decimal("0.25")
    """A fall this far below the unit value's high-water mark halts ordering."""

    def __post_init__(self) -> None:
        for name in ("max_weight", "daily_loss", "max_drawdown"):
            _rate(getattr(self, name), name)
        require_int(self.min_lots, "min_lots", minimum=1)
        if not 0 < self.max_weight <= 1:
            msg = f"max_weight must be above 0 and at most 1, got {self.max_weight}"
            raise ValueError(msg)
        for name in ("daily_loss", "max_drawdown"):
            if not 0 < getattr(self, name) < 1:
                msg = f"{name} must be above 0 and below 1, got {getattr(self, name)}"
                raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Halt:
    """Ordering stopped on ``day``, for ``cause``. In a backtest it lasts to the end of the run."""

    day: date
    cause: str

    def __post_init__(self) -> None:
        require_date(self.day, "halt day")
        require_type(self.cause, str, "cause")
        if not self.cause.strip():
            msg = "a halt needs a cause"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class UnitValue:
    """The portfolio as a fund: ``units`` outstanding, each worth ``price`` at the last valuation.

    Before the first deposit there are no units and the price is 1.
    """

    units: Decimal = Decimal(0)
    price: Decimal = Decimal(1)
    high_water: Decimal = Decimal(1)

    def __post_init__(self) -> None:
        for name in ("units", "price", "high_water"):
            _rate(getattr(self, name), name)
            if getattr(self, name) < 0:
                msg = f"{name} cannot be negative, got {getattr(self, name)}"
                raise ValueError(msg)

    def revalue(self, value: Money) -> UnitValue:
        """The price per unit when the portfolio is worth *value*. Nothing changes before units."""
        if self.units == 0:
            return self
        price = ratio_down(value.amount, self.units)
        return UnitValue(self.units, price, max(self.high_water, price))

    def deposit(self, amount: Money) -> UnitValue:
        """Buy units with *amount* at the current price, which the deposit leaves unchanged."""
        if self.price == 0:
            msg = "no units can be bought at a price of 0"
            raise ValueError(msg)
        return UnitValue(
            self.units + ratio_down(amount.amount, self.price), self.price, self.high_water
        )


@dataclass(frozen=True, slots=True)
class Checked:
    """Orders the risk manager passed, and those it dropped or cut, each with its reason."""

    orders: tuple[Order, ...]
    rejected: tuple[Rejected, ...]
    cuts: tuple[Cut, ...]


class RiskManager:
    """Applies ``RiskLimits`` to sized orders, and decides when to halt."""

    def __init__(self, rules: MarketRules, limits: RiskLimits | None = None) -> None:
        self._rules = rules
        self._limits = RiskLimits() if limits is None else limits

    @property
    def limits(self) -> RiskLimits:
        return self._limits

    def check(
        self,
        orders: Sequence[Order],
        portfolio: PortfolioView,
        tradable: Tradable,
        prices: Mapping[Instrument, Money],
    ) -> Checked:
        """Drop or cut *orders* placed on the tradable set's day, in the order given.

        Buys are sized at the last close in *prices*, costs included, and together never spend
        more than ``portfolio.spendable``. Sale proceeds are not counted: they are not settled.
        """
        day = tradable.day
        passed: list[Order] = []
        rejected: list[Rejected] = []
        cuts: list[Cut] = []
        budget = portfolio.spendable
        cap = portfolio.value.times(self._limits.max_weight, Rounding.DOWN)
        for order in orders:
            reason = tradable.why_not(order.instrument, order.side)
            if reason is not None:
                rejected.append(Rejected(order, reason))
                continue
            if order.side is Side.SELL:
                passed.append(order)
                continue
            lot = self._rules.lot_size(order.instrument, day)
            price = prices[order.instrument]
            held = portfolio.holdings.get(order.instrument, Money.zero(price.currency))
            room = (cap - held).amount // (price * lot).amount * lot
            quantity = min(order.quantity, max(room, 0))
            if quantity < order.quantity:
                limit = _percent(self._limits.max_weight)
                if quantity == 0:
                    rejected.append(Rejected(order, f"already at the {limit} limit per stock"))
                    continue
                cuts.append(Cut(order, quantity, f"cut to the {limit} limit per stock"))
            smallest = self._limits.min_lots * lot
            if quantity < smallest:
                reason = f"below the minimum buy of {self._limits.min_lots} lot(s)"
                rejected.append(Rejected(order, reason))
                continue
            affordable = self._affordable(order.instrument, quantity, price, budget, day)
            if affordable == 0:
                rejected.append(Rejected(order, f"not enough cash: {budget} can be spent"))
                continue
            if affordable < quantity:
                cuts.append(Cut(order, affordable, f"cut to the {budget} that can be spent"))
            budget -= self._cost(affordable, price, day)
            passed.append(Order(order.instrument, order.side, affordable, order.placed_on))
        return Checked(tuple(passed), tuple(rejected), tuple(cuts))

    def halt(self, before: UnitValue, after: UnitValue, day: date) -> Halt | None:
        """A halt when today's unit value breaches a limit, reaching it included; else ``None``."""
        if before.units > 0:
            fall = 1 - ratio_down(after.price, before.price)
            if fall >= self._limits.daily_loss:
                limit = _percent(self._limits.daily_loss)
                cause = (
                    f"daily loss limit: the unit value fell {_percent(fall)}, the limit is {limit}"
                )
                return Halt(day, cause)
        drawdown = 1 - ratio_down(after.price, after.high_water)
        if after.units > 0 and drawdown >= self._limits.max_drawdown:
            limit = _percent(self._limits.max_drawdown)
            cause = (
                f"drawdown kill switch: the unit value is {_percent(drawdown)} below its "
                f"high-water mark, the limit is {limit}"
            )
            return Halt(day, cause)
        return None

    def _affordable(
        self, instrument: Instrument, quantity: int, price: Money, budget: Money, day: date
    ) -> int:
        lot = self._rules.lot_size(instrument, day)
        quantity = min(quantity, max(budget.amount, 0) // (price * lot).amount * lot)
        while quantity > 0 and self._cost(quantity, price, day) > budget:
            quantity -= lot
        return quantity

    def _cost(self, quantity: int, price: Money, day: date) -> Money:
        gross = price * quantity
        return gross + self._rules.costs(Side.BUY, gross, day).total
