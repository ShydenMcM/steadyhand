"""The recorders' own entry points (#374): run by hand to refresh fixtures, so every line of them
is run here with the recording itself stood in; the CLI seed's real rebuild is in
``tests/integration/scripts/test_cli_seed_rebuilt.py``."""

import runpy
import sqlite3
import sys
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest
import record_cli_seed
import record_golden
import record_yahoo_fixture

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


@pytest.mark.parametrize(
    ("script", "argv"),
    [
        ("record_cli_seed.py", ["extra"]),
        ("record_golden.py", ["extra"]),
        ("record_yahoo_fixture.py", ["UNVR"]),
    ],
    ids=["cli-seed", "golden", "yahoo-fixture"],
)
def test_each_recorder_run_as_a_script_with_wrong_arguments_prints_its_usage(
    script: str,
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPTS / script), *argv])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(SCRIPTS / script), run_name="__main__")
    assert exited.value.code == 2
    assert f"uv run python scripts/{script}" in capsys.readouterr().out


def test_the_yahoo_recorder_records_the_range_it_is_given(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    asked: list[tuple[str, date, date]] = []

    def record(symbol: str, start: date, end: date) -> Path:
        asked.append((symbol, start, end))
        return Path("recorded.json")

    monkeypatch.setattr(record_yahoo_fixture, "record", record)
    assert record_yahoo_fixture.main(["UNVR", "2023-05-15", "2023-06-09"]) == 0
    assert asked == [("UNVR", date(2023, 5, 15), date(2023, 6, 9))]
    assert capsys.readouterr().out == "recorded.json\n"


def test_the_seed_recorder_records_when_given_no_arguments(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(record_cli_seed, "record", lambda: Path("seed.sql"))
    assert record_cli_seed.main([]) == 0
    assert capsys.readouterr().out == "seed.sql\n"


def test_the_seed_is_the_caches_rows_in_one_transaction_without_its_schema(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE bars (code TEXT)")
        db.execute("INSERT INTO bars VALUES ('BBCA')")
        db.commit()
    assert record_cli_seed.statements(path) == [
        "BEGIN;",
        "INSERT INTO \"bars\" VALUES('BBCA');",
        "COMMIT;",
    ]


def test_the_golden_recorder_records_all_three_goldens(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("record", "record_exempt", "record_growth"):
        monkeypatch.setattr(record_golden, name, lambda folder, name=name: f"{name}: {folder.name}")
    assert record_golden.main([]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "record: buy-and-hold",
        "record_exempt: exemption",
        "record_growth: dividend-growth",
    ]


def test_a_run_with_no_income_report_records_none() -> None:
    assert record_golden._income(None) is None
