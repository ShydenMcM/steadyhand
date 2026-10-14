"""Yahoo's pandas frames convert to exactly what was recorded (moved out of unit by #292).

These build the real pandas objects ``yfinance`` returns. With them and pandas in it,
``tests/idx/test_yahoo.py`` took 0.67 s of CPU to load (measured 2026-10-13), over the unit load
limit of 0.1 s; without them, 0.08 s. The unit suite keeps a stand-in of each, of the same name, on
three made-up rows in frames of plain Python with the same shape (``tests/idx/test_yahoo.py``,
``Frame``): the same conversion, refusals and dropped rows.
"""

from pathlib import Path

import pandas as pd
import pytest

from steadyhand import DataUnavailableError
from steadyhand_idx.yahoo import YahooHistory, history_from_frames, history_from_json

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "yahoo"
BBCA_FILE = FIXTURES / "BBCA.JK_2021-09-01_2021-11-30.json"
BBRI_FILE = FIXTURES / "BBRI.JK_2021-08-02_2021-09-30.json"
UNVR_FILE = FIXTURES / "UNVR.JK_2023-05-15_2023-06-09.json"


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
