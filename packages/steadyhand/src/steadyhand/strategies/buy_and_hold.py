"""``buy-and-hold``: the baseline every other strategy is measured against (core spec §8).

On its first day it fixes its set: the stocks buyable that day. It never sells. Each day it keeps
every holding at its current weight, so nothing is traded against it, and it splits the cash it
may spend equally across the stocks in its set that are buyable today. Dividends and top-ups are
reinvested the same way. A stock that leaves the universe stays held (M3 spec §6.6).
"""

from __future__ import annotations

from decimal import Decimal

from steadyhand._ratio import ratio_down
from steadyhand.strategies._sets import read_set, write_set
from steadyhand.strategies.protocol import Decision, Memory
from steadyhand.view import MarketView, PortfolioView

_SET_KEY = "set"
"""The memory key holding the set, written as ``MARKET:SYMBOL`` separated by spaces."""


class BuyAndHold:
    """Buy the day-one universe in equal parts and hold it."""

    @property
    def name(self) -> str:
        return "buy-and-hold"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        currency = portfolio.value.currency
        chosen = (
            read_set(memory[_SET_KEY], currency) if _SET_KEY in memory else view.tradable.buyable
        )
        weights = {instrument: portfolio.weight(instrument) for instrument in portfolio.holdings}
        buying = chosen & view.tradable.buyable
        if buying:
            each = ratio_down(portfolio.spendable.amount // len(buying), portfolio.value.amount)
            for instrument in buying:
                weights[instrument] = weights.get(instrument, Decimal(0)) + each
        return Decision(weights, {_SET_KEY: write_set(chosen)})
