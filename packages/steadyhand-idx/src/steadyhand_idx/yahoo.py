"""``YahooDataSource``: unadjusted IDX prices from Yahoo Finance's ``.JK`` tickers (spec §9.2).

Yahoo's "unadjusted" history is not unadjusted (docs/research/t-hist.md §6). Even with
``auto_adjust=False`` every price before a split is divided by the split ratio, and every
dividend with it. Splits are reported, so their adjustment is reversed exactly here, using the
stock's full split history (a split after the requested range still adjusts the prices in it).

Some adjustments are not reported. A rights issue, for one, scales every earlier price by a
factor nobody publishes, so after reversing the reported splits those prices are no longer whole
rupiah. They cannot be recovered, and a day like that raises ``UnrecoverablePricesError`` naming
it (fail closed, spec §9.2). Measured on 2026-09-25 over 25 large IDX stocks for 2021-2025: BBRI
up to 2021-09-07, SMGR up to 2022-12-12, MDKA up to 2022-04-13 and five INCO days in June 2024.

Trading days come from ``holidays.toml``, never from which days have bars. A flat bar with no
volume on a holiday is a Yahoo placeholder and is dropped. A bar with trading on a holiday
contradicts the calendar, and is refused.
"""

from __future__ import annotations

import json
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
)
from steadyhand_idx.calendar import IdxCalendar

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


class UnrecoverablePricesError(DataUnavailableError):
    """Yahoo's prices for these days carry an adjustment it does not report, so the traded
    prices cannot be worked out. ``days`` lists every such day in the requested range."""

    def __init__(self, ticker: str, days: Sequence[date]) -> None:
        self.days = tuple(days)
        super().__init__(
            f"{ticker}: Yahoo's prices for {len(self.days)} day(s) from "
            f"{self.days[0].isoformat()} to {self.days[-1].isoformat()} carry an adjustment it "
            "does not report as a split (for example a rights issue), so the prices traded on "
            "those days cannot be recovered"
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
            day=cast("pd.Timestamp", stamp).date(),
            open=_decimal(record["Open"]),
            high=_decimal(record["High"]),
            low=_decimal(record["Low"]),
            close=_decimal(record["Close"]),
            volume=int(record["Volume"]),
            dividend=_decimal(record["Dividends"]),
        )
        for stamp, record in frame.iterrows()
    )
    split_rows = tuple(
        (cast("pd.Timestamp", stamp).date(), _decimal(ratio)) for stamp, ratio in splits.items()
    )
    return YahooHistory(ticker, rows, split_rows)


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


def unadjust(
    history: YahooHistory, instrument: Instrument, calendar: IdxCalendar, start: date, end: date
) -> tuple[list[Bar], list[CorporateAction]]:
    """The bars and actions from *start* to *end*, with Yahoo's split adjustments reversed."""
    splits = [(day, ratio) for day, ratio in history.splits]
    bars: list[Bar] = []
    actions: list[CorporateAction] = [
        _split(instrument, day, ratio) for day, ratio in splits if start <= day <= end
    ]
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
        factor = Decimal(1)
        for day, ratio in splits:
            if day > row.day:
                factor *= ratio
        prices = [_whole(value * factor) for value in (row.open, row.high, row.low, row.close)]
        volume = _whole(row.volume / factor)
        if None in prices or volume is None:
            unrecoverable.append(row.day)
            continue
        opening, high, low, closing = (Money(cast("int", price), IDR) for price in prices)
        try:
            bars.append(Bar(instrument, row.day, opening, high, low, closing, volume))
        except InvalidBarError as error:
            msg = f"{history.ticker}: {error}"
            raise DataUnavailableError(msg) from error
        if row.dividend > 0:
            actions.append(CashDividend(instrument, row.day, row.dividend * factor))
    if unrecoverable:
        raise UnrecoverablePricesError(history.ticker, unrecoverable)
    actions.sort(key=lambda action: action.ex_date)
    return bars, actions


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
    ) -> None:
        self._calendar = IdxCalendar.shipped() if calendar is None else calendar
        self._download = download_history if download is None else download
        self._sleep = sleep
        self._policy = policy
        self._requests = 0
        self._last: tuple[tuple[str, date, date], YahooHistory] | None = None

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        return self._unadjusted(instrument, start, end)[0]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return self._unadjusted(instrument, start, end)[1]

    def _unadjusted(
        self, instrument: Instrument, start: date, end: date
    ) -> tuple[list[Bar], list[CorporateAction]]:
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        ticker = ticker_for(instrument)
        return unadjust(self._fetch(ticker, start, end), instrument, self._calendar, start, end)

    def _fetch(self, ticker: str, start: date, end: date) -> YahooHistory:
        """One download per range: ``bars`` then ``corporate_actions`` reuse it."""
        key = (ticker, start, end)
        if self._last is not None and self._last[0] == key:
            return self._last[1]
        failure: DataUnavailableError | None = None
        for attempt in range(self._policy.attempts):
            if attempt:
                self._sleep(self._policy.backoff_seconds * 2 ** (attempt - 1))
            elif self._requests:
                self._sleep(self._policy.pause_seconds)
            self._requests += 1
            try:
                history = self._download(ticker, start, end)
            except DataUnavailableError as error:
                failure = error
                continue
            self._last = (key, history)
            return history
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
