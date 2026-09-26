"""The simulated fill: yesterday's orders trade at today's open (core spec §5.1, M3 spec §5).

It is a pure function of the portfolio, the orders and today's prices, so a backtest can rerun a
day and get the same answer. It is not a ``Broker``: that protocol is for M5's manual broker,
where orders leave the program and fills come back.

Every fill is checked so cash never runs short. The day's stamp duty is charged once, after the
last fill, and settles with the day's trades (T+2), the way a broker nets it on the confirmation.
A buy therefore holds back the day's charge from the cash it may spend, and a sale is refused
only if even its own proceeds could not pay the day's charge.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from steadyhand.market import MarketRules
from steadyhand.money import Money, Rounding
from steadyhand.outcomes import Cut, Rejected
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import Bar, Fill, Instrument, Order, Side


def _percent(rate: Decimal) -> str:
    return f"{(rate * 100).normalize():f}%"


@dataclass(frozen=True, slots=True)
class FillSettings:
    """How optimistic the simulated fill may be. Both defaults are core spec §5.1's."""

    slippage: Decimal = Decimal("0.001")
    """Buys pay this much above the open and sales receive this much below it."""
    volume_cap: Decimal = Decimal("0.10")
    """The largest share of a day's traded volume one order may take."""

    def __post_init__(self) -> None:
        for name, rate in (("slippage", self.slippage), ("volume_cap", self.volume_cap)):
            if not isinstance(rate, Decimal) or not rate.is_finite():
                msg = f"{name} must be a finite Decimal, got {rate!r}"
                raise TypeError(msg)
        if not 0 <= self.slippage < 1:
            msg = f"slippage must be at least 0 and below 1, got {self.slippage}"
            raise ValueError(msg)
        if not 0 < self.volume_cap <= 1:
            msg = f"volume_cap must be above 0 and at most 1, got {self.volume_cap}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Opening:
    """What the market shows at today's open, for the stocks with orders.

    ``bars`` holds today's bar for each stock that has one, ``references`` the previous close
    that sets each stock's price band, and ``frozen`` each frozen stock with its reason.
    """

    day: date
    bars: Mapping[Instrument, Bar]
    references: Mapping[Instrument, Money]
    frozen: Mapping[Instrument, str]


@dataclass(frozen=True, slots=True)
class FillResult:
    """One day's fills: the new portfolio, what traded, what did not and why."""

    portfolio: Portfolio
    fills: tuple[Fill, ...]
    rejected: tuple[Rejected, ...]
    cuts: tuple[Cut, ...]
    daily_cost: Money


class SimulatedBroker:
    """Fills queued orders at the next open, after slippage, ticks, bands, volume and cash."""

    def __init__(self, rules: MarketRules, settings: FillSettings | None = None) -> None:
        self._rules = rules
        self._settings = FillSettings() if settings is None else settings

    def fill(self, portfolio: Portfolio, orders: Sequence[Order], opening: Opening) -> FillResult:
        """Fill *orders* at the open: every sell first, then every buy, each in its order."""
        session = _Session(self._rules, portfolio, opening.day)
        for order in sorted(orders, key=lambda order: order.side is Side.BUY):
            price = self._price(order, opening)
            if isinstance(price, str):
                session.reject(order, price)
                continue
            wanted = self._volume_capped(order, opening, session)
            if isinstance(wanted, str):
                session.reject(order, wanted)
            elif order.side is Side.BUY:
                session.buy(order, wanted, price)
            else:
                session.sell(order, wanted, price)
        return session.close()

    def _price(self, order: Order, opening: Opening) -> Money | str:
        instrument = order.instrument
        day = opening.day
        bar = opening.bars.get(instrument)
        if instrument in opening.frozen:
            return f"frozen: {opening.frozen[instrument]}"
        if bar is None:
            return f"no bar for {instrument.symbol} on {day.isoformat()}"
        if bar.volume == 0:
            return f"{instrument.symbol} did not trade on {day.isoformat()}"
        slippage = self._settings.slippage
        if order.side is Side.BUY:
            slipped = bar.open.times(1 + slippage, Rounding.UP)
        else:
            slipped = bar.open.times(1 - slippage, Rounding.DOWN)
        price = self._rules.round_to_tick(instrument, slipped, order.side, day)
        reference = opening.references.get(instrument)
        if reference is None:
            return f"no previous close for {instrument.symbol} to set the price band"
        low, high = self._rules.price_band(instrument, reference, day)
        if not low <= price <= high:
            return f"fill price {price} is outside the band {low} to {high}"
        return price

    def _volume_capped(self, order: Order, opening: Opening, session: _Session) -> int | str:
        cap = self._settings.volume_cap
        volume = opening.bars[order.instrument].volume
        lot = self._rules.lot_size(order.instrument, opening.day)
        allowed = int((volume * cap).to_integral_value(rounding=ROUND_FLOOR)) // lot * lot
        if allowed == 0:
            return f"{_percent(cap)} of the day's {volume:,} shares traded is less than a lot"
        if order.quantity <= allowed:
            return order.quantity
        session.cut(order, allowed, f"cut to {_percent(cap)} of the day's {volume:,} shares traded")
        return allowed


class _Session:
    """One day's fills in progress: the portfolio so far, and the day's running totals."""

    def __init__(self, rules: MarketRules, portfolio: Portfolio, day: date) -> None:
        self._rules = rules
        self._portfolio = portfolio
        self._day = day
        self._fills: list[Fill] = []
        self._rejected: list[Rejected] = []
        self._cuts: list[Cut] = []
        self._traded = Money.zero(portfolio.currency)
        self._proceeds = Money.zero(portfolio.currency)
        self._bought = False

    def reject(self, order: Order, reason: str) -> None:
        self._rejected.append(Rejected(order, reason))

    def cut(self, order: Order, quantity: int, reason: str) -> None:
        self._cuts.append(Cut(order, quantity, reason))

    def buy(self, order: Order, wanted: int, price: Money) -> None:
        """Buy the most whole lots, up to *wanted*, whose cost and the day's charge are paid."""
        available = self._portfolio.spendable_cash(self._day)
        lot = self._rules.lot_size(order.instrument, self._day)
        quantity = min(wanted, max(available.amount, 0) // (price * lot).amount * lot)
        while quantity > 0 and self._cost(price * quantity) > available:
            quantity -= lot
        if quantity == 0:
            self.reject(order, f"not enough cash: {available} can be spent")
            return
        if quantity < wanted:
            self.cut(order, quantity, f"cut to the {available} that can be spent")
        self._book(order, quantity, price)
        self._bought = True

    def sell(self, order: Order, quantity: int, price: Money) -> None:
        """Sell, unless the day's charge would exceed the cash and proceeds that could pay it."""
        gross = price * quantity
        net = gross - self._rules.costs(Side.SELL, gross, self._day).total
        daily = self._daily(self._traded + gross)
        covering = self._portfolio.spendable_cash(self._day) + self._proceeds + net
        if daily > covering:
            self.reject(
                order, f"the day's charges of {daily} exceed the {covering} that could pay them"
            )
            return
        self._book(order, quantity, price)
        self._proceeds += net

    def close(self) -> FillResult:
        """Charge the day's costs once, on everything traded, and report the day."""
        daily = self._daily(self._traded)
        portfolio = self._portfolio
        if daily.amount > 0:
            settles = self._day if self._bought else self._rules.settlement_date(self._day)
            portfolio = portfolio.charge(
                MovementKind.DAILY_COST, daily, self._day, settles_on=settles
            )
        return FillResult(
            portfolio, tuple(self._fills), tuple(self._rejected), tuple(self._cuts), daily
        )

    def _cost(self, gross: Money) -> Money:
        """A buy's cost with the day's charge on everything traded so far, this buy included."""
        buying = self._rules.costs(Side.BUY, gross, self._day).total
        return gross + buying + self._daily(self._traded + gross)

    def _book(self, order: Order, quantity: int, price: Money) -> None:
        gross = price * quantity
        fill = Fill(
            order, self._day, quantity, price, self._rules.costs(order.side, gross, self._day)
        )
        settles = self._rules.settlement_date(self._day)
        self._portfolio = self._portfolio.apply_fill(fill, settles)
        self._fills.append(fill)
        self._traded += gross

    def _daily(self, traded: Money) -> Money:
        if traded.amount == 0:
            return Money.zero(traded.currency)
        return self._rules.daily_costs(traded, self._day)
