"""Yahoo still answers the way the recorded fixtures say it did (spec §9.2).

Marked ``live``: it talks to Yahoo, so it never runs on a pull request. The yahoo-shape workflow,
started by hand since #220, runs it and opens an issue when it fails. The comparison is on the
UNADJUSTED result, so a split Yahoo applies after the recording does not break it; a changed format,
changed prices or a new unreported adjustment does. And a ticker Yahoo does not know is still
answered as a stock it cannot serve (#200), so a run goes on without it rather than stopping.
"""

import re
from datetime import date
from pathlib import Path

import pytest

from steadyhand import IDR, Instrument, StockUnavailableError
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.yahoo import (
    SUFFIX,
    UnrecoverablePricesError,
    YahooHistory,
    download_history,
    history_from_json,
    unadjust,
)

pytestmark = pytest.mark.live
FIXTURES = sorted((Path(__file__).resolve().parents[1] / "fixtures" / "yahoo").glob("*.json"))


def outcome(history: YahooHistory) -> object:
    """What the recording gives from the first year the holiday calendar covers: a recording of
    BBRI's whole history starts in 2014 (#160)."""
    calendar = IdxCalendar.shipped()
    first, last = max(history.rows[0].day, calendar.first_day), history.rows[-1].day
    instrument = Instrument(history.ticker.removesuffix(SUFFIX), "IDX", IDR)
    try:
        return unadjust(history, instrument, calendar, (first, last))
    except UnrecoverablePricesError as error:
        return error.days


# Measured on 2026-10-03 (#178): 14 recordings. Lower it only by a deliberate edit when a
# recording is retired.
RECORDINGS_FLOOR = 13


def test_there_are_fixtures_to_check() -> None:
    assert len(FIXTURES) >= RECORDINGS_FLOOR


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda path: path.stem)
def test_yahoo_still_gives_what_was_recorded(fixture: Path) -> None:
    recorded = history_from_json(fixture)
    live = download_history(recorded.ticker, recorded.rows[0].day, recorded.rows[-1].day)
    assert outcome(live) == outcome(recorded)


@pytest.mark.parametrize("ticker", ["SRIL.JK", "WSKT.JK"])
def test_a_ticker_yahoo_does_not_know_is_a_stock_it_cannot_serve(ticker: str) -> None:
    # Measured on 2026-10-04 (#200): Yahoo answers both with HTTP 404 for 2021-2025.
    failed = rf"^{re.escape(ticker)}: the request to Yahoo failed: HTTP Error 404"
    with pytest.raises(StockUnavailableError, match=failed):
        download_history(ticker, date(2021, 1, 4), date(2025, 12, 30))
