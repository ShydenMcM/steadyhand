"""Market-neutral value types: instruments, bars, corporate actions, orders, fills, positions.

Every type validates itself when constructed, so bad data fails where it enters rather than
three steps later. Lot sizes, ticks and price bands are market rules, not type rules: they live
in a ``MarketRules`` implementation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.money import Currency, CurrencyMismatchError, Money

_SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9.\-]{0,19}")
_MARKET = re.compile(r"[A-Z]{2,10}")


class Side(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Instrument:
    """A tradable stock: its exchange symbol (``BBRI``), market (``IDX``) and currency."""

    symbol: str
    market: str
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str):
            msg = f"symbol must be a str, got {type(self.symbol).__name__}"
            raise TypeError(msg)
        if _SYMBOL.fullmatch(self.symbol) is None:
            msg = (
                f"symbol must be 1-20 capital letters, digits, dots or dashes, got {self.symbol!r}"
            )
            raise ValueError(msg)
        if not isinstance(self.market, str):
            msg = f"market must be a str, got {type(self.market).__name__}"
            raise TypeError(msg)
        if _MARKET.fullmatch(self.market) is None:
            msg = f"market must be 2-10 capital letters, got {self.market!r}"
            raise ValueError(msg)
        require_type(self.currency, Currency, "currency")


class InvalidBarError(ValueError):
    """A price bar is inconsistent. It must never reach the cache or a strategy."""


@dataclass(frozen=True, slots=True)
class Bar:
    """One trading day of **unadjusted** prices for one instrument (spec §4.3)."""

    instrument: Instrument
    day: date
    open: Money
    high: Money
    low: Money
    close: Money
    volume: int

    def __post_init__(self) -> None:
        require_type(self.instrument, Instrument, "instrument")
        require_date(self.day, "bar day")
        where = f"{self.instrument.symbol} {self.day.isoformat()}"
        expected = self.instrument.currency
        prices = {"open": self.open, "high": self.high, "low": self.low, "close": self.close}
        for name, price in prices.items():
            require_type(price, Money, name)
            if price.currency != expected:
                msg = f"{where}: {name} is in {price.currency.code}, expected {expected.code}"
                raise InvalidBarError(msg)
            if price.amount <= 0:
                msg = f"{where}: {name} must be positive, got {price}"
                raise InvalidBarError(msg)
        if type(self.volume) is not int or self.volume < 0:
            msg = f"{where}: volume must be a non-negative int, got {self.volume!r}"
            raise InvalidBarError(msg)
        bracketed = self.low <= self.open <= self.high and self.low <= self.close <= self.high
        if not bracketed:
            msg = (
                f"{where}: low {self.low} and high {self.high} do not bracket "
                f"open {self.open} and close {self.close}"
            )
            raise InvalidBarError(msg)


@dataclass(frozen=True, slots=True)
class Split:
    """On ``ex_date``, every ``old_shares`` become ``new_shares``.

    A 5-for-1 split is ``Split(instrument, ex_date, 1, 5)``; a 1-for-5 reverse split is ``5, 1``.
    """

    instrument: Instrument
    ex_date: date
    old_shares: int
    new_shares: int

    def __post_init__(self) -> None:
        require_type(self.instrument, Instrument, "instrument")
        require_date(self.ex_date, "split ex_date")
        require_int(self.old_shares, "old_shares", minimum=1)
        require_int(self.new_shares, "new_shares", minimum=1)
        if self.old_shares == self.new_shares:
            msg = (
                f"{self.instrument.symbol} {self.ex_date.isoformat()}: turning "
                f"{self.old_shares} shares into {self.new_shares} changes nothing"
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class CashDividend:
    """A cash dividend for holders before ``ex_date``.

    ``per_share`` is in major units of the instrument's currency and may be fractional
    (Rp 12.5 a share), so it is a ``Decimal``, not ``Money``.
    """

    instrument: Instrument
    ex_date: date
    per_share: Decimal

    def __post_init__(self) -> None:
        require_type(self.instrument, Instrument, "instrument")
        require_date(self.ex_date, "dividend ex_date")
        if not isinstance(self.per_share, Decimal):
            msg = f"per_share must be a Decimal, got {type(self.per_share).__name__}"
            raise TypeError(msg)
        if not self.per_share.is_finite() or self.per_share <= 0:
            msg = f"per_share must be a positive finite Decimal, got {self.per_share}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class OtherAction:
    """Any other corporate action (a rights issue, a merger). The engine freezes the stock."""

    instrument: Instrument
    ex_date: date
    description: str

    def __post_init__(self) -> None:
        require_type(self.instrument, Instrument, "instrument")
        require_date(self.ex_date, "action ex_date")
        require_type(self.description, str, "description")
        if not self.description.strip():
            msg = (
                f"{self.instrument.symbol} {self.ex_date.isoformat()}: "
                "an other action needs a description"
            )
            raise ValueError(msg)


type CorporateAction = Split | CashDividend | OtherAction


@dataclass(frozen=True, slots=True)
class Order:
    """A request to trade ``quantity`` shares, placed on ``placed_on``."""

    instrument: Instrument
    side: Side
    quantity: int
    placed_on: date

    def __post_init__(self) -> None:
        require_type(self.instrument, Instrument, "instrument")
        require_type(self.side, Side, "side")
        require_int(self.quantity, "order quantity", minimum=1)
        require_date(self.placed_on, "placed_on")


@dataclass(frozen=True, slots=True)
class OrderAck:
    """A broker's answer to one submitted order. A rejection always says why."""

    order: Order
    accepted: bool
    reason: str = ""

    def __post_init__(self) -> None:
        require_type(self.order, Order, "order")
        require_type(self.accepted, bool, "accepted")
        require_type(self.reason, str, "reason")
        if not self.accepted and not self.reason.strip():
            msg = (
                f"a rejected {self.order.side.value} order for "
                f"{self.order.instrument.symbol} must say why"
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Costs:
    """What one trade costs on top of its gross value: broker fee, exchange levy, sell tax."""

    fee: Money
    levy: Money
    tax: Money

    def __post_init__(self) -> None:
        for name, part in (("fee", self.fee), ("levy", self.levy), ("tax", self.tax)):
            require_type(part, Money, name)
            if part.currency != self.fee.currency:
                raise CurrencyMismatchError(self.fee.currency, part.currency)
            if part.amount < 0:
                msg = f"{name} cannot be negative, got {part}"
                raise ValueError(msg)

    @classmethod
    def zero(cls, currency: Currency) -> Costs:
        nothing = Money.zero(currency)
        return cls(nothing, nothing, nothing)

    @property
    def total(self) -> Money:
        return self.fee + self.levy + self.tax


@dataclass(frozen=True, slots=True)
class Fill:
    """An order, or part of one, that traded on ``day`` at ``price``."""

    order: Order
    day: date
    quantity: int
    price: Money
    costs: Costs

    def __post_init__(self) -> None:
        require_type(self.order, Order, "order")
        require_type(self.price, Money, "price")
        require_type(self.costs, Costs, "costs")
        require_date(self.day, "fill day")
        if self.day < self.order.placed_on:
            msg = (
                f"a fill on {self.day.isoformat()} cannot precede its order placed on "
                f"{self.order.placed_on.isoformat()}"
            )
            raise ValueError(msg)
        require_int(self.quantity, "fill quantity", minimum=1)
        if self.quantity > self.order.quantity:
            msg = f"filled {self.quantity} shares but the order was for {self.order.quantity}"
            raise ValueError(msg)
        currency = self.order.instrument.currency
        if self.price.currency != currency:
            raise CurrencyMismatchError(currency, self.price.currency)
        if self.costs.fee.currency != currency:
            raise CurrencyMismatchError(currency, self.costs.fee.currency)
        if self.price.amount <= 0:
            msg = f"fill price must be positive, got {self.price}"
            raise ValueError(msg)

    @property
    def gross(self) -> Money:
        return self.price * self.quantity


@dataclass(frozen=True, slots=True)
class Position:
    """Shares held in one instrument. ``cost_basis`` is what they cost, buy costs included."""

    instrument: Instrument
    quantity: int
    cost_basis: Money

    def __post_init__(self) -> None:
        require_type(self.instrument, Instrument, "instrument")
        require_int(self.quantity, "position quantity", minimum=1)
        require_type(self.cost_basis, Money, "cost_basis")
        if self.cost_basis.currency != self.instrument.currency:
            raise CurrencyMismatchError(self.instrument.currency, self.cost_basis.currency)
        if self.cost_basis.amount < 0:
            msg = f"cost basis cannot be negative, got {self.cost_basis}"
            raise ValueError(msg)
