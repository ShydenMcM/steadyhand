"""Record one real Yahoo response as a test fixture (spec §10.3).

    uv run python scripts/record_yahoo_fixture.py BBCA 2021-09-01 2021-11-30

writes ``tests/fixtures/yahoo/BBCA.JK_2021-09-01_2021-11-30.json``: the rows exactly as Yahoo gave
them, plus the stock's split history. Tests replay it through the same conversion as live data.
Nothing is edited by hand, and a re-recording is reviewed like any other change.
"""

from __future__ import annotations

import sys
from datetime import date
from importlib.metadata import version
from pathlib import Path

from steadyhand_idx.yahoo import SUFFIX, Downloader, download_history, history_to_json

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "yahoo"


def fixture_path(symbol: str, start: date, end: date, folder: Path = FIXTURES) -> Path:
    return folder / f"{symbol}{SUFFIX}_{start.isoformat()}_{end.isoformat()}.json"


def record(
    symbol: str,
    start: date,
    end: date,
    *,
    folder: Path = FIXTURES,
    download: Downloader = download_history,
) -> Path:
    history = download(symbol + SUFFIX, start, end)
    source = (
        f"yfinance {version('yfinance')}: Ticker.history(auto_adjust=False, actions=True) "
        "and Ticker.splits"
    )
    path = fixture_path(symbol, start, end, folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    recorded = date.today()  # noqa: DTZ011 - the day of recording, a label for the reader
    path.write_text(history_to_json(history, recorded=recorded, source=source), encoding="utf-8")
    return path


def main(argv: list[str]) -> int:
    if len(argv) != 3:  # noqa: PLR2004 - symbol, start, end
        print(__doc__)
        return 2
    symbol, start, end = argv
    print(record(symbol, date.fromisoformat(start), date.fromisoformat(end)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
