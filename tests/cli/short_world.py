"""A short made-up market for the unit stand-ins of the CLI's long real runs (#292).

The golden window's real runs (a year of five recorded stocks, BBRI's whole history restored)
moved to the integration suite: each was over the unit limit of 0.07 s of its own CPU. Their
stand-ins run the same commands through the same real ``YahooDataSource`` and engine over nineteen
trading days of three made-up stocks, which meet what the golden window was chosen for: XAAA pays
a dividend inside the window, XBBB splits inside it, and XCCC's prices carry an adjustment Yahoo
does not report, which steadyhand proves from them and restores, as it does BBRI's. The codes are
made up (``X`` then three letters), as are the prices: no real stock's data is written here.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from functools import cache, partial
from itertools import product
from pathlib import Path

from cli_world import Cli
from record_golden import summary, write_summary

from steadyhand import (
    IDR,
    STRATEGIES,
    BacktestResult,
    BacktestSettings,
    DataSource,
    EngineSettings,
    IncomeGoal,
    Market,
    Money,
    RiskLimits,
    backtest,
)
from steadyhand_idx import BarCache, CachedDataSource
from steadyhand_idx.cli import SourceFactory
from steadyhand_idx.paper import days_to_run
from steadyhand_idx.rules import IdxMarketRules
from steadyhand_idx.universe import Lq45Membership, Lq45Record, Lq45Universe
from steadyhand_idx.yahoo import YahooDataSource, YahooHistory, YahooRow

START, END = date(2021, 12, 15), date(2022, 1, 11)
"""Nineteen trading days across the turn of the year, so ``dividend-growth`` reviews again on
3 January 2022, its first trading day."""
DATA_END = date(2022, 1, 18)
"""The made-up data runs a week past the window."""
RECORDED = date(2022, 1, 20)
DIVIDEND = date(2021, 12, 17)
"""XAAA's ex-date in the window, its 2021 dividend of Rp25 a share, paid on 7 January 2022."""
SPLIT = date(2021, 12, 22)
"""XBBB's 1-for-2 split: every share becomes two, at half the price."""
STOCKS = ("XAAA", "XBBB", "XCCC")
PLACEHOLDERS = tuple("Z" + "".join(letters) for letters in product("ABCDEFGHIJ", repeat=3))[:42]
"""Made-up codes that fill the LQ45 file to 45, every one excluded."""
OPENING = {"XAAA": 1_000, "XBBB": 4_000, "XCCC": 7_000}
STEP = {"XAAA": 5, "XBBB": 20, "XCCC": 25}
"""How far each stock's true prices move, a whole number of its ticks: up two steps a day, then
down one. XBBB's steps halve with its price at the split."""
VOLUME = 5_000_000
"""Shares traded a day: enough that no order waits for volume."""
LOOK_BACK = {
    "XAAA": ((date(2018, 12, 17), 30), (date(2019, 12, 17), 40), (date(2020, 12, 17), 45)),
    "XBBB": (
        (date(2018, 12, 17), 150),
        (date(2019, 12, 17), 100),
        (date(2020, 12, 17), 120),
        (date(2021, 12, 1), 160),
    ),
    "XCCC": (
        (date(2018, 12, 17), 110),
        (date(2019, 12, 17), 132),
        (date(2020, 12, 17), 154),
        (date(2021, 12, 1), 176),
    ),
}
"""Each stock's true dividends a share before the window, on rows of their own at its opening
price. ``dividend-growth`` with a two-year test passes a stock whose dividend was paid in each of
the three years before and whose last is at least its first: in 2021 (2018 to 2020) XAAA and XCCC
pass and XBBB does not; on 3 January 2022 (2019 to 2021, XAAA's 2021 dividend being its Rp25 in
the window) XBBB and XCCC pass and XAAA does not."""
ADJUSTMENT = Decimal("1.1")
"""What Yahoo divided XCCC's prices by without reporting it: steadyhand restores them."""


@cache
def trading_days() -> tuple[date, ...]:
    return days_to_run(START - timedelta(days=1), DATA_END, IdxMarketRules())


def _yahoo(price: int, stock: str, day: date) -> Decimal:
    """*price*, true to the tick grid, as Yahoo shows it: split-adjusted for XBBB before its split,
    divided by ``ADJUSTMENT`` for XCCC and given as the Decimal of its float."""
    if stock == "XBBB" and day < SPLIT:
        return Decimal(price) / 2
    if stock == "XCCC":
        return Decimal(repr(float(Decimal(price) / ADJUSTMENT)))
    return Decimal(price)


@cache
def history(ticker: str) -> YahooHistory:
    """The made-up stock *ticker* as Yahoo would give it, a row for every trading day."""
    stock = ticker.removesuffix(".JK")
    rows, close = [], OPENING[stock]
    for day, paid in LOOK_BACK[stock]:
        price, dividend = (_yahoo(amount, stock, day) for amount in (OPENING[stock], paid))
        volume = VOLUME * (2 if stock == "XBBB" else 1)
        rows.append(YahooRow(day, price, price, price, price, volume, dividend))
    for n, day in enumerate(trading_days()):
        halved = stock == "XBBB" and day >= SPLIT
        step = STEP[stock] // (2 if halved else 1)
        close += step * (2 if n % 2 == 0 else -1)
        true = close // 2 if halved else close
        prices = (true - step, true + step, true - 2 * step, true)
        opening, high, low, last = (_yahoo(price, stock, day) for price in prices)
        volume = VOLUME * (2 if stock == "XBBB" and day < SPLIT else 1)
        dividend = Decimal(25) if stock == "XAAA" and day == DIVIDEND else Decimal(0)
        rows.append(YahooRow(day, opening, high, low, last, volume, dividend))
    splits = ((SPLIT, Decimal(2)),) if stock == "XBBB" else ()
    return YahooHistory(ticker, tuple(rows), splits)


def download(ticker: str, start: date, end: date) -> YahooHistory:
    """Yahoo's answer for a made-up stock over any range: its rows inside it, and no rows for a
    placeholder code."""
    if ticker.removesuffix(".JK") not in STOCKS:
        return YahooHistory(ticker, (), ())
    whole = history(ticker)
    return YahooHistory(
        ticker, tuple(row for row in whole.rows if start <= row.day <= end), whole.splits
    )


def yahoo() -> YahooDataSource:
    """The real ``YahooDataSource`` on the made-up answers, waiting for nothing."""
    return YahooDataSource(download=download, sleep=lambda _: None, today=lambda: RECORDED)


@contextmanager
def uncached(folder: Path) -> Iterator[DataSource]:
    """The made-up answers through the real ``YahooDataSource`` alone. The bar cache fills a
    table for each of the 45 members, about 30 ms of CPU (measured 2026-10-13), so a stand-in that
    is not about the cache reads without it; the cache is proved in ``tests/idx/test_cache.py``."""
    del folder
    yield yahoo()


@contextmanager
def cached(folder: Path) -> Iterator[DataSource]:
    """The made-up answers through the real ``YahooDataSource`` and the bar cache in *folder*."""
    with BarCache(folder / "cache.sqlite") as cache:
        yield CachedDataSource(yahoo(), cache, today=lambda: RECORDED)


VALUES = {"instalments": 12, "min_stocks": 2, "max_stocks": 2, "growth_years": 2}
"""What each strategy is made from: ``GROWTH_CONFIG``'s values, as ``record_golden.VALUES``."""


def universe() -> Lq45Universe:
    """The three made-up stocks as the whole universe, for a library run beside a command's."""
    record = Lq45Record(START, START, "steadyhand test: made-up codes", "review", frozenset(STOCKS))
    return Lq45Universe(Lq45Membership([record]))


def settings(*, income: bool = True) -> BacktestSettings:
    """``SHORT_CONFIG``'s: Rp100,000,000, 35% a stock, so that three stocks can be fully invested,
    and a goal of Rp2,000 a month, which the window's dividends meet, so its projection stops at
    once (a goal it never met would simulate 600 months three times, about 30 ms of CPU)."""
    limits = RiskLimits(max_weight=Decimal("0.35"))
    goal = IncomeGoal(Money(2_000, IDR)) if income else None
    return BacktestSettings(Money(100_000_000, IDR), EngineSettings(limits=limits), goal)


def library_run(
    strategy: str = "buy-and-hold",
    *,
    end: date = END,
    cash: int = 100_000_000,
    broker_fees: str | None = None,
    exemption: bool = False,
) -> BacktestResult:
    """The library's backtest from the window's start to *end*, with ``SHORT_CONFIG``'s settings
    unless told, and each strategy made from ``VALUES``."""
    entry = STRATEGIES[strategy]
    chosen = replace(
        settings(), capital=Money(cash, IDR), lookback_years=entry.lookback_years(VALUES)
    )
    if exemption:
        engine = replace(chosen.engine, dividend_reinvestment_exemption=True)
        chosen = replace(chosen, engine=engine)
    rules = IdxMarketRules() if broker_fees is None else IdxMarketRules(broker_fees=broker_fees)
    return backtest(entry(VALUES), Market(universe(), yahoo(), rules), START, end, chosen)


def write_universe(home: Path) -> None:
    """An LQ45 file of the three made-up stocks and 42 placeholders, which are excluded."""
    members = ", ".join(f'"{code}"' for code in (*STOCKS, *PLACEHOLDERS))
    (home / "lq45_members.toml").write_text(
        f"schema = 1\n\n[[record]]\neffective = {START}\nannounced = {START}\n"
        'source = "steadyhand CLI test: made-up codes, not an LQ45 list"\n'
        f'kind = "review"\nmembers = [{members}]\n',
        encoding="utf-8",
    )
    rows = "".join(f"{code},{START},,a made-up code with no data\n" for code in PLACEHOLDERS)
    (home / "exclusions.csv").write_text(f"symbol,from,to,reason\n{rows}", encoding="utf-8")


SHORT_CONFIG = """[account]
starting_cash_idr = 100_000_000

[goal]
monthly_income_target_idr = 2_000

[strategy]
name = "buy-and-hold"

[risk]
max_weight = "0.35"

[consent]
disclaimer_accepted = 2026-09-27
"""


GROWTH_CONFIG = SHORT_CONFIG.replace(
    'name = "buy-and-hold"',
    'name = "dividend-growth"\nmin_stocks = 2\nmax_stocks = 2\ngrowth_years = 2',
)

WINDOW = ("--from", START.isoformat(), "--to", END.isoformat())
WEEK_END = date(2021, 12, 21)
WEEK = ("--from", START.isoformat(), "--to", WEEK_END.isoformat())
"""The window's first five trading days, for a test of how a command is wired, not of what a
run meets: each day costs the engine about a millisecond of CPU."""


def short_cli(home: Path, config: str = SHORT_CONFIG, source: SourceFactory = uncached) -> Cli:
    """``steadyhand-idx`` over the made-up market, with *config* and the operator's files."""
    home.mkdir(parents=True)
    (home / "steadyhand.toml").write_text(config, encoding="utf-8")
    write_universe(home)
    return Cli(home, source)


RESTORED = (
    "XCCC: Yahoo's prices from 2018-12-17 to 2022-01-18 carry an adjustment Yahoo does not "
    "report, so steadyhand restored them: every price and dividend in that span is multiplied "
    "by 1.100000, proven by 112 prices that fit the IDX tick grid at that factor and at no other."
)
"""The window's one warning: XCCC's restoration, as BBRI's is the golden window's."""


GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "made-up"
RUNS: dict[str, Callable[[], BacktestResult]] = {
    "buy-and-hold": library_run,
    "dividend-growth": partial(library_run, "dividend-growth"),
    "exemption-on": partial(library_run, exemption=True),
}
"""The made-up window's pinned runs, the stand-ins of the golden runs: buy-and-hold, dividend-growth
with its look-back and its review on 3 January 2022, and buy-and-hold with the reinvestment
exemption switched on."""


def golden(name: str) -> Path:
    """Where *name*'s pinned summary is stored."""
    return GOLDEN / f"{name}_{START.isoformat()}_{END.isoformat()}.json"


def record(name: str, path: Path | None = None) -> Path:
    """Run *name* and write its summary as ``record_golden`` writes the golden files: to its
    pinned file unless *path*. After a change that moves these numbers on purpose, re-record with
    ``PYTHONPATH=tests/cli:scripts uv run python -c "import short_world as w; [w.record(n) for n
    in w.RUNS]"`` and review the diff."""
    return write_summary(summary(RUNS[name]()), golden(name) if path is None else path)
