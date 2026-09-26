"""Yahoo still answers the way the recorded fixtures say it did (spec §9.2).

Marked ``live``: it talks to Yahoo, so it never runs on a pull request. The daily yahoo-shape
workflow runs it and opens an issue when it fails. The comparison is on the UNADJUSTED result,
so a split Yahoo applies after the recording does not break it; a changed format, changed
prices or a new unreported adjustment does.
"""

from pathlib import Path

import pytest

from steadyhand import IDR, Instrument
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
    first, last = history.rows[0].day, history.rows[-1].day
    instrument = Instrument(history.ticker.removesuffix(SUFFIX), "IDX", IDR)
    try:
        return unadjust(history, instrument, IdxCalendar.shipped(), first, last)
    except UnrecoverablePricesError as error:
        return error.days


def test_there_are_fixtures_to_check() -> None:
    assert len(FIXTURES) >= 3


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda path: path.stem)
def test_yahoo_still_gives_what_was_recorded(fixture: Path) -> None:
    recorded = history_from_json(fixture)
    live = download_history(recorded.ticker, recorded.rows[0].day, recorded.rows[-1].day)
    assert outcome(live) == outcome(recorded)
