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
    UnsupportedDateError,
)
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.factor import GRID_START, Restoration, find_runs
from steadyhand_idx.rules import IdxMarketRules
from steadyhand_idx.yahoo import (
    RequestPolicy,
    UnprovenDividendsError,
    UnrecoverablePricesError,
    YahooDataSource,
    YahooHistory,
    YahooRow,
    actions_in,
    evidence,
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
BBRI_FIVE_YEARS = FIXTURES / "BBRI.JK_2017-01-31_2022-01-31.json"
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
        history_from_json(BBCA_FILE), BBCA, calendar(), (date(2021, 9, 1), date(2021, 11, 30))
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
    bars, _ = unadjust(history_from_json(BBCA_FILE), BBCA, calendar(), (start, end))
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
    bars, actions = unadjust(history_from_json(path), instrument, calendar(), (start, end))
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
        unadjust(history, BBRI, calendar(), (date(2021, 8, 2), date(2021, 9, 30)))
    assert isinstance(caught.value, UnavailableDaysError)
    assert caught.value.days == calendar().trading_days(date(2021, 8, 2), date(2021, 9, 7))
    bars, _ = unadjust(history, BBRI, calendar(), (date(2021, 9, 8), date(2021, 9, 30)))
    assert bars[0].close == rp(3_730)


def test_a_zero_volume_trading_day_is_kept() -> None:
    bars, _ = unadjust(
        history_from_json(UNVR_FILE), UNVR, calendar(), (date(2023, 5, 15), date(2023, 6, 9))
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
    bars, _ = unadjust(history, UNVR, calendar(), (date(2023, 5, 15), date(2023, 6, 9)))
    assert date(2023, 5, 18) not in {bar.day for bar in bars}


def test_trading_on_a_holiday_is_refused() -> None:
    traded = YahooRow(date(2023, 5, 18), *(Decimal(4450),) * 4, volume=100, dividend=Decimal(0))
    history = _with_row(history_from_json(UNVR_FILE), traded)
    with pytest.raises(
        DataUnavailableError,
        match=r"^UNVR\.JK: Yahoo shows trading on 2023-05-18, which the IDX calendar says",
    ):
        unadjust(history, UNVR, calendar(), (date(2023, 5, 15), date(2023, 6, 9)))


def test_an_inconsistent_bar_is_refused() -> None:
    history = history_from_json(UNVR_FILE)
    broken = replace(history.rows[0], high=Decimal(1))
    with pytest.raises(
        DataUnavailableError, match=r"^UNVR\.JK: UNVR 2023-05-15: .* do not bracket"
    ):
        unadjust(
            replace(history, rows=(broken,)),
            UNVR,
            calendar(),
            (date(2023, 5, 15), date(2023, 5, 15)),
        )


@pytest.mark.parametrize(("ratio", "old", "new"), [("5.0", 1, 5), ("0.2", 5, 1), ("1.5", 2, 3)])
def test_split_ratios_become_whole_share_counts(ratio: str, old: int, new: int) -> None:
    history = YahooHistory("X.JK", (), ((date(2023, 5, 22), Decimal(ratio)),))
    _, actions = unadjust(history, UNVR, calendar(), (date(2023, 5, 15), date(2023, 6, 9)))
    assert actions == [Split(UNVR, date(2023, 5, 22), old, new)]


@pytest.mark.parametrize("ratio", ["0.3333", "0", "-2"])
def test_an_unusable_split_ratio_is_refused(ratio: str) -> None:
    history = YahooHistory("X.JK", (), ((date(2023, 5, 22), Decimal(ratio)),))
    with pytest.raises(DataUnavailableError, match=rf"^UNVR: Yahoo's split ratio {ratio} on"):
        unadjust(history, UNVR, calendar(), (date(2023, 5, 15), date(2023, 6, 9)))


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


@pytest.mark.parametrize("column", ["Open", "High", "Low", "Close", "Volume"])
def test_a_row_yahoo_gives_no_price_is_no_bar(column: str) -> None:
    """Yahoo's unfinished day has no close (as today's had on 2026-10-01): it is no bar, and
    reading the whole history up to today must not stop on it (plan scope decision 20)."""
    history = history_from_json(BBCA_FILE)
    frame, splits = _frames(history)
    frame[column] = frame[column].astype(float)
    frame.loc[frame.index[-1], column] = float("nan")
    assert history_from_frames("BBCA.JK", frame, splits).rows == history.rows[:-1]


def test_a_dividend_on_a_row_with_no_price_is_refused() -> None:
    history = history_from_json(BBCA_FILE)
    frame, splits = _frames(history)
    last = frame.index[-1]
    frame.loc[last, "Close"] = float("nan")
    frame.loc[last, "Dividends"] = 25.0
    day = history.rows[-1].day.isoformat()
    with pytest.raises(
        DataUnavailableError,
        match=rf"^BBCA\.JK: Yahoo has no prices for {day}, the ex-date of a dividend",
    ):
        history_from_frames("BBCA.JK", frame, splits)


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
    with pytest.raises(ValueError, match=r"^end 2021-10-01 is before start 2021-10-02$"):
        source.corporate_actions(BBCA, date(2021, 10, 2), date(2021, 10, 1))


def test_the_default_source_uses_the_shipped_calendar() -> None:
    source = YahooDataSource(download=Replay(UNVR_FILE))
    assert len(source.bars(UNVR, date(2023, 5, 15), date(2023, 6, 9))) == 17


def test_actions_are_read_where_the_prices_cannot_be_recovered() -> None:
    # BBRI's prices before 2021-09-07 carry a rights issue Yahoo does not report, so without the
    # runs of its whole history no bar can be recovered there, but a dividend needs no price
    # (M6 spec §4.3).
    history = history_from_json(BBRI_FIVE_YEARS)
    refused = (date(2021, 2, 1), date(2021, 9, 7))
    with pytest.raises(UnrecoverablePricesError):
        unadjust(history, BBRI, calendar(), refused)
    assert actions_in(history, BBRI, *refused) == [
        CashDividend(BBRI, date(2021, 4, 6), Decimal("89.91268"))
    ]
    # Yahoo divided the 2017 dividend by the 5-for-1 split of 10 November 2017; it is restated.
    assert actions_in(history, BBRI, date(2017, 1, 31), date(2017, 12, 29)) == [
        CashDividend(BBRI, date(2017, 3, 23), Decimal("389.63463")),
        Split(BBRI, date(2017, 11, 10), 1, 5),
    ]


def test_actions_need_no_calendar() -> None:
    # 2015 is before the IDX holidays begin: its bars cannot be checked, but its actions can be
    # read, restated through the 2-for-1 split that followed.
    row = YahooRow(date(2015, 6, 1), *(Decimal(1000),) * 4, volume=100, dividend=Decimal(50))
    history = YahooHistory("BBCA.JK", (row,), ((date(2016, 6, 1), Decimal("2.0")),))
    year = (date(2015, 1, 1), date(2015, 12, 31))
    assert actions_in(history, BBCA, *year) == [CashDividend(BBCA, date(2015, 6, 1), Decimal(100))]
    with pytest.raises(UnsupportedDateError, match=r"^holidays\.toml has no IDX holidays for 2015"):
        unadjust(history, BBCA, calendar(), year)


TODAY = date(2026, 9, 25)


def restoring(path: Path = BBRI_FIVE_YEARS) -> tuple[YahooDataSource, Replay]:
    """The source on a recording, which also serves the whole-history request (#160)."""
    replay = Replay(path)
    source = YahooDataSource(calendar(), download=replay, sleep=lambda _: None, today=lambda: TODAY)
    return source, replay


def test_the_source_restores_a_ranges_prices_and_dividends_reading_the_whole_history_once() -> None:
    source, replay = restoring()
    restored = (date(2021, 2, 1), date(2021, 9, 7))
    assert source.corporate_actions(BBRI, *restored) == [
        CashDividend(BBRI, date(2021, 4, 6), Decimal("98.9057"))
    ]
    bars = source.bars(BBRI, *restored)
    assert [bar.day for bar in bars] == list(calendar().trading_days(*restored))
    assert (bars[0].open, bars[0].close) == (rp(4_180), rp(4_400))
    later = (date(2021, 10, 1), date(2021, 10, 29))
    source.bars(BBRI, *later)
    assert replay.calls == [
        ("BBRI.JK", *restored),
        ("BBRI.JK", GRID_START, TODAY),
        ("BBRI.JK", *later),
    ]


def test_a_range_whose_prices_are_all_whole_reads_no_whole_history() -> None:
    source, replay = restoring(BBCA_FILE)
    october = (date(2021, 10, 1), date(2021, 10, 29))
    assert source.bars(BBCA, *october)
    assert source.restorations(BBCA, *october) == ()
    assert replay.calls == [("BBCA.JK", *october)]


def test_a_restored_day_is_the_same_whatever_range_is_asked() -> None:
    source, _ = restoring()
    whole = source.bars(BBRI, date(2021, 2, 1), date(2021, 9, 7))
    week = source.bars(BBRI, date(2021, 3, 1), date(2021, 3, 5))
    assert week == [bar for bar in whole if date(2021, 3, 1) <= bar.day <= date(2021, 3, 5)]
    assert len(week) == 5


def test_restorations_are_the_proven_runs_overlapping_the_range() -> None:
    source, _ = restoring()
    run = Restoration(BBRI, date(2017, 1, 31), date(2021, 9, 7), Decimal("1.100019"), 4_412)
    assert source.restorations(BBRI, date(2021, 9, 1), date(2021, 9, 30)) == (run,)
    assert source.restorations(BBRI, date(2021, 9, 8), date(2021, 9, 30)) == ()


def unwhole(day: date, price: str, *, volume: int = 100, dividend: str = "0") -> YahooRow:
    return YahooRow(day, *(Decimal(price),) * 4, volume=volume, dividend=Decimal(dividend))


def test_a_dividend_in_an_unproven_run_is_refused_naming_its_ex_date() -> None:
    # Two days off the grid are 8 prices, too few for a proof: their dividend is known to be
    # wrong, in a look-back as in a backtest's own days (#160 spec §5).
    rows = (
        unwhole(date(2021, 3, 1), "1000.5"),
        unwhole(date(2021, 3, 2), "1001.5", dividend="20.5"),
    )
    history = YahooHistory("BBCA.JK", rows, ())
    source = YahooDataSource(calendar(), download=lambda *_: history, today=lambda: TODAY)
    for start in (date(2021, 1, 4), date(2021, 3, 1)):
        with pytest.raises(
            UnprovenDividendsError,
            match=(
                r"^BBCA\.JK: the dividend\(s\) with ex-date 2021-03-02 fall in days whose prices "
                r"carry an adjustment Yahoo does not report and steadyhand could not prove"
            ),
        ) as caught:
            source.corporate_actions(BBCA, start, date(2021, 3, 31))
        assert isinstance(caught.value, UnavailableDaysError)
        assert caught.value.days == (date(2021, 3, 2),)
    with pytest.raises(UnrecoverablePricesError) as refused:
        source.bars(BBCA, date(2021, 3, 1), date(2021, 3, 2))
    assert refused.value.days == (date(2021, 3, 1), date(2021, 3, 2))
    assert source.restorations(BBCA, date(2021, 3, 1), date(2021, 3, 2)) == ()


def test_the_proof_reads_every_row_with_a_price_off_whole_rupiah_and_nothing_else() -> None:
    rows = (
        unwhole(date(2021, 3, 1), "1000.25"),
        unwhole(date(2021, 3, 2), "1000"),  # whole: never evidence
        unwhole(date(2021, 3, 3), "1000.25", volume=0),  # flat with no volume: no evidence
        unwhole(date(2021, 3, 4), "1000.25", volume=7),  # its volume plays no part
    )
    history = YahooHistory("BBCA.JK", rows, ((date(2021, 6, 1), Decimal("2.0")),))
    assert [(row.day, row.prices) for row in evidence(history)] == [
        (date(2021, 3, 1), (Decimal("2000.500"),) * 4),
        (date(2021, 3, 4), (Decimal("2000.500"),) * 4),
    ]


TRUE = (3550, 3600, 3530, 3580, 3610, 3640)
"""Six traded prices on the Rp10 grid, none a whole rupiah once divided by 1.1."""


def scaled(day: date, price: int, *, volume: int = 100, split: int = 1) -> YahooRow:
    """A flat day as Yahoo shows it: divided by 1.1, and by a later *split*, volume multiplied."""
    recorded = Decimal(price) / Decimal("1.1") / split
    return YahooRow(day, *(recorded,) * 4, volume=volume, dividend=Decimal(0))


def test_a_flat_row_with_no_volume_inside_a_proven_run_is_restored_though_it_is_no_evidence() -> (
    None
):
    days = calendar().trading_days(date(2021, 3, 1), date(2021, 3, 9))
    rows = [scaled(day, price) for day, price in zip(days, TRUE, strict=False)]
    rows[2] = scaled(days[2], TRUE[2], volume=0)
    history = YahooHistory("BBCA.JK", tuple(rows), ())
    runs = find_runs(evidence(history))
    assert [(run.first, run.last, run.prices, run.factor) for run in runs] == [
        (days[0], days[5], 20, Decimal("1.100000"))
    ]
    bars, _ = unadjust(history, BBCA, calendar(), (days[0], days[5]), runs)
    assert [(bar.close, bar.volume) for bar in bars] == [
        (rp(p), 0 if i == 2 else 100) for i, p in enumerate(TRUE)
    ]


def test_restorations_leave_out_a_proven_run_outside_the_range() -> None:
    """Two adjustments stacked: each range reads only the run it overlaps."""
    days = calendar().trading_days(date(2021, 3, 1), date(2021, 3, 31))
    older, newer = days[:6], days[6:12]
    rows = [
        *(
            YahooRow(day, *(Decimal(p) / Decimal("1.3"),) * 4, 100, Decimal(0))
            for day, p in zip(older, TRUE, strict=True)
        ),
        *(
            YahooRow(day, *(Decimal(p) / Decimal("1.1"),) * 4, 100, Decimal(0))
            for day, p in zip(newer, TRUE, strict=True)
        ),
    ]
    history = YahooHistory("BBCA.JK", tuple(rows), ())
    source = YahooDataSource(calendar(), download=lambda *_: history, today=lambda: TODAY)
    assert [
        (r.first, r.last, r.factor) for r in source.restorations(BBCA, newer[0], newer[-1])
    ] == [(newer[0], newer[-1], Decimal("1.100000"))]
    assert [
        (r.first, r.last, r.factor) for r in source.restorations(BBCA, older[0], older[-1])
    ] == [(older[0], older[4], Decimal("1.300000"))]  # 3,640 / 1.3 is whole: no evidence


def test_a_row_whose_volume_is_not_whole_stays_refused_though_its_prices_count() -> None:
    days = calendar().trading_days(date(2021, 3, 1), date(2021, 3, 9))
    rows = [
        scaled(day, price, volume=151 if day < days[5] else 200, split=2)
        for day, price in zip(days, TRUE, strict=False)
    ]
    history = YahooHistory("BBCA.JK", tuple(rows), ((date(2021, 6, 1), Decimal("2.0")),))
    runs = find_runs(evidence(history))
    assert [run.prices for run in runs if run.factor is not None] == [24]
    with pytest.raises(UnrecoverablePricesError) as refused:
        unadjust(history, BBCA, calendar(), (days[0], days[5]), runs)
    assert refused.value.days == tuple(days[:5])  # 151 / 2 is not whole; 200 / 2 is
    (bar,) = unadjust(history, BBCA, calendar(), (days[5], days[5]), runs)[0]
    assert (bar.close, bar.volume) == (rp(TRUE[5]), 100)


def test_a_failed_whole_history_read_fails_closed() -> None:
    history = history_from_json(BBRI_FIVE_YEARS)

    def refuse_whole(ticker: str, start: date, end: date) -> YahooHistory:
        del end
        if start == GRID_START:
            msg = f"{ticker}: the request to Yahoo failed: timeout"
            raise DataUnavailableError(msg)
        return history

    slept: list[float] = []
    source = YahooDataSource(
        calendar(), download=refuse_whole, sleep=slept.append, today=lambda: TODAY
    )
    with pytest.raises(
        DataUnavailableError,
        match=r"^BBRI\.JK: no data from Yahoo for 2014-01-06 to 2026-09-25 after 3 attempts",
    ):
        source.bars(BBRI, date(2021, 3, 1), date(2021, 3, 5))
    assert slept == [1.0, 1.0, 2.0]  # the pause after the range, then the backoff


BBRI_WHOLE = FIXTURES / "BBRI.JK_2014-01-06_2026-10-01.json"


def test_bbri_s_whole_recording_proves_one_factor_up_to_its_rights_issue() -> None:
    (run,) = find_runs(evidence(history_from_json(BBRI_WHOLE)))
    assert (run.first, run.last, len(run.days), run.prices, run.factor) == (
        date(2014, 1, 6),
        date(2021, 9, 7),
        1_845,
        7_380,
        Decimal("1.100019"),
    )


def test_bbri_s_2021_dividend_restores_to_what_bri_announced() -> None:
    history = history_from_json(BBRI_WHOLE)
    runs = find_runs(evidence(history))
    (dividend,) = actions_in(history, BBRI, date(2021, 4, 1), date(2021, 4, 30), runs)
    assert isinstance(dividend, CashDividend)
    assert dividend.per_share == Decimal("98.9057")
    assert abs(dividend.per_share - Decimal("98.905659443")) <= Decimal("0.0001")  # Liputan6


def test_bbri_s_golden_years_are_restored_except_where_a_volume_is_not_whole() -> None:
    # #160 spec §9.2: 1,103 days from 2017-01-31 to 2021-09-07 are evidence, a price off whole
    # rupiah on a day that is not a flat row with no volume (57 flat days there have one too); the
    # 153 before the 5-for-1 split of 2017-11-10 also have a volume that is not whole (#162).
    history = history_from_json(BBRI_WHOLE)
    runs = find_runs(evidence(history))
    span = (date(2017, 1, 31), date(2021, 9, 7))
    assert len([row for row in evidence(history) if span[0] <= row.day <= span[1]]) == 1_103
    with pytest.raises(UnrecoverablePricesError) as refused:
        unadjust(history, BBRI, calendar(), span, runs)
    assert (len(refused.value.days), refused.value.days[-1]) == (153, date(2017, 11, 9))
    bars, _ = unadjust(history, BBRI, calendar(), (date(2017, 11, 10), span[1]), runs)
    assert len(bars) == len(calendar().trading_days(date(2017, 11, 10), span[1]))


@pytest.mark.parametrize(
    "older", sorted(FIXTURES.glob("BBRI.JK_20[12]*.json")), ids=lambda p: p.stem
)
def test_bbri_s_whole_recording_agrees_with_every_older_recording(older: Path) -> None:
    whole = history_from_json(BBRI_WHOLE)
    rows = {row.day: row for row in whole.rows}
    recorded = history_from_json(older)
    assert recorded.splits == whole.splits
    assert all(rows[row.day] == row for row in recorded.rows)
    assert len(recorded.rows) > 40
