"""The coverage gate as CI's coverage job runs it (#381): every suite's report and the committed
record in, a verdict out, or, for the record run, the measured record written. A unit test starts
no process, so git is answered here (``stood_in_commands``)."""

import json
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest
from stood_in_commands import Commands, stand_in

from coverage_gate import RECORD, GateError, Record, dump_record, load_record, main

SHA = "a" * 40
HEAD = "b" * 40
OTHER = "c" * 40
WORKFLOW = ".github/workflows/ci.yml"
SHAPE = ".github/workflows/yahoo-shape.yml"
TRACKED = ["scripts/a.py", "extension/b.ts", "extension/c.ts", WORKFLOW, SHAPE, "README.md"]
CLEAN_RECORD = Record(files={"scripts/a.py": (1, 0)}, unmeasured=("extension/c.ts",))


def python_report() -> dict[str, Any]:
    data = {
        "executed_lines": [1, 2],
        "missing_lines": [3],
        "excluded_lines": [],
        "executed_branches": [[1, 2]],
        "missing_branches": [],
    }
    return {"meta": {"format": 3, "branch_coverage": True}, "files": {"scripts/a.py": data}}


def istanbul_report(root: Path) -> dict[str, Any]:
    where = {"start": {"line": 1, "column": 0}, "end": {"line": 1, "column": 5}}
    path = f"{root}/extension/b.ts"
    entry = {"path": path, "statementMap": {"0": where}, "s": {"0": 1}, "branchMap": {}, "b": {}}
    return {path: entry}


def workflow_report(sha: str = SHA) -> dict[str, Any]:
    return {
        "meta": {"sha": sha, "workflow": WORKFLOW},
        "files": {WORKFLOW: {"executed_lines": [1, 2], "missing_lines": []}},
    }


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def tree(tmp_path: Path, record: Record = CLEAN_RECORD, sha: str = SHA) -> tuple[Path, list[str]]:
    """A repository with its files and record, and the reports of one run, as the arguments."""
    root = tmp_path / "repo"
    for path in TRACKED:
        write(root / path, "x = 1\ny = 2\nz = 3\n")
    write(root / RECORD, dump_record(record))
    reports = tmp_path / "reports"
    write(reports / "py312/coverage.json", json.dumps(python_report()))
    write(reports / "py312/sha.txt", f"{sha}\n")
    write(reports / "unit/coverage-final.json", json.dumps(istanbul_report(root)))
    write(reports / "unit/sha.txt", f"{SHA}\n")
    write(reports / "workflows/ci.json", json.dumps(workflow_report()))
    argv = [
        "--sha",
        SHA,
        "--head-sha",
        HEAD,
        "--python",
        str(reports / "py312"),
        "--istanbul",
        str(reports / "unit"),
        "--workflow",
        str(reports / "workflows"),
    ]
    return root, argv


def git(diff: str = "", base: Record | None = CLEAN_RECORD, renames: str = "") -> Commands:
    """git as the coverage job meets it: the tracked files, the merge commit's diff, the base
    branch's record (None: the base has none) and the renames."""
    listing = "".join(f"{path}\0" for path in [*TRACKED, RECORD]).encode()
    answers = {
        ("git", "ls-files"): listing,
        ("git", "diff", "-U0"): diff.encode(),
        ("git", "diff", "--name-status"): renames.encode(),
        ("git", "ls-tree"): b"" if base is None else f"{RECORD}\n".encode(),
    }
    if base is not None:
        answers["git", "show"] = dump_record(base).encode()
    return Commands(answers=answers)


@pytest.fixture
def stood_in(monkeypatch: pytest.MonkeyPatch) -> dict[str, Commands]:
    return stand_in(monkeypatch)


def test_a_run_that_matches_the_record_passes_and_shows_the_percentages(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    assert main(["--event", "push", *argv], root) == 0
    out = capsys.readouterr().out
    assert "statements 83.33% (5 of 6), branch arms 100.00% (1 of 1)" in out
    assert "matches the record" in out


def test_a_rise_fails_naming_it(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path, Record(files={}, unmeasured=("extension/c.ts",)))
    assert main(["--event", "push", *argv], root) == 1
    assert "scripts/a.py: untested statements rose from 0 to 1" in capsys.readouterr().err


def test_the_record_run_writes_the_measured_record_and_never_fails(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path, Record(files={}, unmeasured=()))
    out = tmp_path / "record.json"
    assert main(["--event", "push", *argv, "--write-record", str(out)], root) == 0
    assert load_record(out.read_text(encoding="utf-8")) == CLEAN_RECORD
    assert "scripts/a.py: untested statements rose from 0 to 1" in capsys.readouterr().out


def test_a_report_from_another_commit_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path, sha=OTHER)
    assert main(["--event", "push", *argv], root) == 1
    assert f"is from commit {OTHER}" in capsys.readouterr().err


def test_a_missing_report_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    (tmp_path / "reports/unit/coverage-final.json").unlink()
    assert main(["--event", "push", *argv], root) == 1
    assert "coverage-final.json" in capsys.readouterr().err


def test_a_workflow_report_of_the_pull_requests_head_is_accepted(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    """A hand-started workflow runs on the pull request's head, not its merge commit (#384)."""
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    write(
        tmp_path / "reports/workflows/shape.json", json.dumps(workflow_report(HEAD) | {"files": {}})
    )
    assert main(["--event", "push", *argv], root) == 0


def test_a_workflow_report_of_another_commit_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    write(tmp_path / "reports/workflows/ci.json", json.dumps(workflow_report(OTHER)))
    assert main(["--event", "push", *argv], root) == 1
    assert f"is from commit {OTHER}" in capsys.readouterr().err


def test_a_pull_request_fails_on_a_changed_line_no_test_ran(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git("--- a/scripts/a.py\n+++ b/scripts/a.py\n@@ -3 +3 @@\n-old\n+new\n")
    root, argv = tree(tmp_path)
    assert main(["--event", "pull_request", *argv], root) == 1
    assert "scripts/a.py:3: changed, but no test ran it" in capsys.readouterr().err


def test_a_pull_request_reads_the_merge_commits_own_diff(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    main(["--event", "pull_request", *argv], root)
    diff = next(call for call in stood_in["c"].calls if call[1:2] == ["diff"])
    assert diff[1:] == ["diff", "-U0", "--no-color", "--no-ext-diff", "-M", "HEAD^1", "HEAD"]


def test_a_changed_line_in_an_unmeasured_file_fails(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git("--- a/extension/c.ts\n+++ b/extension/c.ts\n@@ -1 +1 @@\n-o\n+x = 1\n")
    root, argv = tree(tmp_path)
    assert main(["--event", "pull_request", *argv], root) == 1
    assert "extension/c.ts:1: changed in a file no suite measures" in capsys.readouterr().err


def test_a_changed_line_in_a_hand_started_workflow_with_no_report_fails(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git(f"--- a/{SHAPE}\n+++ b/{SHAPE}\n@@ -1 +1 @@\n-o\n+x = 1\n")
    root, argv = tree(tmp_path)
    assert main(["--event", "pull_request", *argv], root) == 1
    assert f"{SHAPE}:1: changed in a file no suite measures" in capsys.readouterr().err


def test_a_hand_started_workflow_with_no_report_carries_its_record(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = git()
    carried = Record(files={"scripts/a.py": (1, 0), SHAPE: (11, 0)}, unmeasured=("extension/c.ts",))
    root, argv = tree(tmp_path, carried)
    assert main(["--event", "push", *argv], root) == 0


def test_a_hand_started_workflow_recorded_unmeasured_stays_so(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = git()
    carried = Record(files={"scripts/a.py": (1, 0)}, unmeasured=("extension/c.ts", SHAPE))
    root, argv = tree(tmp_path, carried)
    assert main(["--event", "push", *argv], root) == 0


def test_a_coverage_ignore_hint_fails(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    write(root / "extension/c.ts", "/* v8 ignore next */\nlet a = 1;\n")
    assert main(["--event", "push", *argv], root) == 1
    assert "extension/c.ts:1: /* v8 ignore next */" in capsys.readouterr().err


def test_a_measured_file_git_does_not_list_is_refused(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    report = python_report()
    # Fully run, so only the refusal itself can name it (no record difference would).
    report["files"]["scripts/stray.py"] = {
        "executed_lines": [1],
        "missing_lines": [],
        "excluded_lines": [],
        "executed_branches": [],
        "missing_branches": [],
    }
    write(tmp_path / "reports/py312/coverage.json", json.dumps(report))
    assert main(["--event", "push", *argv], root) == 1
    assert "measure files git does not list: ['scripts/stray.py']" in capsys.readouterr().err


@pytest.mark.parametrize(
    "text",
    [
        "[]",
        '{"files": {}}',
        '{"files": {"a.py": [1]}, "unmeasured": []}',
        '{"files": {"a.py": [-1, 0]}, "unmeasured": []}',
        '{"files": {"a.py": [0, 0]}, "unmeasured": []}',
        '{"files": {}, "unmeasured": ["b.ts", "a.ts"]}',
        '{"files": {}, "unmeasured": [1]}',
        "not json",
    ],
    ids=[
        "a-list",
        "no-unmeasured",
        "one-count",
        "negative",
        "zero-entry",
        "unsorted",
        "not-a-path",
        "not-json",
    ],
)
def test_a_record_that_does_not_read_is_refused(text: str) -> None:
    with pytest.raises(GateError, match="record"):
        load_record(text)


def test_a_record_reads_back_what_was_written() -> None:
    record = Record(files={"b.py": (0, 2), "a.py": (1, 0)}, unmeasured=("x.ts",))
    assert load_record(dump_record(record)) == record
    assert dump_record(record).index('"a.py"') < dump_record(record).index('"b.py"')


def test_it_runs_as_a_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    script = Path(__file__).resolve().parents[2] / "scripts/coverage_gate.py"
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", [str(script), "--event", "push", *argv])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(script), run_name="__main__")
    assert exited.value.code == 0


def test_a_report_naming_no_commit_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    (tmp_path / "reports/py312/sha.txt").unlink()
    assert main(["--event", "push", *argv], root) == 1
    assert "names no commit" in capsys.readouterr().err


def test_a_difference_prints_the_measured_record_to_fold_in(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    """The coverage job keeps nothing after its last step, so CI's measured record is printed
    for the laptop to fold into the commit ("CI records, laptop commits")."""
    stood_in["c"] = git()
    root, argv = tree(tmp_path, Record(files={}, unmeasured=()))
    assert main(["--event", "push", *argv], root) == 1
    out = capsys.readouterr().out
    printed = out.split("the measured record, to fold into tests/coverage_record.json:\n", 1)[1]
    assert load_record(printed) == CLEAN_RECORD


def test_a_pull_request_whose_record_rises_above_the_bases_fails(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    """Re-making the record to match a worse measurement does not get past the base's."""
    stood_in["c"] = git(base=Record(files={}, unmeasured=("extension/c.ts",)))
    root, argv = tree(tmp_path)
    assert main(["--event", "pull_request", *argv], root) == 1
    assert "scripts/a.py: untested statements would rise from 0 to 1" in capsys.readouterr().err


def test_the_records_first_pull_request_has_no_base_to_keep_to(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git(base=None)
    root, argv = tree(tmp_path)
    assert main(["--event", "pull_request", *argv], root) == 0
    assert "the base has no tests/coverage_record.json yet" in capsys.readouterr().out


def test_a_rename_keeps_the_bases_counts(tmp_path: Path, stood_in: dict[str, Commands]) -> None:
    base = Record(files={"scripts/old.py": (1, 0)}, unmeasured=("extension/c.ts",))
    stood_in["c"] = git(base=base, renames="R090\0scripts/old.py\0scripts/a.py\0")
    root, argv = tree(tmp_path)
    assert main(["--event", "pull_request", *argv], root) == 0
