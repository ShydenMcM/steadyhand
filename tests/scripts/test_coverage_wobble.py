"""Two measured runs of one suite compared (#374): Shyden's ruling of 2026-10-22 (run-to-run
wobble is measured; a line whose coverage wobbles gets a fixed test). The properties suite draws
fresh random cases each run, so its CI step measures it twice and fails on any difference."""

import json
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest

from coverage_wobble import main, wobble


def report(lines: list[int], arms: list[list[int]]) -> dict[str, Any]:
    data = {
        "executed_lines": lines,
        "missing_lines": [],
        "excluded_lines": [],
        "executed_branches": arms,
        "missing_branches": [],
    }
    return {"meta": {"format": 3, "branch_coverage": True}, "files": {"a.py": data}}


def test_two_equal_runs_do_not_wobble() -> None:
    assert wobble(report([1, 2], [[1, 2]]), report([1, 2], [[1, 2]])) == []


@pytest.mark.parametrize(
    ("first", "second", "said"),
    [
        (report([1, 2], []), report([1], []), ["a.py: line 2 ran in one run only"]),
        (
            report([1], [[1, 2]]),
            report([1], [[1, 3]]),
            ["a.py: arm 1>2 ran in one run only", "a.py: arm 1>3 ran in one run only"],
        ),
        (
            report([1], []),
            {"meta": {"format": 3, "branch_coverage": True}, "files": {}},
            ["a.py: measured in one run only"],
        ),
    ],
    ids=["line", "arm", "file"],
)
def test_every_difference_between_two_runs_is_named(
    first: dict[str, Any], second: dict[str, Any], said: list[str]
) -> None:
    assert wobble(first, second) == said


def write(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_it_fails_naming_the_wobble(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    first = write(tmp_path / "a.json", report([1, 2], []))
    second = write(tmp_path / "b.json", report([1], []))
    assert main([str(first), str(second)]) == 1
    assert "a.py: line 2 ran in one run only" in capsys.readouterr().err


def test_it_passes_two_equal_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    first = write(tmp_path / "a.json", report([1], []))
    second = write(tmp_path / "b.json", report([1], []))
    assert main([str(first), str(second)]) == 0
    assert "the two runs measured the same" in capsys.readouterr().out


def test_an_unreadable_run_fails_closed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    first = write(tmp_path / "a.json", report([1], []))
    assert main([str(first), str(tmp_path / "missing.json")]) == 1
    assert "missing.json" in capsys.readouterr().err


def test_it_runs_as_a_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/coverage_wobble.py"
    first = write(tmp_path / "a.json", report([1], []))
    monkeypatch.setattr(sys, "argv", [str(script), str(first), str(first)])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(script), run_name="__main__")
    assert exited.value.code == 0
