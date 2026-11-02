"""New cash shared by water-filling, up to a target weight per stock (#486).

The stocks with the least room below the target are filled first. Each is offered an equal part
of the cash still unspent, rounded down to the rupiah, and takes no more than its room, so what
one stock cannot take goes to the rest, and cash stays idle only when every stock is at its target.
A stock filled to its room uses the rupiah that room needs, rounded up, so the cash offered to
the rest never counts a rupiah twice and the weights never sum above what may be spent.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from decimal import ROUND_CEILING, Decimal, localcontext

from steadyhand._ratio import ratio_down
from steadyhand.types import Instrument
from steadyhand.view import PortfolioView


def _rupiah_up(weight: Decimal, value: int) -> int:
    """The whole rupiah *weight* of a portfolio worth *value* needs, rounded up."""
    with localcontext() as context:
        context.rounding = ROUND_CEILING
        return math.ceil(weight * value)


def top_up(
    portfolio: PortfolioView, buying: Iterable[Instrument], target: Decimal
) -> dict[Instrument, Decimal]:
    """Each stock in *buying* at its weight after *portfolio*'s spendable cash is shared out."""
    held = {stock: portfolio.weight(stock) for stock in buying}
    room = {stock: max(target - weight, Decimal(0)) for stock, weight in held.items()}
    order = sorted(held, key=lambda stock: (room[stock], stock.market, stock.symbol))
    value = portfolio.value.amount
    unspent = portfolio.spendable.amount
    weights: dict[Instrument, Decimal] = {}
    for place, stock in enumerate(order):
        offered = unspent // (len(order) - place)
        share = ratio_down(offered, value)
        if share <= room[stock]:
            weights[stock] = held[stock] + share
            unspent -= offered
        else:
            weights[stock] = held[stock] + room[stock]
            unspent -= _rupiah_up(room[stock], value)
    return weights
