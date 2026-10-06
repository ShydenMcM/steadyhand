"""The CI scope classifier: a docs-only change skips the expensive steps, anything else runs
everything, and a diff it cannot place or compute runs everything too (#218). A path that goes
away is never docs-only: lesson ``sources`` cite specs under ``docs/superpowers/``, and a test
checks that each one exists."""

import os
import runpy
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

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

Build = Callable[[Path], None]


GIT = shutil.which("git")


def git(repo: Path, *args: str) -> None:
    assert GIT is not None, "git is not on the path"
    subprocess.run(  # noqa: S603 - git, with arguments written in the tests
        [GIT, "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def write(repo: Path, name: str, text: str = "x\n") -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def two_commits(tmp_path: Path, change: Build) -> Path:
    """A repo whose base commit holds a code file, a read doc and a plan; HEAD applies *change*."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write(repo, "packages/a.py")
    write(repo, "docs/lq45-members.md")
    write(repo, "docs/superpowers/plans/p.md", "the plan\n" * 20)
    write(repo, "HANDOVER.md")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    change(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", "head")
    return repo


def edit_handover_and_plan(repo: Path) -> None:
    write(repo, "HANDOVER.md", "new\n")
    write(repo, "docs/superpowers/specs/s.md")


def edit_handover_and_code(repo: Path) -> None:
    write(repo, "HANDOVER.md", "new\n")
    write(repo, "packages/a.py", "y\n")


def edit_code(repo: Path) -> None:
    write(repo, "packages/a.py", "y\n")


def edit_read_doc(repo: Path) -> None:
    write(repo, "docs/lq45-members.md", "changed\n")


def delete_plan(repo: Path) -> None:
    (repo / "docs/superpowers/plans/p.md").unlink()


def delete_read_doc(repo: Path) -> None:
    (repo / "docs/lq45-members.md").unlink()


def rename_plan(repo: Path) -> None:
    git(repo, "mv", "docs/superpowers/plans/p.md", "docs/superpowers/plans/q.md")


def rename_plan_out_of_the_fast_path(repo: Path) -> None:
    git(repo, "mv", "docs/superpowers/plans/p.md", "docs/p.md")


def rename_read_doc_into_the_fast_path(repo: Path) -> None:
    git(repo, "mv", "docs/lq45-members.md", "docs/superpowers/plans/lq45-members.md")


def no_change(repo: Path) -> None:
    del repo


@pytest.mark.parametrize(
    ("change", "docs_only"),
    [
        pytest.param(edit_handover_and_plan, True, id="docs-only"),
        pytest.param(edit_handover_and_code, False, id="mixed"),
        pytest.param(edit_code, False, id="code-only"),
        pytest.param(edit_read_doc, False, id="markdown-a-test-reads"),
        pytest.param(delete_plan, False, id="deleted-plan"),
        pytest.param(delete_read_doc, False, id="deleted-read-doc"),
        pytest.param(rename_plan, False, id="renamed-within-the-fast-path"),
        pytest.param(rename_plan_out_of_the_fast_path, False, id="renamed-out-of-the-fast-path"),
        pytest.param(rename_read_doc_into_the_fast_path, False, id="renamed-into-the-fast-path"),
        pytest.param(no_change, False, id="empty-diff"),
    ],
)
def test_a_change_is_classified_by_every_path_it_touches(
    tmp_path: Path, change: Build, *, docs_only: bool
) -> None:
    repo = two_commits(tmp_path, change)
    assert verdict_for(changes(repo, "HEAD^1", "HEAD")).docs_only is docs_only


def test_a_rename_names_both_its_sides_and_its_old_side_goes_away(tmp_path: Path) -> None:
    repo = two_commits(tmp_path, rename_plan_out_of_the_fast_path)
    assert changes(repo, "HEAD^1", "HEAD") == [
        Change("docs/superpowers/plans/p.md", removed=True),
        Change("docs/p.md", removed=False),
    ]


def test_a_deletion_names_the_deleted_path(tmp_path: Path) -> None:
    repo = two_commits(tmp_path, delete_read_doc)
    assert changes(repo, "HEAD^1", "HEAD") == [Change("docs/lq45-members.md", removed=True)]


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


def test_a_docs_only_verdict_counts_its_paths() -> None:
    verdict = verdict_for(edits("HANDOVER.md", "docs/superpowers/specs/s.md"))
    assert verdict == Verdict(True, "docs-only: 2 paths, all on the fast path")


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
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = two_commits(tmp_path, edit_handover_and_plan)
    assert run_main(tmp_path, "pull_request", repo) == (0, "docs_only=true\n")
    assert capsys.readouterr().out == "ci-scope: docs-only: 2 paths, all on the fast path\n"


def test_a_code_pull_request_runs_everything(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = two_commits(tmp_path, edit_handover_and_code)
    assert run_main(tmp_path, "pull_request", repo) == (0, "docs_only=false\n")
    assert capsys.readouterr().out == (
        f"ci-scope: {FULL}: packages/a.py is not on the docs-only fast path\n"
    )


def merge_of(tmp_path: Path, pull_request: Build, base_moves_on: Build) -> Path:
    """The commit CI checks out for a pull request: its branch merged into a base that moved on
    after the branch was cut, so HEAD^1 is the base and HEAD^2 the pull request's head."""
    repo = two_commits(tmp_path, no_change)
    git(repo, "switch", "-q", "-c", "pull-request")
    pull_request(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the pull request")
    git(repo, "switch", "-q", "main")
    base_moves_on(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the base moves on")
    git(repo, "merge", "-q", "--no-ff", "-m", "merge", "pull-request")
    return repo


@pytest.mark.parametrize(
    ("pull_request", "base_moves_on", "written"),
    [
        pytest.param(
            edit_handover_and_plan, edit_code, "docs_only=true\n", id="docs-onto-a-code-change"
        ),
        pytest.param(
            edit_code, edit_handover_and_plan, "docs_only=false\n", id="code-onto-a-docs-change"
        ),
    ],
)
def test_a_merge_commit_is_judged_by_the_pull_requests_own_change(
    tmp_path: Path, pull_request: Build, base_moves_on: Build, written: str
) -> None:
    repo = merge_of(tmp_path, pull_request, base_moves_on)
    assert run_main(tmp_path, "pull_request", repo) == (0, written)


@pytest.mark.parametrize("event", ["push", "workflow_dispatch", "schedule"])
def test_every_event_but_a_pull_request_runs_everything(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], event: str
) -> None:
    repo = two_commits(tmp_path, edit_handover_and_plan)
    assert run_main(tmp_path, event, repo) == (0, "docs_only=false\n")
    assert capsys.readouterr().out == (
        f"ci-scope: {FULL}: a {event} run always runs everything (deploys included)\n"
    )


def test_a_diff_it_cannot_compute_runs_everything_and_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "one-commit"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write(repo, "HANDOVER.md")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "only")
    assert run_main(tmp_path, "pull_request", repo) == (0, "docs_only=false\n")
    out = capsys.readouterr().out
    assert out.startswith(f"ci-scope: {FULL}: cannot compute the diff: git diff exited 128: ")
    assert "HEAD^1" in out


def test_without_an_output_file_it_says_everything_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = two_commits(tmp_path, edit_handover_and_plan)
    assert main(["pull_request"], {}, repo) == 0
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
    repo = two_commits(tmp_path, edit_handover_and_plan)
    monkeypatch.setenv("PATH", str(tmp_path / "no-tools-here"))
    assert run_main(tmp_path, "pull_request", repo) == (0, "docs_only=false\n")
    assert capsys.readouterr().out == (
        f"ci-scope: {FULL}: cannot compute the diff: git is not on the path\n"
    )


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/ci_scope.py"


def test_the_workflow_command_runs_on_the_standard_library_alone(tmp_path: Path) -> None:
    """CI runs it with the runner's system python3, before uv installs anything: -S drops
    site-packages, so an import from outside the standard library fails here first."""
    repo = two_commits(tmp_path, edit_handover_and_plan)
    out = output_of(tmp_path)
    result = subprocess.run(  # noqa: S603 - this interpreter, running the script under test
        [sys.executable, "-I", "-S", str(SCRIPT), "pull_request"],
        cwd=repo,
        env={"GITHUB_OUTPUT": str(out), "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode, result.stdout, result.stderr) == (
        0,
        "ci-scope: docs-only: 2 paths, all on the fast path\n",
        "",
    )
    assert out.read_text(encoding="utf-8") == "docs_only=true\n"


def test_run_as_a_script_it_reads_the_event_the_environment_and_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = two_commits(tmp_path, edit_handover_and_code)
    out = output_of(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "pull_request"])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exited.value.code == 0
    assert capsys.readouterr().out == (
        f"ci-scope: {FULL}: packages/a.py is not on the docs-only fast path\n"
    )
    assert out.read_text(encoding="utf-8") == "docs_only=false\n"
