"""``YahooDataSource``: unadjusted IDX prices from Yahoo Finance's ``.JK`` tickers (spec §9.2).

Yahoo's "unadjusted" history is not unadjusted (docs/research/t-hist.md §6). Even with
``auto_adjust=False`` every price before a split is divided by the split ratio, and every
dividend with it. Splits are reported, so their adjustment is reversed exactly here, using the
stock's full split history (a split after the requested range still adjusts the prices in it).

Some adjustments are not reported. A rights issue, for one, scales every earlier price by a
factor nobody publishes, so after reversing the reported splits those prices are no longer whole
rupiah. When a range has such a price, the source reads the stock's whole history once, finds the
runs of those days, and restores every price and dividend of each run whose factor the tick grid
proves (``steadyhand_idx.factor``, #160). A day in no proven run still raises
``UnrecoverablePricesError`` naming it (fail closed, spec §9.2), and a dividend in an unproven run
is refused, because its amount is known to be wrong.

Trading days come from ``holidays.toml``, never from which days have bars. A flat bar with no
volume on a holiday is a Yahoo placeholder and is dropped. A bar with trading on a holiday
contradicts the calendar, and is refused.

Corporate actions need no calendar: a dividend is restated through the reported splits, and
through a proven run's factor. So ``corporate_actions`` reads only splits and dividends, and a
range the holiday calendar does not cover still gives its actions. That is what a strategy's
look-back reads (M6 spec §4.3).
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, cast

from steadyhand import (
    IDR,
    Bar,
    CashDividend,
    CorporateAction,
    DataUnavailableError,
    Instrument,
    InvalidBarError,
    Money,
    Split,
    UnavailableDaysError,
)
from steadyhand_idx.cache import jakarta_today
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.factor import (
    GRID_START,
    PriceRow,
    Restoration,
    Run,
    find_runs,
    restore_dividend,
    restore_price,
)

if TYPE_CHECKING:
    import pandas as pd

SUFFIX = ".JK"
PRICE_COLUMNS = ("Open", "High", "Low", "Close")
REQUIRED_COLUMNS = (*PRICE_COLUMNS, "Volume", "Dividends")
YAHOO_TIMEZONE = "Asia/Jakarta"
# A reversed price counts as whole rupiah when it is this close to one. Yahoo's floats carry noise
# far below a rupiah; an unreported adjustment leaves a visible fraction (BBRI's close on
# 7 Sep 2021 reads 3,554.484130859375 in Yahoo's recorded response).
WHOLE_RUPIAH_TOLERANCE = Decimal("0.0001")
_SPLIT_DENOMINATOR_LIMIT = 1000


class UnrecoverablePricesError(UnavailableDaysError):
    """Yahoo's prices for these days carry an adjustment it does not report, and no factor could
    be proven for them, so the traded prices cannot be worked out. ``days`` lists every such day
    in the requested range."""

    def __init__(self, ticker: str, days: Sequence[date]) -> None:
        found = tuple(days)
        super().__init__(
            f"{ticker}: Yahoo's prices for {len(found)} day(s) from "
            f"{found[0].isoformat()} to {found[-1].isoformat()} carry an adjustment it "
            "does not report as a split (for example a rights issue), so the prices traded on "
            "those days cannot be recovered",
            found,
        )


@dataclass(frozen=True, slots=True)
class YahooRow:
    """One day as Yahoo gives it, split-adjusted. Numbers are Decimals of Yahoo's own floats."""

    day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    dividend: Decimal


@dataclass(frozen=True, slots=True)
class YahooHistory:
    """What one request returns: the rows in range and the stock's whole split history.

    Each split is (ex date, new shares per old share), so a 5-for-1 split is 5.
    """

    ticker: str
    rows: tuple[YahooRow, ...]
    splits: tuple[tuple[date, Decimal], ...]


type Downloader = Callable[[str, date, date], YahooHistory]


def ticker_for(instrument: Instrument) -> str:
    if instrument.market != "IDX" or instrument.currency != IDR:
        msg = (
            f"Yahoo's .JK tickers cover IDX IDR stocks, "
            f"not {instrument.symbol} on {instrument.market}"
        )
        raise ValueError(msg)
    return instrument.symbol + SUFFIX


def _decimal(value: object) -> Decimal:
    """A pandas/numpy number as the Decimal of its shortest float spelling."""
    return Decimal(repr(float(cast("float", value))))


def history_from_frames(ticker: str, frame: pd.DataFrame, splits: pd.Series) -> YahooHistory:
    """Convert ``Ticker.history(auto_adjust=False, actions=True)`` and ``Ticker.splits``."""
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        msg = f"{ticker}: Yahoo's response has no {missing[0]!r} column; its format has changed"
        raise DataUnavailableError(msg)
    if frame.empty:
        msg = f"{ticker}: Yahoo returned no rows"
        raise DataUnavailableError(msg)
    for index in (frame.index, splits.index):
        zone = str(getattr(index, "tz", None))
        if zone != YAHOO_TIMEZONE and len(index):
            msg = f"{ticker}: Yahoo's dates are in {zone}, expected {YAHOO_TIMEZONE}"
            raise DataUnavailableError(msg)
    rows = tuple(
        YahooRow(
            day=day,
            open=_decimal(record["Open"]),
            high=_decimal(record["High"]),
            low=_decimal(record["Low"]),
            close=_decimal(record["Close"]),
            volume=int(record["Volume"]),
            dividend=_decimal(record["Dividends"]),
        )
        for stamp, record in frame.iterrows()
        if _priced(ticker, day := cast("pd.Timestamp", stamp).date(), record)
    )
    split_rows = tuple(
        (cast("pd.Timestamp", stamp).date(), _decimal(ratio)) for stamp, ratio in splits.items()
    )
    return YahooHistory(ticker, rows, split_rows)


def _priced(ticker: str, day: date, record: pd.Series) -> bool:
    """Whether Yahoo gives *record* its prices and volume. A row without them is a day Yahoo has
    no prices for, such as its unfinished day: no bar, like a day it leaves out. A dividend on such
    a row would be lost with it, so that row is refused instead (fail closed)."""
    if not any(math.isnan(float(record[column])) for column in (*PRICE_COLUMNS, "Volume")):
        return True
    if float(record["Dividends"]) != 0:
        msg = f"{ticker}: Yahoo has no prices for {day.isoformat()}, the ex-date of a dividend"
        raise DataUnavailableError(msg)
    return False


def history_to_json(history: YahooHistory, *, recorded: date, source: str) -> str:
    """A recorded response, as committed under ``tests/fixtures/yahoo`` (spec §10.3)."""
    document = {
        "ticker": history.ticker,
        "recorded": recorded.isoformat(),
        "source": source,
        "splits": [[day.isoformat(), str(ratio)] for day, ratio in history.splits],
        "rows": [
            {
                "day": row.day.isoformat(),
                "open": str(row.open),
                "high": str(row.high),
                "low": str(row.low),
                "close": str(row.close),
                "volume": row.volume,
                "dividend": str(row.dividend),
            }
            for row in history.rows
        ],
    }
    return json.dumps(document, indent=1) + "\n"


def history_from_json(path: Path) -> YahooHistory:
    """Load a recorded response written by ``history_to_json``."""
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = tuple(
        YahooRow(
            day=date.fromisoformat(row["day"]),
            open=Decimal(row["open"]),
            high=Decimal(row["high"]),
            low=Decimal(row["low"]),
            close=Decimal(row["close"]),
            volume=int(row["volume"]),
            dividend=Decimal(row["dividend"]),
        )
        for row in document["rows"]
    )
    splits = tuple((date.fromisoformat(day), Decimal(ratio)) for day, ratio in document["splits"])
    return YahooHistory(str(document["ticker"]), rows, splits)


def _split(instrument: Instrument, day: date, ratio: Decimal) -> Split:
    fraction = Fraction(ratio).limit_denominator(_SPLIT_DENOMINATOR_LIMIT)
    if fraction <= 0 or Decimal(fraction.numerator) / fraction.denominator != ratio:
        msg = f"{instrument.symbol}: Yahoo's split ratio {ratio} on {day.isoformat()} is not usable"
        raise DataUnavailableError(msg)
    return Split(instrument, day, fraction.denominator, fraction.numerator)


def _whole(value: Decimal) -> int | None:
    nearest = value.to_integral_value()
    return int(nearest) if abs(value - nearest) <= WHOLE_RUPIAH_TOLERANCE else None


def actions_in(
    history: YahooHistory,
    instrument: Instrument,
    start: date,
    end: date,
    runs: Sequence[Run] = (),
) -> list[CorporateAction]:
    """The splits and cash dividends with an ex-date from *start* to *end*, in date order.

    A dividend is restated through every reported split after its ex-date, as prices are, and
    through the factor of the proven run its ex-date falls in. One whose ex-date falls in an
    unproven run is refused, naming it: its amount is known to be wrong. No calendar is read.
    """
    actions: list[CorporateAction] = [
        _split(instrument, day, ratio) for day, ratio in history.splits if start <= day <= end
    ]
    refused: list[date] = []
    for row in history.rows:
        if start <= row.day <= end and row.dividend > 0:
            amount = row.dividend * _factor(history, row.day)
            run = _covering(runs, row.day)
            if run is not None and run.factor is None:
                refused.append(row.day)
                continue
            if run is not None and run.factor is not None:
                amount = restore_dividend(amount, run.factor)
            actions.append(CashDividend(instrument, row.day, amount))
    if refused:
        raise UnprovenDividendsError(history.ticker, refused)
    actions.sort(key=lambda action: action.ex_date)
    return actions


class UnprovenDividendsError(UnavailableDaysError):
    """Dividends whose ex-date falls in a run of Yahoo's prices carrying an unreported adjustment
    that could not be proven: their recorded amounts are known to be wrong (#160 spec §5)."""

    def __init__(self, ticker: str, days: Sequence[date]) -> None:
        found = tuple(days)
        named = ", ".join(day.isoformat() for day in found)
        super().__init__(
            f"{ticker}: the dividend(s) with ex-date {named} fall in days whose prices carry an "
            "adjustment Yahoo does not report and steadyhand could not prove, so the amounts "
            "are known to be wrong",
            found,
        )


def reversed_prices(history: YahooHistory, row: YahooRow) -> tuple[Decimal, ...]:
    """*row*'s open, high, low and close with every reported split after it reversed."""
    factor = _factor(history, row.day)
    return tuple(value * factor for value in (row.open, row.high, row.low, row.close))


def _all_whole(prices: Sequence[Decimal]) -> bool:
    return all(_whole(price) is not None for price in prices)


def _placeholder(row: YahooRow) -> bool:
    """A flat row with no volume: it repeats an earlier close, on a holiday or not."""
    return row.volume == 0 and row.open == row.high == row.low == row.close


def evidence(history: YahooHistory) -> list[PriceRow]:
    """The proof's input (#160 spec §4): every row with a price that is not whole after the
    reported splits are reversed, in date order, except a flat row with no volume, which repeats
    an earlier close and is no evidence. Its volume plays no part (spec §3.6)."""
    found: list[PriceRow] = []
    for row in history.rows:
        prices = reversed_prices(history, row)
        if not _placeholder(row) and not _all_whole(prices):
            found.append(PriceRow(row.day, prices))
    return found


def _covering(runs: Sequence[Run], day: date) -> Run | None:
    return next((run for run in runs if run.first <= day <= run.last), None)


def _amounts(prices: Sequence[Decimal], run: Run | None, day: date) -> list[int] | None:
    """The traded prices: whole as they are, restored in a proven run, else ``None``."""
    whole = [_whole(price) for price in prices]
    if all(amount is not None for amount in whole):
        return [cast("int", amount) for amount in whole]
    if run is None or run.factor is None:
        return None
    return [restore_price(price, run.factor, day).amount for price in prices]


def _factor(history: YahooHistory, day: date) -> Decimal:
    """The product of every reported split ratio after *day*, which Yahoo divided *day* by."""
    factor = Decimal(1)
    for split_day, ratio in history.splits:
        if split_day > day:
            factor *= ratio
    return factor


def unadjust(
    history: YahooHistory,
    instrument: Instrument,
    calendar: IdxCalendar,
    span: tuple[date, date],
    runs: Sequence[Run] = (),
) -> tuple[list[Bar], list[CorporateAction]]:
    """The bars and actions from the first to the last day of *span*, with Yahoo's split
    adjustments reversed and the prices of every day in a proven run of *runs* restored."""
    start, end = span
    bars: list[Bar] = []
    unrecoverable: list[date] = []
    for row in history.rows:
        if not start <= row.day <= end:
            continue
        flat = row.open == row.high == row.low == row.close
        if not calendar.is_trading_day(row.day):
            if row.volume == 0 and flat:
                continue
            msg = (
                f"{history.ticker}: Yahoo shows trading on {row.day.isoformat()}, "
                "which the IDX calendar says was a holiday"
            )
            raise DataUnavailableError(msg)
        amounts = _amounts(reversed_prices(history, row), _covering(runs, row.day), row.day)
        volume = _whole(row.volume / _factor(history, row.day))
        if amounts is None or volume is None:
            unrecoverable.append(row.day)
            continue
        opening, high, low, closing = (Money(amount, IDR) for amount in amounts)
        try:
            bars.append(Bar(instrument, row.day, opening, high, low, closing, volume))
        except InvalidBarError as error:
            msg = f"{history.ticker}: {error}"
            raise DataUnavailableError(msg) from error
    if unrecoverable:
        raise UnrecoverablePricesError(history.ticker, unrecoverable)
    return bars, actions_in(history, instrument, start, end, runs)


@dataclass(frozen=True, slots=True)
class RequestPolicy:
    """How politely and how persistently Yahoo is asked (spec §9.2)."""

    attempts: int = 3
    backoff_seconds: float = 1.0
    pause_seconds: float = 1.0


class YahooDataSource:
    """A ``DataSource`` backed by Yahoo Finance. Wrap it in ``CachedDataSource`` for real use."""

    def __init__(
        self,
        calendar: IdxCalendar | None = None,
        *,
        download: Downloader | None = None,
        sleep: Callable[[float], None] = time.sleep,
        policy: RequestPolicy = RequestPolicy(),  # noqa: B008 - a frozen value, safe to share
        today: Callable[[], date] = jakarta_today,
    ) -> None:
        self._calendar = IdxCalendar.shipped() if calendar is None else calendar
        self._download = download_history if download is None else download
        self._sleep = sleep
        self._policy = policy
        self._today = today
        self._requests = 0
        self._last: tuple[tuple[str, date, date], YahooHistory] | None = None
        self._runs: dict[str, tuple[Run, ...]] = {}

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        history = self._history(instrument, start, end)
        runs = self._runs_for(history, start, end)
        return unadjust(history, instrument, self._calendar, (start, end), runs)[0]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        """The splits and dividends in the range, read without the calendar (``actions_in``)."""
        history = self._history(instrument, start, end)
        return actions_in(history, instrument, start, end, self._runs_for(history, start, end))

    def restorations(
        self, instrument: Instrument, start: date, end: date
    ) -> tuple[Restoration, ...]:
        """The proven runs overlapping the range, oldest first. A range with no price that is
        not whole reads no runs, and restores nothing, so it has none."""
        history = self._history(instrument, start, end)
        return tuple(
            Restoration(instrument, run.first, run.last, run.factor, run.prices)
            for run in self._runs_for(history, start, end)
            if run.factor is not None and run.first <= end and run.last >= start
        )

    def _history(self, instrument: Instrument, start: date, end: date) -> YahooHistory:
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        return self._fetch(ticker_for(instrument), start, end)

    def _runs_for(self, history: YahooHistory, start: date, end: date) -> tuple[Run, ...]:
        """The runs of the stock's whole history, from ``GRID_START`` to today, read once per
        ticker, when the range has a price that is not whole; none otherwise (#160 spec §5)."""
        if all(
            _all_whole(reversed_prices(history, row))
            for row in history.rows
            if start <= row.day <= end
        ):
            return ()
        ticker = history.ticker
        if ticker not in self._runs:
            whole = self._request(ticker, GRID_START, self._today())
            self._runs[ticker] = find_runs(evidence(whole))
        return self._runs[ticker]

    def _fetch(self, ticker: str, start: date, end: date) -> YahooHistory:
        """One download per range: ``bars`` then ``corporate_actions`` reuse it."""
        key = (ticker, start, end)
        if self._last is not None and self._last[0] == key:
            return self._last[1]
        history = self._request(ticker, start, end)
        self._last = (key, history)
        return history

    def _request(self, ticker: str, start: date, end: date) -> YahooHistory:
        """Ask Yahoo, under the request policy: a pause between requests, retries with backoff."""
        failure: DataUnavailableError | None = None
        for attempt in range(self._policy.attempts):
            if attempt:
                self._sleep(self._policy.backoff_seconds * 2 ** (attempt - 1))
            elif self._requests:
                self._sleep(self._policy.pause_seconds)
            self._requests += 1
            try:
                return self._download(ticker, start, end)
            except DataUnavailableError as error:
                failure = error
        msg = (
            f"{ticker}: no data from Yahoo for {start.isoformat()} to {end.isoformat()} "
            f"after {self._policy.attempts} attempts: {failure}"
        )
        raise DataUnavailableError(msg) from failure


def download_history(ticker: str, start: date, end: date) -> YahooHistory:  # pragma: no cover
    """Ask Yahoo for one ticker's history (network; run daily by the yahoo-shape workflow).

    This is the only function that talks to Yahoo, and the only code excluded from coverage:
    ``tests/meta/test_coverage_exclusions.py`` holds it to that. Everything it returns goes
    through ``history_from_frames``, which the tests run on real recorded data.
    """
    import yfinance  # noqa: PLC0415 - a heavy import, paid only when data is really fetched

    yfinance.config.debug.hide_exceptions = False  # raise a failure instead of logging it
    try:
        handle = yfinance.Ticker(ticker)
        frame = handle.history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),  # yfinance's end is exclusive
            auto_adjust=False,
            actions=True,
        )
        splits = handle.splits
    except Exception as error:  # a network library's failures are not ours to enumerate
        msg = f"{ticker}: the request to Yahoo failed: {error}"
        raise DataUnavailableError(msg) from error
    return history_from_frames(ticker, frame, splits)
