"""The reader as CI's coverage job runs it (#384): a workflow, the run's jobs listing and the
trace folders in; a coverage.py-shaped report out, or a refusal naming what does not fit."""

import json
import runpy
import sys
from pathlib import Path

import pytest

from workflow_coverage import TRACING_SHELL, main

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/workflow_coverage.py"
SHA = "f" * 40
WORKFLOW = (
    "name: w\ndefaults:\n  run:\n    shell: '"
    + TRACING_SHELL.replace("'", "''")
    + "'\njobs:\n  a:\n    steps:\n      - run: |\n          echo one\n          echo two\n"
)
JOBS = {
    "total_count": 1,
    "jobs": [
        {
            "name": "a",
            "status": "completed",
            "conclusion": "success",
            "steps": [
                {"name": "Set up job", "status": "completed", "conclusion": "success"},
                {"name": "Run echo one", "status": "completed", "conclusion": "success"},
            ],
        }
    ],
}


def inputs(tmp_path: Path, workflow: str = WORKFLOW) -> list[str]:
    """The workflow, the jobs listing and two trace folders (one downloaded, one the job's own)
    written to *tmp_path*, as the reader's arguments."""
    (tmp_path / "w.yml").write_text(workflow, encoding="utf-8")
    (tmp_path / "jobs.json").write_text(json.dumps(JOBS), encoding="utf-8")
    downloaded = tmp_path / "traces/workflow-trace-a-0/a"
    downloaded.mkdir(parents=True)
    (downloaded / "__run").write_text(f"sha {SHA}\nlines 2\n1\n", encoding="utf-8")
    (tmp_path / "own").mkdir()
    return [
        "--workflow",
        str(tmp_path / "w.yml"),
        "--jobs",
        str(tmp_path / "jobs.json"),
        "--sha",
        SHA,
        "--traces",
        str(tmp_path / "traces"),
        "--traces",
        str(tmp_path / "own"),
        "--out",
        str(tmp_path / "out/report.json"),
    ]


def test_it_writes_which_lines_ran_and_prints_what_did_not(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(inputs(tmp_path), {}) == 0
    report = json.loads((tmp_path / "out/report.json").read_text(encoding="utf-8"))
    path = str(tmp_path / "w.yml")
    assert report == {
        "meta": {"sha": SHA, "workflow": path},
        "files": {path: {"executed_lines": [1, 2, 3, 4, 5, 6, 7, 8, 9], "missing_lines": [10]}},
    }
    assert capsys.readouterr().out == f"{path}: 9 of 10 lines ran; unrun: [10]\n"


def test_a_workflow_without_the_tracing_shell_is_refused_and_nothing_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    untraced = "name: w\njobs:\n  a:\n    steps:\n      - run: echo one\n"
    assert main(inputs(tmp_path, untraced), {}) == 1
    assert "does not set the tracing shell" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_it_runs_as_a_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), *inputs(tmp_path)])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exited.value.code == 0
    assert "9 of 10 lines ran" in capsys.readouterr().out


def test_the_jobs_own_traces_are_read_from_runner_temp(tmp_path: Path) -> None:
    """The coverage job's own steps' traces, found without any step's shell naming the folder."""
    argv = inputs(tmp_path)
    own = tmp_path / "temp/workflow-trace/a"
    own.mkdir(parents=True)
    (own / "__run").write_text(f"sha {SHA}\nlines 2\n2\n", encoding="utf-8")
    environ = {"RUNNER_TEMP": str(tmp_path / "temp"), "GITHUB_JOB": "a"}
    assert main([*argv, "--own-traces"], environ) == 0
    report = json.loads((tmp_path / "out/report.json").read_text(encoding="utf-8"))
    assert report["files"][str(tmp_path / "w.yml")]["missing_lines"] == []


def test_own_traces_without_runner_temp_are_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([*inputs(tmp_path), "--own-traces"], {"GITHUB_JOB": "a"}) == 1
    assert "RUNNER_TEMP is not set" in capsys.readouterr().err


def test_own_traces_without_github_job_are_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    environ = {"RUNNER_TEMP": str(tmp_path / "temp")}
    assert main([*inputs(tmp_path), "--own-traces"], environ) == 1
    assert "GITHUB_JOB is not set" in capsys.readouterr().err
