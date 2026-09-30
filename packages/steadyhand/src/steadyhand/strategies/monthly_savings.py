"""``monthly-savings``: the starting cash invested in monthly instalments (M6 spec §5).

On its first day it fixes the instalment: the cash it may spend that day divided by
``instalments``, rounded down to a whole minor unit. On the first day it decides in each
calendar month it spends its spendable cash less a reserve for the instalments still due after
this one, split equally across the stocks buyable that day, and keeps every holding at its
current weight. It never sells. Top-ups and dividends go in with the next instalment, and after
the last one it spends all its cash each month. A month in which no stock can be bought is not
counted: the next day tries again. With ``instalments = 1`` it invests everything on its first
day, then reinvests monthly.
"""

from __future__ import annotations

from decimal import Decimal

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_int
from steadyhand.strategies.protocol import Decision, Memory
from steadyhand.view import MarketView, PortfolioView

_INSTALMENT = "instalment"
"""The memory key holding the instalment, in whole minor units."""

_DUE = "due"
"""The memory key holding how many instalments are still due."""

_MONTH = "month"
"""The memory key holding the last month it bought in, as ``YYYY-MM``."""


class MonthlySavings:
    """Invest the starting cash in equal monthly instalments, then reinvest each month."""

    def __init__(self, instalments: int) -> None:
        require_int(instalments, "instalments", minimum=1)
        self._instalments = instalments

    @property
    def name(self) -> str:
        return "monthly-savings"

    @property
    def instalments(self) -> int:
        """How many instalments a run that starts now spreads its cash over."""
        return self._instalments

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        cash = portfolio.spendable.amount
        if _INSTALMENT in memory:
            instalment, due = int(memory[_INSTALMENT]), int(memory[_DUE])
        else:
            instalment, due = cash // self._instalments, self._instalments
        bought = {_MONTH: memory[_MONTH]} if _MONTH in memory else {}
        weights = {stock: portfolio.weight(stock) for stock in portfolio.holdings}
        month = f"{view.today:%Y-%m}"
        buying = view.tradable.buyable
        if buying and bought.get(_MONTH) != month:
            reserve = (due - 1) * instalment if due > 0 else 0
            each = ratio_down(max(cash - reserve, 0) // len(buying), portfolio.value.amount)
            for stock in buying:
                weights[stock] = weights.get(stock, Decimal(0)) + each
            due, bought[_MONTH] = max(due - 1, 0), month
        return Decision(weights, {_INSTALMENT: str(instalment), _DUE: str(due), **bought})
