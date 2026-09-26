"""Sizing: turning target weights into orders of whole lots (core spec §6.2, M3 spec §6.2).

The sizer only does the arithmetic. Every limit that can drop or cut an order, cash included,
is the risk manager's, so each carries a reason in one place.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from steadyhand.market import MarketRules
from steadyhand.money import Money, Rounding
from steadyhand.types import Instrument, Order, Side
from steadyhand.view import PortfolioView


@runtime_checkable
class Sizer(Protocol):
    """Turns a strategy's target weights into orders."""

    def size(
        self,
        weights: Mapping[Instrument, Decimal],
        portfolio: PortfolioView,
        held: Mapping[Instrument, int],
        prices: Mapping[Instrument, Money],
        day: date,
    ) -> tuple[Order, ...]:
        """Orders placed on *day*: every sell first, then every buy, each by market and symbol.

        *held* is the shares of each holding and *prices* the last close of every stock that
        is weighted or held. A stock missing from *weights* is targeted at zero.
        """
        ...


class CompoundingSizer:
    """Sizes from the portfolio's current value, so gains and dividends grow later orders.

    Each stock's target is its weight times the value (all cash plus holdings at the last
    close). The difference from what is held becomes whole lots at the last close, always
    rounded towards zero, so a target within a lot of the holding places no order.
    """

    def __init__(self, rules: MarketRules) -> None:
        self._rules = rules

    def size(
        self,
        weights: Mapping[Instrument, Decimal],
        portfolio: PortfolioView,
        held: Mapping[Instrument, int],
        prices: Mapping[Instrument, Money],
        day: date,
    ) -> tuple[Order, ...]:
        sells: list[Order] = []
        buys: list[Order] = []
        for instrument in sorted(set(weights) | set(held), key=_by_symbol):
            price = prices.get(instrument)
            if price is None:
                msg = f"no price for {instrument.symbol} on {day.isoformat()} to size it with"
                raise LookupError(msg)
            weight = weights.get(instrument, Decimal(0))
            target = portfolio.value.times(weight, Rounding.DOWN)
            current = portfolio.holdings.get(instrument, Money.zero(portfolio.value.currency))
            lot = self._rules.lot_size(instrument, day)
            lots = abs((target - current).amount) // (price * lot).amount
            if target < current:
                quantity = min(lots * lot, held.get(instrument, 0) // lot * lot)
                if quantity:
                    sells.append(Order(instrument, Side.SELL, quantity, day))
            elif lots:
                buys.append(Order(instrument, Side.BUY, lots * lot, day))
        return (*sells, *buys)


def _by_symbol(instrument: Instrument) -> tuple[str, str]:
    return (instrument.market, instrument.symbol)
