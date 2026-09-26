"""A ten-year backtest over 45 stocks finishes in under 30 seconds (core spec §10.4, M3 §9).

The prices are synthetic, generated here from a fixed seed with integer arithmetic only: ten
years of real fixtures would bloat the repository. IDX's rule data does not reach ten years
ahead, so the run uses ``_PlainRules``, a small market written for this test, which also shows
the engine running a market other than IDX. The strategy rebalances to equal weights every day,
so the strategy's run and the baseline's both trade, value and size every day.
"""

import time
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from decimal import Decimal

import pytest

from steadyhand import (
    IDR,
    BacktestSettings,
    Bar,
    CashDividend,
    CorporateAction,
    Costs,
    Currency,
    Decision,
    EngineSettings,
    Instrument,
    Market,
    MarketView,
    Memory,
    Money,
    PortfolioView,
    Rounding,
    Side,
    UnsupportedDateError,
    backtest,
)

SEED = 20260926
STOCKS = 45
START, END = date(2016, 1, 4), date(2025, 12, 31)
BUDGET_SECONDS = 30


class _PlainRules:
    """A market open on weekdays, with one-rupiah ticks, lots of 100 and flat-rate costs."""

    @property
    def currency(self) -> Currency:
        return IDR

    @property
    def verified_from(self) -> date:
        return date(2000, 1, 3)

    def require_supported(self, day: date) -> None:
        if day < self.verified_from:
            msg = f"the plain market opens on {self.verified_from.isoformat()}"
            raise UnsupportedDateError(msg)

    def lot_size(self, instrument: Instrument, on: date) -> int:
        return 100

    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money:
        return price

    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]:
        return reference.times(Decimal("0.65"), Rounding.UP), reference.times(
            Decimal("1.35"), Rounding.DOWN
        )

    def costs(self, side: Side, gross: Money, on: date) -> Costs:
        fee = gross.times(Decimal("0.0015"), Rounding.UP)
        tax = gross.times(Decimal("0.001"), Rounding.UP) if side is Side.SELL else Money.zero(IDR)
        return Costs(fee, Money.zero(IDR), tax)

    def daily_costs(self, traded: Money, on: date) -> Money:
        return Money(10_000 if traded.amount else 0, IDR)

    def settlement_date(self, trade_date: date) -> date:
        day, left = trade_date, 2
        while left:
            day += timedelta(days=1)
            left -= self.is_trading_day(day)
        return day

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        return gross.times(Decimal("0.1"), Rounding.UP)

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5


class _Lcg:
    """A 64-bit linear congruential generator (Knuth's MMIX constants): integers only, and the
    same sequence on every Python version, which ``random`` does not promise."""

    def __init__(self, seed: int) -> None:
        self._state = seed

    def randint(self, low: int, high: int) -> int:
        self._state = (self._state * 6364136223846793005 + 1442695040888963407) % 2**64
        return low + (self._state >> 33) % (high - low + 1)


class _Synthetic:
    """Ten years of daily bars and one June dividend a year for each stock, from ``SEED``."""

    def __init__(self) -> None:
        rng = _Lcg(SEED)
        self.stocks = [Instrument(f"S{n:03d}", "PLAIN", IDR) for n in range(STOCKS)]
        self._bars: dict[Instrument, list[Bar]] = {}
        self._actions: dict[Instrument, list[CorporateAction]] = {}
        days = [START + timedelta(days=n) for n in range((END - START).days + 1)]
        trading = [day for day in days if day.weekday() < 5]
        for stock in self.stocks:
            close = rng.randint(1_000, 20_000)
            bars: list[Bar] = []
            actions: list[CorporateAction] = []
            for day in trading:
                opening = close * (1_000 + rng.randint(-10, 10)) // 1_000
                close = max(50, opening * (1_000 + rng.randint(-20, 21)) // 1_000)
                high, low = max(opening, close), min(opening, close)
                high_, low_ = Money(high, IDR), Money(low, IDR)
                bars.append(
                    Bar(stock, day, Money(opening, IDR), high_, low_, Money(close, IDR), 10**8)
                )
                if day.month == 6 and day.day == 15:
                    actions.append(CashDividend(stock, day, Decimal(close // 50)))
            self._bars[stock] = bars
            self._actions[stock] = actions

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        return [bar for bar in self._bars[instrument] if start <= bar.day <= end]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return [a for a in self._actions[instrument] if start <= a.ex_date <= end]


class _All:
    """Every synthetic stock, every day, with nothing excluded and no gaps."""

    def __init__(self, stocks: Sequence[Instrument]) -> None:
        self._stocks = frozenset(stocks)

    def members_on(self, day: date) -> frozenset[Instrument]:
        return self._stocks

    def excluded_on(self, day: date) -> Mapping[Instrument, str]:
        return {}

    def first_day(self) -> date:
        return START

    def survivorship_warnings(self, start: date, end: date) -> Sequence[str]:
        return ()


class _EqualWeight:
    """Every buyable stock at the same weight, rebalanced every day."""

    @property
    def name(self) -> str:
        return "equal-weight"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        buyable = view.tradable.buyable
        if not buyable:
            return Decision({})
        each = Decimal(1) / len(buyable)
        return Decision(
            {stock: each.quantize(Decimal("0.0001"), Rounding.DOWN.value) for stock in buyable}
        )


@pytest.mark.perf
def test_ten_years_of_45_stocks_run_inside_the_budget() -> None:
    source = _Synthetic()
    settings = BacktestSettings(
        Money(1_000_000_000, IDR), EngineSettings(monthly_contribution=Money(10_000_000, IDR))
    )
    market = Market(_All(source.stocks), source, _PlainRules())
    began = time.perf_counter()
    result = backtest(_EqualWeight(), market, START, END, settings)
    seconds = time.perf_counter() - began
    assert result.baseline is not None
    runs = (result.run, result.baseline)
    # The run did the work it is timed on: every weekday, trades and dividends in both runs.
    weekdays = sum((START + timedelta(days=n)).weekday() < 5 for n in range((END - START).days + 1))
    assert [len(run.reports) for run in runs] == [weekdays, weekdays]
    assert all(run.halt is None for run in runs)
    assert all(sum(len(r.fills) for r in run.reports) > 45 for run in runs)
    assert all(run.metrics.dividends.gross.amount > 0 for run in runs)
    assert seconds < BUDGET_SECONDS, f"took {seconds:.1f} s, over the {BUDGET_SECONDS} s budget"
