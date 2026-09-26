"""The fixture recorder writes exactly what the conversion reads back."""

from datetime import date
from pathlib import Path

import pytest
import record_yahoo_fixture

from steadyhand_idx.yahoo import YahooHistory, history_from_json

RECORDED = Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"
UNVR = RECORDED / "UNVR.JK_2023-05-15_2023-06-09.json"


def test_the_file_name_carries_the_ticker_and_range(tmp_path: Path) -> None:
    path = record_yahoo_fixture.fixture_path("UNVR", date(2023, 5, 15), date(2023, 6, 9), tmp_path)
    assert path == tmp_path / "UNVR.JK_2023-05-15_2023-06-09.json"


def test_a_recording_reads_back_as_the_history_it_was_given(tmp_path: Path) -> None:
    history = history_from_json(UNVR)
    asked: list[tuple[str, date, date]] = []

    def download(ticker: str, start: date, end: date) -> YahooHistory:
        asked.append((ticker, start, end))
        return history

    before = date.today()  # noqa: DTZ011 - brackets the recorder's own date.today()
    path = record_yahoo_fixture.record(
        "UNVR", date(2023, 5, 15), date(2023, 6, 9), folder=tmp_path / "new", download=download
    )
    after = date.today()  # noqa: DTZ011
    assert asked == [("UNVR.JK", date(2023, 5, 15), date(2023, 6, 9))]
    assert history_from_json(path) == history
    text = path.read_text(encoding="utf-8")
    assert '"source": "yfinance ' in text
    assert any(f'"recorded": "{day.isoformat()}"' in text for day in {before, after})


def test_usage_is_printed_for_the_wrong_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert record_yahoo_fixture.main(["UNVR"]) == 2
    assert "record_yahoo_fixture.py BBCA 2021-09-01 2021-11-30" in capsys.readouterr().out
