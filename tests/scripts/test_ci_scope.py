"""The CI scope classifier: a docs-only change skips the expensive steps, anything else runs
everything, and a diff it cannot place or compute runs everything too (#218). A path that goes
away is never docs-only: lesson ``sources`` cite specs under ``docs/superpowers/``, and a test
checks that each one exists.

A unit test starts no process (#286): here git is stood in (``tests/scripts/conftest.py``). The
real git cases are in ``tests/integration/scripts/test_ci_scope_git.py``."""

import re
import runpy
import sys
from pathlib import Path

import pytest
from script_imports import imported_modules
from stood_in_git import FakeGit

from ci_scope import (
    FULL,
    Change,
    ScopeError,
    Verdict,
    changes,
    main,
    on_fast_path,
    parse_name_status,
    verdict_for,
)

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/ci_scope.py"


def test_changes_asks_git_for_the_name_status_diff_and_reads_its_answer(
    tmp_path: Path, fake_git: FakeGit
) -> None:
    fake_git.stdout = b"R087\0docs/superpowers/plans/p.md\0docs/p.md\0D\0docs/lq45-members.md\0"
    assert changes(tmp_path, "BASE", "HEAD") == [
        Change("docs/superpowers/plans/p.md", removed=True),
        Change("docs/p.md", removed=False),
        Change("docs/lq45-members.md", removed=True),
    ]
    assert fake_git.called_in(tmp_path, "diff", "--name-status", "-z", "-M", "BASE", "HEAD")


def test_a_git_diff_that_fails_is_refused_with_its_exit_code_and_message(
    tmp_path: Path, fake_git: FakeGit
) -> None:
    fake_git.returncode = 128
    fake_git.stderr = b"fatal: ambiguous argument 'HEAD^1':\n  unknown revision\n"
    with pytest.raises(
        ScopeError,
        match=(
            r"^cannot compute the diff: git diff exited 128: "
            r"fatal: ambiguous argument 'HEAD\^1': unknown revision$"
        ),
    ):
        changes(tmp_path, "HEAD^1", "HEAD")


def test_a_git_message_that_is_not_utf_8_is_still_reported(
    tmp_path: Path, fake_git: FakeGit
) -> None:
    fake_git.returncode = 1
    fake_git.stderr = b"bad \xff byte"
    with pytest.raises(
        ScopeError, match=r"^cannot compute the diff: git diff exited 1: bad \ufffd byte$"
    ):
        changes(tmp_path, "HEAD^1", "HEAD")


@pytest.mark.parametrize(
    ("raw", "parsed"),
    [
        pytest.param(b"A\0a.md\0", [Change("a.md", removed=False)], id="added"),
        pytest.param(b"M\0a.md\0", [Change("a.md", removed=False)], id="modified"),
        pytest.param(b"T\0a.md\0", [Change("a.md", removed=False)], id="type-changed"),
        pytest.param(b"D\0a.md\0", [Change("a.md", removed=True)], id="deleted"),
        pytest.param(
            b"R087\0a.md\0b.md\0",
            [Change("a.md", removed=True), Change("b.md", removed=False)],
            id="renamed",
        ),
        pytest.param(
            b"C100\0a.md\0b.md\0",
            [Change("a.md", removed=False), Change("b.md", removed=False)],
            id="copied",
        ),
        pytest.param(
            b"M\0docs/superpowers/a b \xc3\xa9.md\0",
            [Change("docs/superpowers/a b \u00e9.md", removed=False)],
            id="a-path-with-a-space-and-an-accent",
        ),
        pytest.param(b"", [], id="empty"),
    ],
)
def test_each_status_letter_names_its_paths_and_whether_they_go_away(
    raw: bytes, parsed: list[Change]
) -> None:
    assert parse_name_status(raw) == parsed


@pytest.mark.parametrize(
    ("path", "fast"),
    [
        ("HANDOVER.md", True),
        ("docs/superpowers/plans/2026-10-06-x.md", True),
        ("docs/superpowers", False),
        ("docs/superpowersX/a.md", False),
        ("docs/lq45-members.md", False),
        ("docs/research/t-fees.md", False),
        ("docs/strategies/README.md", False),
        ("README.md", False),
        ("packages/steadyhand/README.md", False),
        ("sub/HANDOVER.md", False),
        ("HANDOVER.md.orig", False),
    ],
)
def test_only_the_handover_and_the_plans_and_specs_are_on_the_fast_path(
    path: str, *, fast: bool
) -> None:
    assert on_fast_path(path) is fast


def edits(*paths: str) -> list[Change]:
    return [Change(path, removed=False) for path in paths]


def test_a_full_verdict_names_the_first_path_off_the_fast_path() -> None:
    verdict = verdict_for(edits("HANDOVER.md", "packages/a.py", "uv.lock"))
    assert verdict == Verdict(False, "packages/a.py is not on the docs-only fast path")


def test_a_fast_path_file_that_goes_away_runs_everything_and_says_why() -> None:
    verdict = verdict_for(
        [*edits("HANDOVER.md"), Change("docs/superpowers/specs/s.md", removed=True)]
    )
    assert verdict == Verdict(
        False, "docs/superpowers/specs/s.md goes away, and a test may check that it exists"
    )


@pytest.mark.parametrize(
    ("paths", "reason"),
    [
        pytest.param(("HANDOVER.md",), "docs-only: 1 path, all on the fast path", id="one"),
        pytest.param(
            ("HANDOVER.md", "docs/superpowers/specs/s.md"),
            "docs-only: 2 paths, all on the fast path",
            id="two",
        ),
    ],
)
def test_a_docs_only_verdict_counts_its_paths(paths: tuple[str, ...], reason: str) -> None:
    assert verdict_for(edits(*paths)) == Verdict(True, reason)


def test_an_empty_diff_runs_everything_and_says_why() -> None:
    assert verdict_for([]) == Verdict(False, "the diff names no path")


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(b"X\0a.md\0", id="unknown-status"),
        pytest.param(b"M\0", id="missing-path"),
        pytest.param(b"R100\0docs/superpowers/a.md\0", id="rename-missing-its-new-side"),
        pytest.param(b"M\0a.md", id="unterminated"),
        pytest.param(b"M\0\xff.md\0", id="path-not-utf-8"),
    ],
)
def test_a_diff_it_cannot_read_is_refused_by_name(raw: bytes) -> None:
    with pytest.raises(ScopeError, match="cannot read the diff"):
        parse_name_status(raw)


def output_of(tmp_path: Path) -> Path:
    return tmp_path / "github_output"


def run_main(tmp_path: Path, event: str, repo: Path) -> tuple[int, str]:
    out = output_of(tmp_path)
    code = main([event], {"GITHUB_OUTPUT": str(out)}, repo)
    return code, out.read_text(encoding="utf-8")


def test_a_docs_only_pull_request_skips_the_expensive_steps(
    tmp_path: Path, fake_git: FakeGit, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_git.stdout = b"M\0HANDOVER.md\0A\0docs/superpowers/specs/s.md\0"
    assert run_main(tmp_path, "pull_request", tmp_path) == (0, "docs_only=true\n")
    assert capsys.readouterr().out == "ci-scope: docs-only: 2 paths, all on the fast path\n"


def test_a_code_pull_request_runs_everything(
    tmp_path: Path, fake_git: FakeGit, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_git.stdout = b"M\0HANDOVER.md\0M\0packages/a.py\0"
    assert run_main(tmp_path, "pull_request", tmp_path) == (0, "docs_only=false\n")
    assert capsys.readouterr().out == (
        f"ci-scope: {FULL}: packages/a.py is not on the docs-only fast path\n"
    )


def test_a_pull_request_is_judged_against_its_merge_commits_first_parent(
    tmp_path: Path, fake_git: FakeGit
) -> None:
    """CI checks out a pull request's merge commit, whose first parent is the base branch, so the
    diff is HEAD^1 to HEAD: the pull request's own change, whatever the base did meanwhile."""
    fake_git.stdout = b"M\0HANDOVER.md\0"
    run_main(tmp_path, "pull_request", tmp_path)
    assert fake_git.called_in(tmp_path, "diff", "--name-status", "-z", "-M", "HEAD^1", "HEAD")


def test_a_diff_it_cannot_compute_runs_everything_and_says_so(
    tmp_path: Path, fake_git: FakeGit, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_git.returncode = 128
    fake_git.stderr = b"fatal: ambiguous argument 'HEAD^1'\n"
    assert run_main(tmp_path, "pull_request", tmp_path) == (0, "docs_only=false\n")
    assert capsys.readouterr().out == (
        f"ci-scope: {FULL}: cannot compute the diff: git diff exited 128: "
        "fatal: ambiguous argument 'HEAD^1'\n"
    )


@pytest.mark.parametrize("event", ["push", "workflow_dispatch", "schedule"])
def test_every_event_but_a_pull_request_runs_everything(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], event: str
) -> None:
    """No git is stood in: a run that called it would be refused (#286)."""
    assert run_main(tmp_path, event, tmp_path) == (0, "docs_only=false\n")
    assert capsys.readouterr().out == (
        f"ci-scope: {FULL}: a {event} run always runs everything (deploys included)\n"
    )


def test_without_an_output_file_it_says_everything_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["pull_request"], {}, tmp_path) == 0
    assert capsys.readouterr().out == (
        f"ci-scope: {FULL}: GITHUB_OUTPUT is not set, so no step can be skipped\n"
    )


@pytest.mark.parametrize("argv", [[], ["pull_request", "extra"]])
def test_it_takes_exactly_the_event_name(tmp_path: Path, argv: list[str]) -> None:
    with pytest.raises(SystemExit, match=r"^usage: ci_scope\.py <github\.event_name>$"):
        main(argv, {"GITHUB_OUTPUT": str(output_of(tmp_path))}, tmp_path)


def test_without_git_on_the_path_it_runs_everything_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "no-tools-here"))
    assert run_main(tmp_path, "pull_request", tmp_path) == (0, "docs_only=false\n")
    assert capsys.readouterr().out == (
        f"ci-scope: {FULL}: cannot compute the diff: git is not on the path\n"
    )


def test_the_workflow_command_imports_from_the_standard_library_alone() -> None:
    """CI runs it with the runner's system python3, before uv installs anything. The run under
    that bare interpreter is in the integration suite; here, every import it makes is read."""
    imported = imported_modules(SCRIPT)
    assert "subprocess" in imported
    assert sorted(imported - sys.stdlib_module_names) == []


@pytest.mark.parametrize(
    ("source", "found"),
    [
        pytest.param("import os.path\n", {"os"}, id="import"),
        pytest.param("import json as j, csv\n", {"json", "csv"}, id="aliased-and-several"),
        pytest.param("from xml.etree import ElementTree\n", {"xml"}, id="from-import"),
        pytest.param("def f():\n    import yaml\n", {"yaml"}, id="inside-a-function"),
    ],
)
def test_every_import_form_is_read(tmp_path: Path, source: str, found: set[str]) -> None:
    script = tmp_path / "script.py"
    script.write_text(source, encoding="utf-8")
    assert imported_modules(script) == found


@pytest.mark.parametrize(
    ("source", "refusal"),
    [
        pytest.param("from . import x\n", "a relative import in script.py", id="relative"),
        pytest.param("__import__('yaml')\n", "a dynamic import in script.py, line 1", id="dunder"),
        pytest.param(
            "import importlib\nimportlib.import_module('yaml')\n",
            "a dynamic import in script.py, line 2",
            id="import-module",
        ),
    ],
)
def test_an_import_it_cannot_read_is_refused(tmp_path: Path, source: str, refusal: str) -> None:
    script = tmp_path / "script.py"
    script.write_text(source, encoding="utf-8")
    with pytest.raises(AssertionError, match=f"^{re.escape(refusal)}"):
        imported_modules(script)


def test_run_as_a_script_it_reads_the_event_the_environment_and_the_working_directory(
    tmp_path: Path,
    fake_git: FakeGit,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_git.stdout = b"M\0HANDOVER.md\0M\0packages/a.py\0"
    out = output_of(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "pull_request"])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exited.value.code == 0
    assert capsys.readouterr().out == (
        f"ci-scope: {FULL}: packages/a.py is not on the docs-only fast path\n"
    )
    assert out.read_text(encoding="utf-8") == "docs_only=false\n"
    assert fake_git.called_in(tmp_path, "diff", "--name-status", "-z", "-M", "HEAD^1", "HEAD")
