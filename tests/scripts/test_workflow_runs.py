"""The hand-started workflows a pull request changes, read from their runs on its commit (#384).

Shyden, 2026-10-22: "Run them on the PR commit", then "Scratch branch": the commit is pushed to
``coverage/<branch>`` (which starts no CI) and each changed hand-started workflow is started there.
A unit test starts no process, so every ``gh`` and ``git`` call is answered here.
"""

import json
import runpy
import sys
from pathlib import Path

import pytest
from stood_in_commands import Commands, stand_in

from workflow_coverage import TRACING_SHELL
from workflow_runs import main

HEAD = "c" * 40
OTHER = "d" * 40
BRANCH = "coverage/384/x"
SLUG = "o/r"
SHAPE = ".github/workflows/yahoo-shape.yml"
# The file only yahoo-shape measures (coverage_gate.MEASURED_ONLY_BY), and its report as kept.
LIVE = "tests/idx/test_yahoo_live.py"
LIVE_REPORT = "coverage-python-yahoo-shape/coverage.json"
# Lines 2-4: the tracing shell every workflow sets (YAML single quotes double a quote).
TRACED = "name: s\ndefaults:\n  run:\n    shell: '" + TRACING_SHELL.replace("'", "''") + "'\n"
SHAPE_TEXT = TRACED + "jobs:\n  shape:\n    steps:\n      - run: echo hi\n"
TRACE = f"sha {HEAD}\nlines 1\n1\n"


def jobs_payload(conclusion: str = "success") -> bytes:
    step = {"name": "Run echo hi", "status": "completed", "conclusion": conclusion}
    setup = {"name": "Set up job", "status": "completed", "conclusion": "success"}
    job = {"name": "shape", "status": "completed", "conclusion": "success", "steps": [setup, step]}
    return json.dumps({"total_count": 1, "jobs": [job]}).encode()


def runs_listing(*ids: int) -> bytes:
    return json.dumps({"total_count": len(ids), "workflow_runs": [{"id": i} for i in ids]}).encode()


def repo_with(tmp_path: Path, text: str = SHAPE_TEXT) -> Path:
    path = tmp_path / SHAPE
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return tmp_path


def standard(changed: bytes = SHAPE.encode() + b"\0", head_text: str = SHAPE_TEXT) -> Commands:
    return Commands(
        answers={
            ("git", "diff"): changed,
            ("git", "show"): head_text.encode(),
            ("gh", "api", f"repos/{SLUG}/actions/workflows/yahoo-shape.yml/runs"): runs_listing(7),
            ("gh", "api", f"repos/{SLUG}/actions/runs/7/jobs"): jobs_payload(),
        },
        downloads={"7": {"workflow-trace-shape-0/shape/__run": TRACE, LIVE_REPORT: '{"run": 7}'}},
    )


@pytest.fixture
def stood_in(monkeypatch: pytest.MonkeyPatch) -> dict[str, Commands]:
    return stand_in(monkeypatch)


def run_main(repo: Path, out: Path) -> int:
    argv = ["--event", "pull_request", "--repo", SLUG, "--branch", BRANCH, "--sha", HEAD]
    return main([*argv, "--out", str(out)], repo)


def test_a_changed_hand_started_workflow_is_read_from_its_run_on_the_commit(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = standard()
    repo = repo_with(tmp_path / "repo")
    assert run_main(repo, tmp_path / "out") == 0
    report = json.loads((tmp_path / "out/yahoo-shape.json").read_text(encoding="utf-8"))
    assert report == {
        "meta": {"sha": HEAD, "workflow": SHAPE, "runs": [7]},
        "files": {SHAPE: {"executed_lines": [1, 2, 3, 4, 5, 6, 7, 8], "missing_lines": []}},
    }


def test_it_asks_for_runs_of_that_workflow_on_the_scratch_branch_at_the_commit(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = standard()
    run_main(repo_with(tmp_path / "repo"), tmp_path / "out")
    listing = next(
        call for call in stood_in["c"].calls if call[1:2] == ["api"] and "runs?" in call[2]
    )
    assert listing[2] == (
        f"repos/{SLUG}/actions/workflows/yahoo-shape.yml/runs"
        f"?branch={BRANCH}&head_sha={HEAD}&status=completed&per_page=100"
    )


def test_the_changed_files_come_from_the_merge_commits_two_parents(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = standard()
    run_main(repo_with(tmp_path / "repo"), tmp_path / "out")
    diff = next(call for call in stood_in["c"].calls if call[1:2] == ["diff"])
    assert diff[1:] == [
        "diff",
        "--name-only",
        "--diff-filter=d",
        "-z",
        "HEAD^1",
        "HEAD",
        "--",
        ".github/workflows/",
        LIVE,
        "tests/logs/",
    ]


def test_ci_itself_and_unchanged_workflows_need_no_other_run(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = Commands(answers={("git", "diff"): b".github/workflows/ci.yml\0"})
    assert run_main(repo_with(tmp_path / "repo"), tmp_path / "out") == 0
    assert [call[1] for call in stood_in["c"].calls] == ["diff"]


def test_a_changed_workflow_with_no_run_on_the_commit_fails_naming_how_to_start_it(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands = standard()
    commands.answers[("gh", "api", f"repos/{SLUG}/actions/workflows/yahoo-shape.yml/runs")] = (
        runs_listing()
    )
    stood_in["c"] = commands
    assert run_main(repo_with(tmp_path / "repo"), tmp_path / "out") == 1
    err = capsys.readouterr().err
    assert "no completed run of .github/workflows/yahoo-shape.yml" in err
    assert f"git push origin HEAD:refs/heads/{BRANCH}" in err
    assert f"gh workflow run yahoo-shape.yml --ref {BRANCH}" in err


def test_a_workflow_that_differs_from_the_pull_requests_own_is_refused(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = standard(head_text=SHAPE_TEXT + "# develop changed it too\n")
    assert run_main(repo_with(tmp_path / "repo"), tmp_path / "out") == 1
    assert "differs from the pull request's own" in capsys.readouterr().err


def test_runs_of_the_same_commit_join(tmp_path: Path, stood_in: dict[str, Commands]) -> None:
    text = (
        TRACED + "jobs:\n  shape:\n    steps:\n      - run: |\n          echo a\n          echo b\n"
    )
    commands = standard(head_text=text)
    listing = ("gh", "api", f"repos/{SLUG}/actions/workflows/yahoo-shape.yml/runs")
    commands.answers[listing] = runs_listing(7, 8)
    payload = json.loads(jobs_payload())
    payload["jobs"][0]["steps"][1]["name"] = "Run echo a"
    commands.answers[("gh", "api", f"repos/{SLUG}/actions/runs/7/jobs")] = json.dumps(
        payload
    ).encode()
    commands.answers[("gh", "api", f"repos/{SLUG}/actions/runs/8/jobs")] = json.dumps(
        payload
    ).encode()
    commands.downloads = {
        "7": {"workflow-trace-shape-0/shape/__run": f"sha {HEAD}\nlines 2\n1\n", LIVE_REPORT: "7"},
        "8": {"workflow-trace-shape-0/shape/__run": f"sha {HEAD}\nlines 2\n2\n", LIVE_REPORT: "8"},
    }
    stood_in["c"] = commands
    assert run_main(repo_with(tmp_path / "repo", text), tmp_path / "out") == 0
    report = json.loads((tmp_path / "out/yahoo-shape.json").read_text(encoding="utf-8"))
    assert report["files"][SHAPE] == {
        "executed_lines": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "missing_lines": [],
    }
    assert report["meta"]["runs"] == [7, 8]
    # Every run's coverage report is kept, none dropped (G12).
    kept = tmp_path / "out/yahoo-shape-python"
    assert [(kept / f"{run}/coverage.json").read_text(encoding="utf-8") for run in (7, 8)] == [
        "7",
        "8",
    ]


def test_a_trace_from_another_commit_fails(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands = standard()
    commands.downloads = {
        "7": {"workflow-trace-shape-0/shape/__run": f"sha {OTHER}\nlines 1\n1\n", LIVE_REPORT: "{}"}
    }
    stood_in["c"] = commands
    assert run_main(repo_with(tmp_path / "repo"), tmp_path / "out") == 1
    assert OTHER in capsys.readouterr().err


def test_a_failing_gh_call_fails_naming_it(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands = standard()
    commands.failing = ("gh", "run", "download")
    stood_in["c"] = commands
    assert run_main(repo_with(tmp_path / "repo"), tmp_path / "out") == 1
    assert "gh run download 7 failed: HTTP 404" in capsys.readouterr().err


def test_a_listing_that_reads_fewer_runs_than_it_counts_is_refused(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands = standard()
    listing = json.dumps({"total_count": 101, "workflow_runs": [{"id": 7}]}).encode()
    commands.answers[("gh", "api", f"repos/{SLUG}/actions/workflows/yahoo-shape.yml/runs")] = (
        listing
    )
    stood_in["c"] = commands
    assert run_main(repo_with(tmp_path / "repo"), tmp_path / "out") == 1
    assert "counts 101 runs but 1 were read" in capsys.readouterr().err


def test_a_missing_tool_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert run_main(repo_with(tmp_path / "repo"), tmp_path / "out") == 1
    assert "git is not on the path" in capsys.readouterr().err


def test_a_changed_workflow_without_the_tracing_shell_is_refused(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    untraced = "name: s\njobs:\n  shape:\n    steps:\n      - run: echo hi\n"
    stood_in["c"] = standard(head_text=untraced)
    assert run_main(repo_with(tmp_path / "repo", untraced), tmp_path / "out") == 1
    assert "does not set the tracing shell" in capsys.readouterr().err


def test_a_push_has_no_pull_request_to_read_for(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    stood_in["c"] = Commands(answers={})
    argv = ["--event", "push", "--repo", SLUG, "--branch", "coverage/", "--sha", HEAD]
    assert main([*argv, "--out", str(tmp_path / "out")], repo_with(tmp_path / "repo")) == 0
    assert stood_in["c"].calls == []
    assert "push: no pull request" in capsys.readouterr().out


def test_it_runs_as_a_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/workflow_runs.py"
    argv = ["--event", "push", "--repo", SLUG, "--branch", "coverage/", "--sha", HEAD]
    monkeypatch.setattr(sys, "argv", [str(script), *argv, "--out", str(tmp_path)])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(script), run_name="__main__")
    assert exited.value.code == 0
    assert "push: no pull request" in capsys.readouterr().out


def test_a_change_to_a_file_only_the_workflow_measures_reads_its_run_and_report(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    """The live test changed, yahoo-shape did not: its run on the commit is read all the same,
    its trace and its coverage report (#374 AC9, "Same as workflows"; G10)."""
    stood_in["c"] = standard(changed=LIVE.encode() + b"\0")
    assert run_main(repo_with(tmp_path / "repo"), tmp_path / "out") == 0
    assert json.loads((tmp_path / "out/yahoo-shape.json").read_text(encoding="utf-8"))["meta"] == {
        "sha": HEAD,
        "workflow": SHAPE,
        "runs": [7],
    }
    kept = tmp_path / "out/yahoo-shape-python/7/coverage.json"
    assert kept.read_text(encoding="utf-8") == '{"run": 7}'


def test_the_workflow_and_a_file_it_measures_both_changed_read_it_once(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = standard(changed=f"{SHAPE}\0{LIVE}\0".encode())
    assert run_main(repo_with(tmp_path / "repo"), tmp_path / "out") == 0
    listings = [
        call for call in stood_in["c"].calls if "workflows/yahoo-shape.yml/runs" in call[-1]
    ]
    assert len(listings) == 1


def test_the_coverage_report_is_downloaded_by_its_name(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = standard()
    run_main(repo_with(tmp_path / "repo"), tmp_path / "out")
    named = [call for call in stood_in["c"].calls if "--name" in call]
    assert [call[call.index("--name") + 1] for call in named] == ["coverage-python-yahoo-shape"]


def test_a_run_that_kept_no_coverage_report_fails_naming_it(
    tmp_path: Path, stood_in: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    """The live check failed, so its measured step never ran and kept nothing (G11)."""
    commands = standard()
    commands.downloads = {"7": {"workflow-trace-shape-0/shape/__run": TRACE}}
    stood_in["c"] = commands
    assert run_main(repo_with(tmp_path / "repo"), tmp_path / "out") == 1
    assert "no artifact matches" in capsys.readouterr().err


def test_a_workflow_measuring_no_file_of_its_own_downloads_no_report(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    other = ".github/workflows/record-floors.yml"
    commands = standard(changed=other.encode() + b"\0")
    commands.answers[("gh", "api", f"repos/{SLUG}/actions/workflows/record-floors.yml/runs")] = (
        runs_listing(7)
    )
    stood_in["c"] = commands
    repo = tmp_path / "repo"
    (repo / ".github/workflows").mkdir(parents=True)
    (repo / other).write_text(SHAPE_TEXT, encoding="utf-8")
    assert run_main(repo, tmp_path / "out") == 0
    assert not [call for call in stood_in["c"].calls if "--name" in call]
    assert not (tmp_path / "out/record-floors-python").exists()


LOGS = ".github/workflows/logs.yml"


def logs_commands(changed: bytes) -> Commands:
    """git and gh as a pull request changing a file under tests/logs meets them (#336)."""
    return Commands(
        answers={
            ("git", "diff"): changed,
            ("git", "show"): SHAPE_TEXT.encode(),
            ("gh", "api", f"repos/{SLUG}/actions/workflows/logs.yml/runs"): runs_listing(9),
            ("gh", "api", f"repos/{SLUG}/actions/runs/9/jobs"): jobs_payload(),
        },
        downloads={
            "9": {
                "workflow-trace-shape-0/shape/__run": TRACE,
                "coverage-python-logs/coverage.json": '{"run": 9}',
            }
        },
    )


def logs_repo(tmp_path: Path) -> Path:
    path = tmp_path / LOGS
    path.parent.mkdir(parents=True)
    path.write_text(SHAPE_TEXT, encoding="utf-8")
    return tmp_path


def test_a_change_under_tests_logs_reads_the_logs_workflows_run_and_report(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = logs_commands(b"tests/logs/cli/test_paper_run_trails.py\0")
    assert run_main(logs_repo(tmp_path / "repo"), tmp_path / "out") == 0
    assert json.loads((tmp_path / "out/logs.json").read_text(encoding="utf-8"))["meta"] == {
        "sha": HEAD,
        "workflow": LOGS,
        "runs": [9],
    }
    kept = tmp_path / "out/logs-python/9/coverage.json"
    assert kept.read_text(encoding="utf-8") == '{"run": 9}'


def test_a_change_beside_tests_logs_reads_no_run(
    tmp_path: Path, stood_in: dict[str, Commands]
) -> None:
    stood_in["c"] = logs_commands(b"tests/logsx/test_beside.py\0")
    assert run_main(logs_repo(tmp_path / "repo"), tmp_path / "out") == 0
    assert [call[1] for call in stood_in["c"].calls] == ["diff"]
