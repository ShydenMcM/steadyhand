"""The Yahoo data source, run on real recorded responses (spec §10.3: real data, replayed)."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from functools import cache
from itertools import pairwise
from pathlib import Path

import pandas as pd
import pytest

from steadyhand import (
    IDR,
    CashDividend,
    DataSource,
    DataUnavailableError,
    Instrument,
    Money,
    Side,
    Split,
    UnavailableDaysError,
)
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.rules import IdxMarketRules
from steadyhand_idx.yahoo import (
    RequestPolicy,
    UnrecoverablePricesError,
    YahooDataSource,
    YahooHistory,
    YahooRow,
    history_from_frames,
    history_from_json,
    history_to_json,
    ticker_for,
    unadjust,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"
BBCA_FILE = FIXTURES / "BBCA.JK_2021-09-01_2021-11-30.json"
BBRI_FILE = FIXTURES / "BBRI.JK_2021-08-02_2021-09-30.json"
UNVR_FILE = FIXTURES / "UNVR.JK_2023-05-15_2023-06-09.json"
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
UNVR = Instrument("UNVR", "IDX", IDR)


@cache
def calendar() -> IdxCalendar:
    return IdxCalendar.shipped()


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def test_tickers_are_the_symbol_with_jk() -> None:
    assert ticker_for(BBCA) == "BBCA.JK"
    with pytest.raises(
        ValueError, match=r"^Yahoo's \.JK tickers cover IDX IDR stocks, not X on ASX$"
    ):
        ticker_for(Instrument("X", "ASX", IDR))


def test_splits_are_reversed_using_the_whole_split_history() -> None:
    bars, actions = unadjust(
        history_from_json(BBCA_FILE), BBCA, calendar(), date(2021, 9, 1), date(2021, 11, 30)
    )
    by_day = {bar.day: bar for bar in bars}
    # Yahoo reads 6,550 for the open on 1 Sep 2021: a fifth of what traded, for the later split.
    first = by_day[date(2021, 9, 1)]
    assert (first.open, first.close, first.volume) == (rp(32_750), rp(32_825), 13_472_500)
    assert by_day[date(2021, 10, 12)].close == rp(36_600)  # the last day before the split
    assert by_day[date(2021, 10, 13)].open == rp(7_400)  # the first day after it
    assert actions == [
        Split(BBCA, date(2021, 10, 13), 1, 5),
        CashDividend(BBCA, date(2021, 11, 17), Decimal("25.0")),
    ]


def test_there_is_one_bar_per_trading_day() -> None:
    start, end = date(2021, 9, 1), date(2021, 11, 30)
    bars, _ = unadjust(history_from_json(BBCA_FILE), BBCA, calendar(), start, end)
    assert [bar.day for bar in bars] == list(calendar().trading_days(start, end))


@pytest.mark.parametrize(
    ("path", "instrument", "start", "end"),
    [
        (BBCA_FILE, BBCA, date(2021, 9, 1), date(2021, 11, 30)),
        (BBRI_FILE, BBRI, date(2021, 9, 8), date(2021, 9, 30)),
        (UNVR_FILE, UNVR, date(2023, 5, 15), date(2023, 6, 9)),
    ],
)
def test_recovered_prices_obey_the_ticks_and_bands(
    path: Path, instrument: Instrument, start: date, end: date
) -> None:
    """Real data against the rule tables: every price is on the tick grid, and every day's prices
    sit inside the auto-rejection band around the previous close, except across a split, where
    the reference is the theoretical price (t-verify.md §4.2)."""
    bars, actions = unadjust(history_from_json(path), instrument, calendar(), start, end)
    split_days = {action.ex_date for action in actions if isinstance(action, Split)}
    for bar in bars:
        for price in (bar.open, bar.high, bar.low, bar.close):
            assert rules().round_to_tick(instrument, price, Side.BUY, bar.day) == price, bar.day
    checked = 0
    for previous, bar in pairwise(bars):
        if bar.day in split_days:
            continue
        low, high = rules().price_band(instrument, previous.close, bar.day)
        assert low <= bar.low, bar.day
        assert bar.high <= high, bar.day
        checked += 1
    assert checked == len(bars) - 1 - len(split_days & {bar.day for bar in bars[1:]})
    assert checked > 10


def test_an_unreported_adjustment_is_refused_with_every_day_named() -> None:
    history = history_from_json(BBRI_FILE)
    with pytest.raises(
        UnrecoverablePricesError,
        match=(
            r"^BBRI\.JK: Yahoo's prices for 25 day\(s\) from 2021-08-02 to 2021-09-07 carry an "
            r"adjustment it does not report as a split"
        ),
    ) as caught:
        unadjust(history, BBRI, calendar(), date(2021, 8, 2), date(2021, 9, 30))
    assert isinstance(caught.value, UnavailableDaysError)
    assert caught.value.days == calendar().trading_days(date(2021, 8, 2), date(2021, 9, 7))
    bars, _ = unadjust(history, BBRI, calendar(), date(2021, 9, 8), date(2021, 9, 30))
    assert bars[0].close == rp(3_730)


def test_a_zero_volume_trading_day_is_kept() -> None:
    bars, _ = unadjust(
        history_from_json(UNVR_FILE), UNVR, calendar(), date(2023, 5, 15), date(2023, 6, 9)
    )
    quiet = [bar for bar in bars if bar.volume == 0]
    # Yahoo gives UNVR no volume on 24 May 2023, though its open and close differ. The day is
    # kept, and spec §5.1 rejects orders on it: the cautious reading of a missing number.
    assert [(bar.day, bar.open, bar.close) for bar in quiet] == [
        (date(2023, 5, 24), rp(4_450), rp(4_410))
    ]


def _with_row(history: YahooHistory, row: YahooRow) -> YahooHistory:
    return replace(history, rows=tuple(sorted((*history.rows, row), key=lambda r: r.day)))


def test_a_flat_empty_bar_on_a_holiday_is_dropped() -> None:
    placeholder = YahooRow(date(2023, 5, 18), *(Decimal(4450),) * 4, volume=0, dividend=Decimal(0))
    history = _with_row(history_from_json(UNVR_FILE), placeholder)
    bars, _ = unadjust(history, UNVR, calendar(), date(2023, 5, 15), date(2023, 6, 9))
    assert date(2023, 5, 18) not in {bar.day for bar in bars}


def test_trading_on_a_holiday_is_refused() -> None:
    traded = YahooRow(date(2023, 5, 18), *(Decimal(4450),) * 4, volume=100, dividend=Decimal(0))
    history = _with_row(history_from_json(UNVR_FILE), traded)
    with pytest.raises(
        DataUnavailableError,
        match=r"^UNVR\.JK: Yahoo shows trading on 2023-05-18, which the IDX calendar says",
    ):
        unadjust(history, UNVR, calendar(), date(2023, 5, 15), date(2023, 6, 9))


def test_an_inconsistent_bar_is_refused() -> None:
    history = history_from_json(UNVR_FILE)
    broken = replace(history.rows[0], high=Decimal(1))
    with pytest.raises(
        DataUnavailableError, match=r"^UNVR\.JK: UNVR 2023-05-15: .* do not bracket"
    ):
        unadjust(
            replace(history, rows=(broken,)), UNVR, calendar(), date(2023, 5, 15), date(2023, 5, 15)
        )


@pytest.mark.parametrize(("ratio", "old", "new"), [("5.0", 1, 5), ("0.2", 5, 1), ("1.5", 2, 3)])
def test_split_ratios_become_whole_share_counts(ratio: str, old: int, new: int) -> None:
    history = YahooHistory("X.JK", (), ((date(2023, 5, 22), Decimal(ratio)),))
    _, actions = unadjust(history, UNVR, calendar(), date(2023, 5, 15), date(2023, 6, 9))
    assert actions == [Split(UNVR, date(2023, 5, 22), old, new)]


@pytest.mark.parametrize("ratio", ["0.3333", "0", "-2"])
def test_an_unusable_split_ratio_is_refused(ratio: str) -> None:
    history = YahooHistory("X.JK", (), ((date(2023, 5, 22), Decimal(ratio)),))
    with pytest.raises(DataUnavailableError, match=rf"^UNVR: Yahoo's split ratio {ratio} on"):
        unadjust(history, UNVR, calendar(), date(2023, 5, 15), date(2023, 6, 9))


def _frames(history: YahooHistory) -> tuple[pd.DataFrame, pd.Series]:
    """The pandas objects yfinance returns, rebuilt from a recording: the same columns, dtypes
    and time zone as ``Ticker.history`` and ``Ticker.splits`` (checked live by test_yahoo_live)."""
    index = pd.DatetimeIndex([pd.Timestamp(row.day) for row in history.rows]).tz_localize(
        "Asia/Jakarta"
    )
    frame = pd.DataFrame(
        {
            "Open": [float(row.open) for row in history.rows],
            "High": [float(row.high) for row in history.rows],
            "Low": [float(row.low) for row in history.rows],
            "Close": [float(row.close) for row in history.rows],
            "Adj Close": [float(row.close) for row in history.rows],
            "Volume": [row.volume for row in history.rows],
            "Dividends": [float(row.dividend) for row in history.rows],
            "Stock Splits": [0.0 for _ in history.rows],
        },
        index=index,
    )
    split_index = pd.DatetimeIndex([pd.Timestamp(day) for day, _ in history.splits])
    splits = pd.Series(
        [float(ratio) for _, ratio in history.splits],
        index=split_index.tz_localize("Asia/Jakarta"),
    )
    return frame, splits


@pytest.mark.parametrize("path", [BBCA_FILE, BBRI_FILE, UNVR_FILE])
def test_frames_convert_to_exactly_what_was_recorded(path: Path) -> None:
    recorded = history_from_json(path)
    assert history_from_frames(recorded.ticker, *_frames(recorded)) == recorded


def test_a_changed_response_shape_is_refused() -> None:
    frame, splits = _frames(history_from_json(UNVR_FILE))
    with pytest.raises(DataUnavailableError, match=r"^X\.JK: Yahoo's response has no 'Dividends'"):
        history_from_frames("X.JK", frame.drop(columns=["Dividends"]), splits)
    with pytest.raises(DataUnavailableError, match=r"^X\.JK: Yahoo returned no rows$"):
        history_from_frames("X.JK", frame.iloc[0:0], splits)
    with pytest.raises(DataUnavailableError, match="dates are in UTC, expected Asia/Jakarta"):
        history_from_frames("X.JK", frame.tz_convert("UTC"), splits)


def test_recordings_round_trip_through_json(tmp_path: Path) -> None:
    recorded = history_from_json(BBCA_FILE)
    path = tmp_path / "copy.json"
    path.write_text(history_to_json(recorded, recorded=date(2026, 9, 25), source="test"))
    assert history_from_json(path) == recorded


class Replay:
    """Serves a recording in place of the network, failing the first *failures* calls."""

    def __init__(self, path: Path, failures: int = 0) -> None:
        self.history = history_from_json(path)
        self.failures = failures
        self.calls: list[tuple[str, date, date]] = []

    def __call__(self, ticker: str, start: date, end: date) -> YahooHistory:
        self.calls.append((ticker, start, end))
        if len(self.calls) <= self.failures:
            msg = f"{ticker}: the request to Yahoo failed: timeout {len(self.calls)}"
            raise DataUnavailableError(msg)
        return self.history


def test_the_source_is_a_data_source_and_downloads_each_range_once() -> None:
    replay, slept = Replay(BBCA_FILE), list[float]()
    source = YahooDataSource(calendar(), download=replay, sleep=slept.append)
    assert isinstance(source, DataSource)
    start, end = date(2021, 10, 1), date(2021, 10, 29)
    assert len(source.bars(BBCA, start, end)) == len(calendar().trading_days(start, end))
    assert source.corporate_actions(BBCA, start, end) == [Split(BBCA, date(2021, 10, 13), 1, 5)]
    assert replay.calls == [("BBCA.JK", start, end)]
    source.bars(BBCA, start, date(2021, 10, 28))
    assert slept == [1.0]  # a pause before every request after the first


def test_failures_are_retried_with_backoff_then_raised() -> None:
    replay, slept = Replay(BBCA_FILE, failures=2), list[float]()
    source = YahooDataSource(calendar(), download=replay, sleep=slept.append)
    assert source.bars(BBCA, date(2021, 10, 1), date(2021, 10, 1))
    assert slept == [1.0, 2.0]
    replay, slept = Replay(BBCA_FILE, failures=3), list[float]()
    source = YahooDataSource(
        calendar(), download=replay, sleep=slept.append, policy=RequestPolicy(attempts=3)
    )
    with pytest.raises(
        DataUnavailableError,
        match=(
            r"^BBCA\.JK: no data from Yahoo for 2021-10-01 to 2021-10-01 after 3 attempts: "
            r"BBCA\.JK: the request to Yahoo failed: timeout 3$"
        ),
    ) as caught:
        source.bars(BBCA, date(2021, 10, 1), date(2021, 10, 1))
    assert isinstance(caught.value.__cause__, DataUnavailableError)


def test_a_reversed_range_is_refused() -> None:
    source = YahooDataSource(calendar(), download=Replay(BBCA_FILE))
    with pytest.raises(ValueError, match=r"^end 2021-10-01 is before start 2021-10-02$"):
        source.bars(BBCA, date(2021, 10, 2), date(2021, 10, 1))


def test_the_default_source_uses_the_shipped_calendar() -> None:
    source = YahooDataSource(download=Replay(UNVR_FILE))
    assert len(source.bars(UNVR, date(2023, 5, 15), date(2023, 6, 9))) == 17
