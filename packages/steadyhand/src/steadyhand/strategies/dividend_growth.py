"""``dividend-growth``: the stocks that paid a dividend every year and grew it (M6 spec §6).

It reviews on the first day it decides in each calendar year, which is also a run's first day.
A stock passes in year Y when it is in the universe, its dividend history is complete, it paid a
cash dividend in every calendar year from Y - growth_years - 1 to Y - 1 (by ex-date, restated in
today's shares), and its total for Y - 1 is at least its total for Y - growth_years - 1. The
passers it can buy, and those it holds, are its candidates. Up to ``max_stocks`` are held, in
equal parts of 1 / max(``min_stocks``, number held); with more candidates than that it picks
them one at a time to spread the months they pay in, then by trailing yield, then by market and
symbol. Everything else is sold. Fewer than ``min_stocks`` leaves the rest in cash, with a note.
Between reviews it keeps its holdings and puts new cash into the stocks it picked, never above
the review's target.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_int
from steadyhand.notes import STRATEGY_TOO_FEW_QUALIFIED, Note
from steadyhand.strategies._sets import read_set, write_set
from steadyhand.strategies.protocol import Decision, Memory
from steadyhand.types import Instrument
from steadyhand.view import MarketView, PortfolioView

_SET_KEY = "set"
"""The memory key holding the stocks it picked, written as ``buy-and-hold`` writes its set."""

_YEAR_KEY = "year"
"""The memory key holding the calendar year it last reviewed."""

_TRAILING_DAYS = 365
"""The window of the trailing yield that breaks a tie: the dividends of the last 365 days."""


class DividendGrowthStrategy:
    """Hold the stocks whose dividends were paid every year and grew, spread across pay months."""

    def __init__(self, min_stocks: int, max_stocks: int, growth_years: int) -> None:
        require_int(min_stocks, "min_stocks", minimum=1)
        require_int(max_stocks, "max_stocks", minimum=1)
        require_int(growth_years, "growth_years", minimum=1)
        if max_stocks < min_stocks:
            msg = f"max_stocks must be at least min_stocks ({min_stocks}), got {max_stocks}"
            raise ValueError(msg)
        self._min = min_stocks
        self._max = max_stocks
        self._growth_years = growth_years

    @property
    def name(self) -> str:
        return "dividend-growth"

    @property
    def min_stocks(self) -> int:
        """Below this many picked stocks, the rest of the money is held as cash."""
        return self._min

    @property
    def max_stocks(self) -> int:
        """The most stocks it holds."""
        return self._max

    @property
    def growth_years(self) -> int:
        """The years over which a stock's dividends must have grown."""
        return self._growth_years

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        if memory.get(_YEAR_KEY) != str(view.today.year):
            return self._review(view, portfolio)
        return self._between(view, portfolio, memory)

    def passes(self, view: MarketView, stock: Instrument) -> bool:
        """Whether *stock* passes the dividend test in today's year (M6 spec §6)."""
        if stock not in view.tradable.members or not view.history_complete(stock):
            return False
        year = view.today.year
        first = year - self._growth_years - 1
        totals: defaultdict[int, Decimal] = defaultdict(Decimal)
        for dividend in view.dividends(stock):
            totals[dividend.ex_date.year] += dividend.per_share
        if any(totals[paid] == 0 for paid in range(first, year)):
            return False
        return totals[year - 1] >= totals[first]

    def _review(self, view: MarketView, portfolio: PortfolioView) -> Decision:
        reachable = view.tradable.buyable | frozenset(portfolio.holdings)
        candidates = [
            stock
            for stock in sorted(reachable, key=lambda i: (i.market, i.symbol))
            if self.passes(view, stock)
        ]
        picked = candidates if len(candidates) <= self._max else self._spread(view, candidates)
        target = ratio_down(1, max(self._min, len(picked)))
        notes: tuple[Note, ...] = ()
        if len(picked) < self._min:
            notes = (Note(STRATEGY_TOO_FEW_QUALIFIED, _too_few(len(picked))),)
        memory = {_SET_KEY: write_set(picked), _YEAR_KEY: str(view.today.year)}
        return Decision(dict.fromkeys(picked, target), memory, notes)

    def _spread(self, view: MarketView, candidates: Sequence[Instrument]) -> list[Instrument]:
        """``max_stocks`` of *candidates*, picked one at a time: each time the one whose least
        crowded pay month has the fewest stocks already picked, then the higher trailing yield,
        then by market and symbol."""
        last_year = view.today.year - 1
        months = {
            stock: frozenset(
                view.pay_date(dividend.ex_date).month
                for dividend in view.dividends(stock)
                if dividend.ex_date.year == last_year
            )
            for stock in candidates
        }
        yields = {stock: _trailing_yield(view, stock) for stock in candidates}
        crowding: defaultdict[int, int] = defaultdict(int)
        picked: list[Instrument] = []
        left = list(candidates)
        for _ in range(self._max):
            best = min(
                left,
                key=lambda stock: (
                    min(crowding[month] for month in months[stock]),
                    -yields[stock],
                    stock.market,
                    stock.symbol,
                ),
            )
            picked.append(best)
            left.remove(best)
            for month in months[best]:
                crowding[month] += 1
        return picked

    def _between(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        chosen = read_set(memory[_SET_KEY], portfolio.value.currency)
        target = ratio_down(1, max(self._min, len(chosen)))
        weights = {stock: portfolio.weight(stock) for stock in portfolio.holdings}
        buying = chosen & view.tradable.buyable
        if buying:
            each = ratio_down(portfolio.spendable.amount // len(buying), portfolio.value.amount)
            for stock in buying:
                held = weights.get(stock, Decimal(0))
                weights[stock] = held + min(each, max(target - held, Decimal(0)))
        return Decision(weights, dict(memory))


def _trailing_yield(view: MarketView, stock: Instrument) -> Decimal:
    """The stock's dividends of the last 365 days, restated in today's shares, over its last
    close."""
    since = view.today - timedelta(days=_TRAILING_DAYS)
    paid = sum(
        (dividend.per_share for dividend in view.dividends(stock) if dividend.ex_date > since),
        Decimal(0),
    )
    close = view.last_close(stock)
    return paid / close.amount if close is not None and close.amount else Decimal(0)


def _too_few(count: int) -> str:
    if count == 0:
        return "No stock passed the dividend test; everything is held as cash until one does."
    stocks = "stock" if count == 1 else "stocks"
    return (
        f"Only {count} {stocks} passed the dividend test; the rest is held as cash until more do."
    )
