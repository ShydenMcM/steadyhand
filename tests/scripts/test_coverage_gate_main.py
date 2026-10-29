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

from coverage_gate import (
    ISTANBUL_REPORTS,
    MEASURED_ONLY_BY,
    PYTHON_REPORTS,
    RECORD,
    GateError,
    Record,
    dump_record,
    load_record,
    main,
)

SHA = "a" * 40
HEAD = "b" * 40
OTHER = "c" * 40
WORKFLOW = ".github/workflows/ci.yml"
SHAPE = ".github/workflows/yahoo-shape.yml"
# The file only yahoo-shape's own run measures (MEASURED_ONLY_BY, #374 AC9).
LIVE = "tests/idx/test_yahoo_live.py"
# The logs suite's workflow owns every tracked code file under tests/logs (#336), read from git.
LOGS = ".github/workflows/logs.yml"
TRAIL = "tests/logs/test_trails.py"
TRAIL_HELPER = "tests/logs/trail_world.py"
# A code file of each language that no suite measures.
UNMEASURED = ("extension/c.ts", "tools/d.py")
TRACKED = [
    "scripts/a.py",
    "extension/b.ts",
    *UNMEASURED,
    WORKFLOW,
    SHAPE,
    LIVE,
    LOGS,
    TRAIL,
    TRAIL_HELPER,
    "tests/logs/README.md",
    "README.md",
]
CLEAN_RECORD = Record(files={"scripts/a.py": (1, 0)}, unmeasured=UNMEASURED)


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
    # Every suite's folder, as the coverage job downloads them; one of each kind holds data.
    empty_python = {"meta": {"format": 3, "branch_coverage": True}, "files": {}}
    for name in PYTHON_REPORTS:
        data = python_report() if name == "coverage-python" else empty_python
        write(reports / "coverage" / name / "coverage.json", json.dumps(data))
        write(
            reports / "coverage" / name / "sha.txt",
            f"{sha if name == 'coverage-python' else SHA}\n",
        )
    for name in ISTANBUL_REPORTS:
        data = istanbul_report(root) if name == "coverage-extension-unit" else {}
        write(reports / "coverage" / name / "coverage-final.json", json.dumps(data))
        write(reports / "coverage" / name / "sha.txt", f"{SHA}\n")
    write(reports / "workflows/ci.json", json.dumps(workflow_report()))
    argv = [
        "--sha",
        SHA,
        "--head-sha",
        HEAD,
        "--reports",
        str(reports / "coverage"),
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
    root, argv = tree(tmp_path, Record(files={}, unmeasured=UNMEASURED))
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
    (tmp_path / "reports/coverage/coverage-extension-unit/coverage-final.json").unlink()
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


@pytest.mark.parametrize("path", UNMEASURED)
def test_a_changed_line_in_an_unmeasured_file_fails(
    path: str,
    tmp_path: Path,
    stood_in: dict[str, Commands],
    capsys: pytest.CaptureFixture[str],
) -> None:
    stood_in["c"] = git(f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-o\n+x = 1\n")
    root, argv = tree(tmp_path)
    assert main(["--event", "pull_request", *argv], root) == 1
    assert f"{path}:1: changed in a file no suite measures" in capsys.readouterr().err


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
    carried = Record(files={"scripts/a.py": (1, 0), SHAPE: (11, 0)}, unmeasured=UNMEASURED)
    root, argv = tree(tmp_path, carried)
    assert main(["--event", "push", *argv], root) == 0


def test_a_hand_started_workflow_recorded_unmeasured_stays_so(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = git()
    carried = Record(files={"scripts/a.py": (1, 0)}, unmeasured=(*UNMEASURED, SHAPE))
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
    write(tmp_path / "reports/coverage/coverage-python/coverage.json", json.dumps(report))
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
    (tmp_path / "reports/coverage/coverage-python/sha.txt").unlink()
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
    stood_in["c"] = git(base=Record(files={}, unmeasured=UNMEASURED))
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
    base = Record(files={"scripts/old.py": (1, 0)}, unmeasured=UNMEASURED)
    stood_in["c"] = git(base=base, renames="R090\0scripts/old.py\0scripts/a.py\0")
    root, argv = tree(tmp_path)
    assert main(["--event", "pull_request", *argv], root) == 0


def test_reports_written_under_another_checkout_are_read_from_its_root(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    """The laptop reads CI's own reports, whose paths start with the runner's checkout."""
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    runner = "/home/runner/work/steadyhand/steadyhand"
    report = {
        key.replace(str(root), runner): entry | {"path": entry["path"].replace(str(root), runner)}
        for key, entry in istanbul_report(root).items()
    }
    write(
        tmp_path / "reports/coverage/coverage-extension-unit/coverage-final.json",
        json.dumps(report),
    )
    assert main(["--event", "push", *argv, "--report-root", runner], root) == 0


def test_a_suite_whose_report_is_missing_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    folder = tmp_path / "reports/coverage" / PYTHON_REPORTS[-1]
    for path in folder.iterdir():
        path.unlink()
    folder.rmdir()
    assert main(["--event", "push", *argv], root) == 1
    assert f"no report from {PYTHON_REPORTS[-1]}" in capsys.readouterr().err


def test_a_report_from_no_known_suite_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    """A suite's report the gate does not join would leave its measurement out unseen."""
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    write(tmp_path / "reports/coverage/coverage-python-stray/coverage.json", "{}")
    assert main(["--event", "push", *argv], root) == 1
    assert "coverage-python-stray" in capsys.readouterr().err


def test_no_reports_folder_at_all_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    argv[argv.index("--reports") + 1] = str(tmp_path / "nowhere")
    assert main(["--event", "push", *argv], root) == 1
    assert f"no report from {PYTHON_REPORTS[0]}" in capsys.readouterr().err


def test_a_suites_second_run_that_differs_where_no_other_runs_fails(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    """The properties suite is measured twice: a line only one of its runs took, where no other
    suite runs it, wobbles (Shyden 2026-10-22: a wobbling line gets a fixed test)."""
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    wobbly = python_report()
    wobbly["files"]["scripts/a.py"]["executed_lines"] = [1, 2, 3]
    wobbly["files"]["scripts/a.py"]["missing_lines"] = []
    write(
        tmp_path / "reports/coverage/coverage-python-properties-again/coverage.json",
        json.dumps(wobbly),
    )
    assert main(["--event", "push", *argv], root) == 1
    assert "wobble: scripts/a.py: statement 3 ran in one of two runs" in capsys.readouterr().err


def test_the_suite_run_twice_is_named_in_the_report_list() -> None:
    assert "coverage-python-properties-again" in PYTHON_REPORTS


def test_every_python_report_the_gate_waits_for_is_named() -> None:
    """Each a ci.yml upload; the measured perf run (#374 AC9) feeds the record too."""
    assert PYTHON_REPORTS == (
        "coverage-python",
        "coverage-python-guards",
        "coverage-python-integration",
        "coverage-python-perf",
        "coverage-python-properties",
        "coverage-python-properties-again",
    )


def lines(executed: list[int], missing: list[int]) -> dict[str, Any]:
    return {
        "executed_lines": executed,
        "missing_lines": missing,
        "excluded_lines": [],
        "executed_branches": [],
        "missing_branches": [],
    }


def measured_in_unit(tmp_path: Path, path: str, data: dict[str, Any]) -> None:
    """The unit report measures *path* too: a test module's import lines run when collected."""
    report = tmp_path / "reports/coverage/coverage-python/coverage.json"
    whole = json.loads(report.read_text(encoding="utf-8"))
    whole["files"][path] = data
    write(report, json.dumps(whole))


def live_run(
    tmp_path: Path,
    files: dict[str, dict[str, Any]],
    *,
    sha: str = HEAD,
    run: str = "7",
    trace: bool = True,
    workflow: str = SHAPE,
) -> None:
    """A hand-started workflow (yahoo-shape unless named) read from its run on the head, as
    workflow_runs.py writes it: its trace report and, one folder per run, its coverage report of
    the files only it measures."""
    stem = Path(workflow).stem
    folder = tmp_path / f"reports/workflows/{stem}-python" / run
    meta = {"format": 3, "branch_coverage": True}
    write(folder / "coverage.json", json.dumps({"meta": meta, "files": files}))
    write(folder / "sha.txt", f"{sha}\n")
    if trace:
        traced = {workflow: {"executed_lines": [1, 2, 3], "missing_lines": []}}
        report = {"meta": {"sha": HEAD, "workflow": workflow}, "files": traced}
        write(tmp_path / f"reports/workflows/{stem}.json", json.dumps(report))


def with_live(counts: tuple[int, int] | None) -> Record:
    files = {"scripts/a.py": (1, 0)} | ({} if counts is None else {LIVE: counts})
    return Record(files=files, unmeasured=UNMEASURED)


def test_the_live_check_and_the_logs_folder_are_what_only_hand_started_workflows_measure() -> None:
    assert MEASURED_ONLY_BY == {SHAPE: (LIVE,), LOGS: ("tests/logs/",)}


def test_a_changed_line_under_tests_logs_the_logs_run_ran_passes(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = git(f"--- a/{TRAIL}\n+++ b/{TRAIL}\n@@ -1 +1 @@\n-o\n+x = 1\n")
    root, argv = tree(tmp_path)
    trails = {TRAIL: lines([1, 2, 3], []), TRAIL_HELPER: lines([1, 2, 3], [])}
    live_run(tmp_path, trails, workflow=LOGS)
    assert main(["--event", "pull_request", *argv], root) == 0


def test_a_changed_line_under_tests_logs_with_no_logs_report_fails(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    """The logs suite runs on no pull request: only its run on the commit counts, never a line
    the unit report ran by importing the file."""
    stood_in["c"] = git(f"--- a/{TRAIL_HELPER}\n+++ b/{TRAIL_HELPER}\n@@ -1 +1 @@\n-o\n+x = 1\n")
    root, argv = tree(tmp_path)
    measured_in_unit(tmp_path, TRAIL_HELPER, lines([1, 2, 3], []))
    assert main(["--event", "pull_request", *argv], root) == 1
    assert f"{TRAIL_HELPER}:1: changed in a file no suite measures" in capsys.readouterr().err


def test_a_logs_report_missing_a_tracked_file_under_tests_logs_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    """The folder is read from git, so a file the run did not measure is named, never skipped."""
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    live_run(tmp_path, {TRAIL: lines([1, 2, 3], [])}, workflow=LOGS)
    assert main(["--event", "push", *argv], root) == 1
    assert f"does not measure {TRAIL_HELPER}" in capsys.readouterr().err


def test_a_logs_report_speaks_for_tests_logs_alone(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    """It runs lines of scripts/a.py too: counted, that file's record would swing between commits
    that ran the logs suite and commits that did not."""
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    trails = {TRAIL: lines([1, 2, 3], []), TRAIL_HELPER: lines([1, 2, 3], [])}
    live_run(tmp_path, {**trails, "scripts/a.py": lines([1, 2, 3], [])}, workflow=LOGS)
    assert main(["--event", "push", *argv], root) == 0


@pytest.mark.parametrize("recorded", [(14, 0), None])
def test_with_no_live_report_the_live_checks_recorded_counts_are_carried(
    tmp_path: Path, stood_in: dict[str, Commands], recorded: tuple[int, int] | None
) -> None:
    """The unit report runs its import lines only; what counts is the record, even a record of
    nothing untested, which must not let the unit report's count through (G17)."""
    stood_in["c"] = git()
    root, argv = tree(tmp_path, with_live(recorded))
    measured_in_unit(tmp_path, LIVE, lines([1, 2], [3]))
    assert main(["--event", "push", *argv], root) == 0


def test_with_no_live_report_a_live_check_recorded_unmeasured_stays_so(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(
        tmp_path, Record(files={"scripts/a.py": (1, 0)}, unmeasured=(*UNMEASURED, LIVE))
    )
    measured_in_unit(tmp_path, LIVE, lines([1, 2, 3], []))
    assert main(["--event", "push", *argv], root) == 0


def test_a_changed_line_in_the_live_check_with_no_live_report_fails(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    """Even a line the unit report ran: only a run of yahoo-shape on the commit counts (G19)."""
    stood_in["c"] = git(f"--- a/{LIVE}\n+++ b/{LIVE}\n@@ -1 +1 @@\n-o\n+x = 1\n")
    root, argv = tree(tmp_path)
    measured_in_unit(tmp_path, LIVE, lines([1, 2, 3], []))
    assert main(["--event", "pull_request", *argv], root) == 1
    assert f"{LIVE}:1: changed in a file no suite measures" in capsys.readouterr().err


def test_a_live_report_joins_the_unit_report_for_the_live_check(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    measured_in_unit(tmp_path, LIVE, lines([1], [2, 3]))
    live_run(tmp_path, {LIVE: lines([2, 3], [1])})
    assert main(["--event", "push", *argv], root) == 0


def test_a_live_report_that_runs_more_asks_for_it_to_be_recorded(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path, with_live((14, 0)))
    live_run(tmp_path, {LIVE: lines([1, 2, 3], [])})
    assert main(["--event", "push", *argv], root) == 1
    assert f"{LIVE}: untested statements fell from 14 to 0: record it" in capsys.readouterr().err


def test_a_changed_line_the_live_report_ran_passes(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = git(f"--- a/{LIVE}\n+++ b/{LIVE}\n@@ -1 +1 @@\n-o\n+x = 1\n")
    root, argv = tree(tmp_path)
    live_run(tmp_path, {LIVE: lines([1, 2, 3], [])})
    assert main(["--event", "pull_request", *argv], root) == 0


def test_a_live_report_speaks_for_the_live_check_alone(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    """It runs a line of scripts/a.py no pull request's suite runs: counted, that file's record
    would swing between commits that ran yahoo-shape and commits that did not (G14)."""
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    live_run(tmp_path, {LIVE: lines([1, 2, 3], []), "scripts/a.py": lines([1, 2, 3], [])})
    assert main(["--event", "push", *argv], root) == 0


def test_a_live_report_that_does_not_measure_the_live_check_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    live_run(tmp_path, {"scripts/a.py": lines([1, 2, 3], [])})
    assert main(["--event", "push", *argv], root) == 1
    assert f"does not measure {LIVE}" in capsys.readouterr().err


@pytest.mark.parametrize("sha", [SHA, OTHER])
def test_a_live_report_from_any_commit_but_the_head_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str], sha: str
) -> None:
    """yahoo-shape runs on the pull request's head, never its merge commit (G13)."""
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    live_run(tmp_path, {LIVE: lines([1, 2, 3], [])}, sha=sha)
    assert main(["--event", "push", *argv], root) == 1
    assert f"is from commit {sha}" in capsys.readouterr().err


def test_a_folder_of_no_workflow_beside_the_workflow_reports_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    (tmp_path / "reports/workflows/stray").mkdir()
    assert main(["--event", "push", *argv], root) == 1
    assert "folders of no workflow that measures files of its own: ['stray']" in (
        capsys.readouterr().err
    )


def test_a_live_folder_holding_no_runs_report_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    live_run(tmp_path, {LIVE: lines([1, 2, 3], [])})
    for path in (tmp_path / "reports/workflows/yahoo-shape-python/7").iterdir():
        path.unlink()
    (tmp_path / "reports/workflows/yahoo-shape-python/7").rmdir()
    assert main(["--event", "push", *argv], root) == 1
    assert "yahoo-shape-python holds no run's report" in capsys.readouterr().err


def test_yahoo_shape_read_without_its_coverage_report_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    """workflow_runs.py writes both or fails: half of them is a broken input (G18)."""
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    live_run(tmp_path, {LIVE: lines([1, 2, 3], [])})
    for path in (tmp_path / "reports/workflows/yahoo-shape-python/7").iterdir():
        path.unlink()
    for folder in ("yahoo-shape-python/7", "yahoo-shape-python"):
        (tmp_path / "reports/workflows" / folder).rmdir()
    assert main(["--event", "push", *argv], root) == 1
    assert f"{SHAPE} was read from its run without its coverage report" in capsys.readouterr().err


def test_a_coverage_report_of_yahoo_shape_without_its_run_read_fails_closed(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = git()
    root, argv = tree(tmp_path)
    live_run(tmp_path, {LIVE: lines([1, 2, 3], [])}, trace=False)
    assert main(["--event", "push", *argv], root) == 1
    assert f"a coverage report of {SHAPE} without its run read" in capsys.readouterr().err
