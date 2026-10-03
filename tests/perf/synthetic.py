"""A synthetic market for the performance tests: ten years of prices and dividends for 45
stocks, generated from a fixed seed with integer arithmetic only, under ``PlainRules``, a small
market that is not IDX. Ten years of real fixtures would bloat the repository, and IDX's rule
data does not reach ten years ahead. ``EqualWeight`` rebalances every day, so it trades,
values and sizes every day."""

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from decimal import Decimal

from steadyhand import (
    IDR,
    Bar,
    CashDividend,
    CorporateAction,
    Costs,
    Currency,
    Decision,
    Instrument,
    MarketView,
    Memory,
    Money,
    Note,
    PortfolioView,
    Rounding,
    Side,
    UnsupportedDateError,
)

SEED = 20260926
STOCKS = 45
START, END = date(2016, 1, 4), date(2025, 12, 31)


class PlainRules:
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

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        return gross.times(Decimal("0.1"), Rounding.UP)

    def reinvestment_deadline(self, ex_date: date) -> date | None:
        return None

    def protection_end(self, purchase_day: date) -> date:
        return purchase_day

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5


class Lcg:
    """A 64-bit linear congruential generator (Knuth's MMIX constants): integers only, and the
    same sequence on every Python version, which ``random`` does not promise."""

    def __init__(self, seed: int) -> None:
        self._state = seed

    def randint(self, low: int, high: int) -> int:
        self._state = (self._state * 6364136223846793005 + 1442695040888963407) % 2**64
        return low + (self._state >> 33) % (high - low + 1)


class Synthetic:
    """Ten years of daily bars and a dividend each year on the first weekday from 15 June, for
    each stock, from ``SEED``. Every year pays, so the last year gives a run-rate to project."""

    def __init__(self) -> None:
        rng = Lcg(SEED)
        self.stocks = [Instrument(f"S{n:03d}", "PLAIN", IDR) for n in range(STOCKS)]
        self._bars: dict[Instrument, list[Bar]] = {}
        self._actions: dict[Instrument, list[CorporateAction]] = {}
        days = [START + timedelta(days=n) for n in range((END - START).days + 1)]
        trading = [day for day in days if day.weekday() < 5]
        for stock in self.stocks:
            close = rng.randint(1_000, 20_000)
            bars: list[Bar] = []
            actions: list[CorporateAction] = []
            paid: set[int] = set()
            for day in trading:
                opening = close * (1_000 + rng.randint(-10, 10)) // 1_000
                close = max(50, opening * (1_000 + rng.randint(-20, 21)) // 1_000)
                high, low = max(opening, close), min(opening, close)
                high_, low_ = Money(high, IDR), Money(low, IDR)
                bars.append(
                    Bar(stock, day, Money(opening, IDR), high_, low_, Money(close, IDR), 10**8)
                )
                if (day.month, day.day) >= (6, 15) and day.year not in paid:
                    paid.add(day.year)
                    actions.append(CashDividend(stock, day, Decimal(close // 50)))
            self._bars[stock] = bars
            self._actions[stock] = actions

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        return [bar for bar in self._bars[instrument] if start <= bar.day <= end]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return [a for a in self._actions[instrument] if start <= a.ex_date <= end]

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> Sequence[Note]:
        return ()


class All:
    """Every synthetic stock, every day, with nothing excluded and no gaps."""

    def __init__(self, stocks: Sequence[Instrument]) -> None:
        self._stocks = frozenset(stocks)

    def members_on(self, day: date) -> frozenset[Instrument]:
        return self._stocks

    def excluded_on(self, day: date) -> Mapping[Instrument, str]:
        return {}

    def first_day(self) -> date:
        return START

    def survivorship_warnings(self, start: date, end: date) -> Sequence[Note]:
        return ()


class EqualWeight:
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
