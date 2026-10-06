# EXT S1 #218 A Docs-Only Fast Path For CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pull request that only adds or edits `HANDOVER.md` or files under `docs/superpowers/` skips CI's expensive steps, while all five required checks still run and report under their own names. Every other change, and every push, runs everything.

**Architecture:** `scripts/ci_scope.py`, standard library only, reads `git diff --name-status -z -M HEAD^1 HEAD` on the pull request's merge commit and writes `docs_only=true|false` to `$GITHUB_OUTPUT`. A path that goes away is never docs-only, and everything it cannot place or compute runs everything (Task 1). Each gated job in `ci.yml` checks out two commits, runs the scope step second, and puts `if: steps.scope.outputs.docs_only != 'true'` on every later step. The deploy job is untouched, and a guard derives the gated jobs from the workflow (Task 2). An audit hook installed by `tests/conftest.py` records every repository file the test run opens, and a guard that runs last refuses any on the fast path. This is Shyden's AC4 choice, "watch the test run" (Task 3).

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18, pytest, PyYAML (already a dev dependency), GitHub Actions. No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md` §12.1 ("The docs-only fast path (Shyden's global rule): steadyhand's CI has none. Its own ticket measures the current CI first … and adds it before other CI work in this epic"). The story's acceptance criteria are on #218, with AC1's measurements (issuecomment-6010057109), the AC4 decision (issuecomment-6010107442) and the status-aware correction (issuecomment-6011927550). Every code block below was generated from a commit that passed the whole gate, not typed. The review log at the end says how each claim was checked.

## Global Constraints

- The required check still runs and reports: no `paths` or `paths-ignore` on any trigger, which would leave a required check pending (AC2).
- The fast path is `HANDOVER.md` and `docs/superpowers/**` only, never Markdown a test reads (AC2). The rest of `docs/` is read by tests (`lq45-members.md`, `strategies/**`) or existence-checked (`research/**`, through lesson `sources`).
- Fail closed to the full pipeline, and say so by name in the log (AC3). The scope step always exits 0: failing closed means a full run, never a red one.
- Deploy jobs on `develop` always run in full (AC5): a job holding an `environment` never carries the skip.
- One test per case (Shyden's global rule): a population known before the run is a `parametrize`, never a loop inside a test.
- Every quality gate is green at 100% branch coverage on 3.12 and 3.13 (AC7); `ci_scope` joins `source_pkgs`, measured to add no coverage warning under `-W error`.

## Review Focus

1. **The merge commit CI checks out.** On a pull request, `actions/checkout` checks out the merge into the base, so `HEAD^1` is the base. A base that moved on with code after the branch was cut must not count against a docs-only pull request, and a code pull request must not pass because the base only changed docs. Pinned in Task 1 by `test_a_merge_commit_is_judged_by_the_pull_requests_own_change` and by mutation C17.
2. **A fast-path file that goes away.** 32 lessons cite 7 specs under `docs/superpowers/specs/`, and `test_every_source_is_a_repo_file` checks that each exists. Deleting or renaming one must run everything. Pinned in Task 1 (`deleted-plan`, `renamed-within-the-fast-path`, mutations C13–C15).
3. **A path git prints unusually.** Paths with spaces or accents, and a non-UTF-8 path, must be placed or refused by name, never misread. Pinned in Task 1 (`a-path-with-a-space-and-an-accent`, `path-not-utf-8`).
4. **A test that reads a fast-path file in a subprocess.** The audit hook sees only its own process. Most CLI journeys run `steadyhand-idx` in-process, but some run the installed console script in its own process (`tests/cli/cli_world.py`), so package code must name no fast-path file. Pinned in Task 3 by `test_no_package_code_names_a_file_on_the_fast_path`.
5. **A run that is not the whole suite.** The read guard judges what every other test opened, so a partial run must fail by name rather than pass on what little it saw, and the guard must run last. Pinned in Task 3: the guard asserts its own place at the end and the derived user docs as a known positive (mutations R4, R3).

---

### Task 1: The docs-only scope classifier

**Acceptance criteria (story text):** AC3; AC4 (the classifier tested one test per case: docs-only, mixed, code-only, a Markdown file a test reads, a deleted file, a renamed file, an empty diff); AC7 (mutations: the allowlist widened to `**/*.md`; an unknown path failing open).

**Files:**
- Create: `scripts/ci_scope.py`, `tests/scripts/test_ci_scope.py`
- Modify: `pyproject.toml` (`ci_scope` in `known-first-party` and `source_pkgs`)

**Interfaces:**
- Consumes: nothing (standard library only).
- Produces: in `ci_scope`: `FULL`, `USAGE`, `FAST_PATH_FILES`, `FAST_PATH_DIRS`, `Change(path: str, removed: bool)`, `ScopeError`, `Verdict(docs_only: bool, reason: str)`, `on_fast_path(path: str) -> bool`, `parse_name_status(raw: bytes) -> list[Change]`, `changes(repo: Path, base: str, head: str) -> list[Change]`, `verdict_for(found: list[Change]) -> Verdict`, `main(argv: list[str], environ: Mapping[str, str], repo: Path) -> int`.

- [ ] **Step 1: Branch.** `git switch -c ext/s1-ci-fast-path origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/scripts/test_ci_scope.py`** (new)

<!-- file: tests/scripts/test_ci_scope.py -->
```python
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
```


- [ ] **Step 3: Write the stubs and the configuration.** New names only.

**`pyproject.toml`** (changed; configuration, needed to collect the tests: 2 edits)

<!-- edit: pyproject.toml -->
Replace:
```toml
[tool.ruff.lint.isort]
known-first-party = ["steadyhand", "steadyhand_idx", "set_dev_version"]

```
with:
```toml
[tool.ruff.lint.isort]
known-first-party = ["steadyhand", "steadyhand_idx", "set_dev_version", "ci_scope"]

```

<!-- edit: pyproject.toml -->
Replace:
```toml
branch = true
source_pkgs = ["steadyhand", "steadyhand_idx"]

```
with:
```toml
branch = true
source_pkgs = ["steadyhand", "steadyhand_idx", "ci_scope"]

```

**`scripts/ci_scope.py`** (new, as stubs)

<!-- file: scripts/ci_scope.py -->
```python
"""Decide whether a CI run may skip its expensive steps (#218).

Usage: python3 scripts/ci_scope.py <github.event_name>

A pull request that only adds or edits paths on the docs-only fast path (the handover and the
plans and specs under ``docs/superpowers/``, which no test opens) writes ``docs_only=true`` to
``$GITHUB_OUTPUT``; the workflow then skips every later step, while each job still reports
under its own name, so the required checks are never left pending. Anything else runs
everything: a code change, a fast-path file that goes away (lesson ``sources`` cite specs, and a
test checks that each one exists), any other event, and every diff this script cannot compute
or read. It always exits 0, because failing closed means a full run, never a red one.

Standard library only: it runs on the runner's system ``python3`` before uv is installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

FULL = "full pipeline"
USAGE = "usage: ci_scope.py <github.event_name>"
FAST_PATH_FILES = frozenset({"HANDOVER.md"})
FAST_PATH_DIRS = ("docs/superpowers/",)
# Status letters `git diff --name-status` prints between two commits. R and C carry a score and
# two paths; a rename's old side goes away, a copy's stays. U (unmerged) and X (unknown) cannot
# appear between two commits, so they are refused with every other letter.
ONE_PATH = frozenset("ADMT")
TWO_PATHS = frozenset("RC")


@dataclass(frozen=True)
class Change:
    path: str
    removed: bool


class ScopeError(Exception):
    """The diff could not be computed or read, so nothing may be skipped."""


@dataclass(frozen=True)
class Verdict:
    docs_only: bool
    reason: str


def on_fast_path(path: str) -> bool:
    raise NotImplementedError("on_fast_path")


def _decode(path: bytes) -> str:
    raise NotImplementedError("_decode")


def parse_name_status(raw: bytes) -> list[Change]:
    """Every path named by ``git diff --name-status -z``, both sides of a rename or copy."""
    raise NotImplementedError("parse_name_status")


def changes(repo: Path, base: str, head: str) -> list[Change]:
    raise NotImplementedError("changes")


def verdict_for(found: list[Change]) -> Verdict:
    raise NotImplementedError("verdict_for")


def _decide(event: str, repo: Path) -> Verdict:
    raise NotImplementedError("_decide")


def main(argv: list[str], environ: Mapping[str, str], repo: Path) -> int:
    if len(argv) != 1:
        raise SystemExit(USAGE)
    output = environ.get("GITHUB_OUTPUT")
    if not output:
        print(f"ci-scope: {FULL}: GITHUB_OUTPUT is not set, so no step can be skipped")
        return 0
    verdict = _decide(argv[0], repo)
    label = verdict.reason if verdict.docs_only else f"{FULL}: {verdict.reason}"
    print(f"ci-scope: {label}")
    with Path(output).open("a", encoding="utf-8") as handle:
        handle.write(f"docs_only={'true' if verdict.docs_only else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], os.environ, Path.cwd()))
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider --continue-on-collection-errors`

Expected: 2285 tests, 51 failed, by kind {'AssertionError': 1, 'NotImplementedError': 50}. Every failure but one is the stub's `NotImplementedError` from the new names. The other is the `python -I -S` entry-point test, which fails on its own assertion (the subprocess reports the stub's traceback). Three tests of `main`'s own argument and environment checks pass against the stubs: stubgen keeps the body of any function a top-level statement calls (the `__main__` guard calls `main`), so in the red phase `main` is real and `_decide` is stubbed. Mutations C18 and C19 prove those three tests go red when that code breaks.

<!-- check: red total=2285 failed=51 -->

- [ ] **Step 5: Implement.**

**`scripts/ci_scope.py`** (replaces the stubs)

<!-- file: scripts/ci_scope.py -->
```python
"""Decide whether a CI run may skip its expensive steps (#218).

Usage: python3 scripts/ci_scope.py <github.event_name>

A pull request that only adds or edits paths on the docs-only fast path (the handover and the
plans and specs under ``docs/superpowers/``, which no test opens) writes ``docs_only=true`` to
``$GITHUB_OUTPUT``; the workflow then skips every later step, while each job still reports
under its own name, so the required checks are never left pending. Anything else runs
everything: a code change, a fast-path file that goes away (lesson ``sources`` cite specs, and a
test checks that each one exists), any other event, and every diff this script cannot compute
or read. It always exits 0, because failing closed means a full run, never a red one.

Standard library only: it runs on the runner's system ``python3`` before uv is installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

FULL = "full pipeline"
USAGE = "usage: ci_scope.py <github.event_name>"
FAST_PATH_FILES = frozenset({"HANDOVER.md"})
FAST_PATH_DIRS = ("docs/superpowers/",)
# Status letters `git diff --name-status` prints between two commits. R and C carry a score and
# two paths; a rename's old side goes away, a copy's stays. U (unmerged) and X (unknown) cannot
# appear between two commits, so they are refused with every other letter.
ONE_PATH = frozenset("ADMT")
TWO_PATHS = frozenset("RC")


@dataclass(frozen=True)
class Change:
    path: str
    removed: bool


class ScopeError(Exception):
    """The diff could not be computed or read, so nothing may be skipped."""


@dataclass(frozen=True)
class Verdict:
    docs_only: bool
    reason: str


def on_fast_path(path: str) -> bool:
    return path in FAST_PATH_FILES or path.startswith(FAST_PATH_DIRS)


def _decode(path: bytes) -> str:
    try:
        return path.decode("utf-8")
    except UnicodeDecodeError as error:
        msg = f"cannot read the diff: a path is not UTF-8 ({error})"
        raise ScopeError(msg) from error


def parse_name_status(raw: bytes) -> list[Change]:
    """Every path named by ``git diff --name-status -z``, both sides of a rename or copy."""
    if not raw:
        return []
    if not raw.endswith(b"\0"):
        msg = "cannot read the diff: the output does not end in NUL"
        raise ScopeError(msg)
    fields = raw[:-1].split(b"\0")
    found: list[Change] = []
    index = 0
    while index < len(fields):
        status = fields[index].decode("ascii", errors="replace")
        letter, score = status[:1], status[1:]
        if letter in ONE_PATH and not score:
            width = 1
        elif letter in TWO_PATHS and score.isdigit():
            width = 2
        else:
            msg = f"cannot read the diff: unknown status {status!r}"
            raise ScopeError(msg)
        named = fields[index + 1 : index + 1 + width]
        if len(named) != width or not all(named):
            msg = f"cannot read the diff: status {status!r} names {len(named)} of {width} paths"
            raise ScopeError(msg)
        if width == 1:
            found.append(Change(_decode(named[0]), removed=letter == "D"))
        else:
            found.append(Change(_decode(named[0]), removed=letter == "R"))
            found.append(Change(_decode(named[1]), removed=False))
        index += 1 + width
    return found


def changes(repo: Path, base: str, head: str) -> list[Change]:
    git = shutil.which("git")
    if git is None:
        msg = "cannot compute the diff: git is not on the path"
        raise ScopeError(msg)
    result = subprocess.run(  # noqa: S603 - git, with revisions this script chooses
        [git, "diff", "--name-status", "-z", "-M", base, head],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = " ".join(result.stderr.decode("utf-8", errors="replace").split())
        msg = f"cannot compute the diff: git diff exited {result.returncode}: {stderr}"
        raise ScopeError(msg)
    return parse_name_status(result.stdout)


def verdict_for(found: list[Change]) -> Verdict:
    if not found:
        return Verdict(docs_only=False, reason="the diff names no path")
    for change in found:
        if not on_fast_path(change.path):
            reason = f"{change.path} is not on the docs-only fast path"
            return Verdict(docs_only=False, reason=reason)
        if change.removed:
            reason = f"{change.path} goes away, and a test may check that it exists"
            return Verdict(docs_only=False, reason=reason)
    return Verdict(docs_only=True, reason=f"docs-only: {len(found)} paths, all on the fast path")


def _decide(event: str, repo: Path) -> Verdict:
    if event != "pull_request":
        reason = f"a {event} run always runs everything (deploys included)"
        return Verdict(docs_only=False, reason=reason)
    # A pull request's checkout is the merge commit, whose first parent is the base branch.
    try:
        return verdict_for(changes(repo, "HEAD^1", "HEAD"))
    except ScopeError as error:
        return Verdict(docs_only=False, reason=str(error))


def main(argv: list[str], environ: Mapping[str, str], repo: Path) -> int:
    if len(argv) != 1:
        raise SystemExit(USAGE)
    output = environ.get("GITHUB_OUTPUT")
    if not output:
        print(f"ci-scope: {FULL}: GITHUB_OUTPUT is not set, so no step can be skipped")
        return 0
    verdict = _decide(argv[0], repo)
    label = verdict.reason if verdict.docs_only else f"{FULL}: {verdict.reason}"
    print(f"ci-scope: {label}")
    with Path(output).open("a", encoding="utf-8") as handle:
        handle.write(f"docs_only={'true' if verdict.docs_only else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], os.environ, Path.cwd()))
```


- [ ] **Step 6: Run the whole gate** (as **The gate** says).

Expected: every step exits 0; 2285 passed on 3.12 and on 3.13, branch coverage 100% (verified on `f872403`).

<!-- check: gate total=2285 passed=2285 -->

- [ ] **Step 7: Mutations.** Run C1–C19 (with C1b) from **Mutation checks**; each must turn the classifier's tests red as predicted, with the total unchanged.
- [ ] **Step 8: Commit** `feat(ci): #218 the docs-only scope classifier (Refs #218)`.

---

### Task 2: Skip the expensive steps on a docs-only pull request

**Acceptance criteria (story text):** AC2; AC5.

**Files:**
- Modify: `.github/workflows/ci.yml` (and, fixed on sight, actionlint's SC2012 in the `build` job's wheel count)
- Create: `tests/meta/test_ci_fast_path.py`

**Interfaces:**
- Consumes: Task 1's `scripts/ci_scope.py`, run as `python3 scripts/ci_scope.py "$EVENT_NAME"`.
- Produces: in every gated job, a step `id: scope` whose output `docs_only` later steps read.

- [ ] **Step 1: Write the failing guard.**

**`tests/meta/test_ci_fast_path.py`** (new)

<!-- file: tests/meta/test_ci_fast_path.py -->
```python
"""The docs-only fast path is wired into ci.yml so every required check still reports (#218).

``scripts/ci_scope.py`` decides; this guard checks the workflow obeys. Each job that gates a
merge checks out two commits (the merge commit and its parents, for the diff), runs the scope
step second, and skips every later step on a docs-only verdict, so the job reports success
under its own name instead of being left pending. Deploy jobs (the ones holding an
``environment``) never carry the skip: they always run in full.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml
from population import searched

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github/workflows/ci.yml"
SKIP = "steps.scope.outputs.docs_only != 'true'"
SCOPE_RUN = 'python3 scripts/ci_scope.py "$EVENT_NAME"'
EVENT = "${{ github.event_name }}"
# Measured on 2026-10-06 (#218): 4 gated jobs whose later steps number 19. Lower each only by
# a deliberate edit when the workflow shrinks.
GATED_FLOOR = 3
SKIPPED_STEPS_FLOOR = 18

# PyYAML reads the bare key `on` as the boolean True, so a key may be a bool.
WORKFLOW: dict[str | bool, Any] = yaml.safe_load(CI.read_text(encoding="utf-8"))
JOBS: dict[str, dict[str, Any]] = WORKFLOW["jobs"]
GATED = sorted(name for name, job in JOBS.items() if "environment" not in job)
DEPLOYS = sorted(name for name, job in JOBS.items() if "environment" in job)


def test_the_gated_and_deploy_jobs_are_the_ones_expected() -> None:
    assert "lint" in GATED
    assert "publish-dev" in DEPLOYS
    assert len(GATED) >= GATED_FLOOR


def test_no_trigger_filters_by_path() -> None:
    """A path filter leaves a required check pending forever; the fast path skips steps instead."""
    triggers: dict[str, Any] = WORKFLOW[True]
    assert set(triggers) == {"pull_request", "push"}
    filtered = [
        f"{event}: {key}"
        for event, spec in triggers.items()
        for key in spec
        if key in {"paths", "paths-ignore"}
    ]
    assert searched(filtered, of=len(triggers), what="triggers") == []


@pytest.mark.parametrize("name", GATED)
def test_a_gated_job_checks_out_the_merge_commit_and_its_parents(name: str) -> None:
    checkout = JOBS[name]["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["fetch-depth"] == 2


@pytest.mark.parametrize("name", GATED)
def test_a_gated_job_runs_the_scope_step_second_and_unconditionally(name: str) -> None:
    scope = JOBS[name]["steps"][1]
    assert scope == {
        "name": "Scope: may this docs-only change skip the rest?",
        "id": "scope",
        "env": {"EVENT_NAME": EVENT},
        "run": SCOPE_RUN,
    }


@pytest.mark.parametrize("name", GATED)
def test_a_gated_job_reports_and_skips_every_later_step(name: str) -> None:
    job = JOBS[name]
    assert "if" not in job, "a job-level condition would leave its required check skipped"
    later = job["steps"][2:]
    unguarded = [
        step.get("name", step.get("run", step.get("uses")))
        for step in later
        if step.get("if") != SKIP
    ]
    assert searched(unguarded, of=len(later), what=f"later steps of {name}") == []


def test_the_skip_covers_every_later_step_of_every_gated_job() -> None:
    later = [step for name in GATED for step in JOBS[name]["steps"][2:]]
    assert len(later) >= SKIPPED_STEPS_FLOOR
    assert sum(step.get("if") == SKIP for step in later) == len(later)


@pytest.mark.parametrize("name", DEPLOYS)
def test_a_deploy_job_always_runs_in_full(name: str) -> None:
    steps = JOBS[name]["steps"]
    scoped = [step for step in steps if step.get("id") == "scope" or SKIP in str(step.get("if"))]
    assert searched(scoped, of=len(steps), what=f"steps of {name}") == []
```


- [ ] **Step 2: Run the whole suite and watch it fail.**

Expected: 2303 tests, 13 failed, by kind {'AssertionError': 4, 'KeyError': 4, 'assert 15 >= 18': 1, "assert {'uses'": 4}. Every failure is the guard's own assertion against the unchanged workflow: no `fetch-depth` (4), no scope step second (4), unguarded later steps (4), and the step count under its floor (1). The three that pass describe what is already true: the jobs split as expected, no trigger filters by path, and the deploy job carries no skip.

<!-- check: red total=2303 failed=13 -->

- [ ] **Step 3: Wire the workflow.** The event goes in through `env`, never inlined into the script (template injection).

**`.github/workflows/ci.yml`** (changed, rewritten whole)

<!-- file: .github/workflows/ci.yml -->
```yaml
name: ci

on:
  pull_request:
    branches: [develop, main]
  push:
    branches: [develop, main]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

env:
  UV_VERSION: "0.12.18"
  HYPOTHESIS_PROFILE: ci

jobs:
  lint:
    name: lint
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          fetch-depth: 2
      - name: "Scope: may this docs-only change skip the rest?"
        id: scope
        env:
          EVENT_NAME: ${{ github.event_name }}
        run: python3 scripts/ci_scope.py "$EVENT_NAME"
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        if: steps.scope.outputs.docs_only != 'true'
        with:
          version: ${{ env.UV_VERSION }}
          python-version: "3.12"
          enable-cache: true
      - run: uv sync --locked
        if: steps.scope.outputs.docs_only != 'true'
      - run: uv run --locked ruff check
        if: steps.scope.outputs.docs_only != 'true'
      - run: uv run --locked ruff format --check
        if: steps.scope.outputs.docs_only != 'true'
      - run: uv run --locked mypy
        if: steps.scope.outputs.docs_only != 'true'

  test:
    name: test (py${{ matrix.python }})
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    strategy:
      fail-fast: false
      matrix:
        python: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          fetch-depth: 2
      - name: "Scope: may this docs-only change skip the rest?"
        id: scope
        env:
          EVENT_NAME: ${{ github.event_name }}
        run: python3 scripts/ci_scope.py "$EVENT_NAME"
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        if: steps.scope.outputs.docs_only != 'true'
        with:
          version: ${{ env.UV_VERSION }}
          python-version: ${{ matrix.python }}
          enable-cache: true
      - run: uv sync --locked
        if: steps.scope.outputs.docs_only != 'true'
      - run: uv run --locked pytest -W error --cov --cov-report=term-missing
        if: steps.scope.outputs.docs_only != 'true'
      # The ten-year backtest is timed on its own: under coverage's tracing it would time the
      # tracer, which roughly triples the run.
      - name: Performance, a ten-year backtest in under 30 seconds
        if: steps.scope.outputs.docs_only != 'true'
        run: uv run --locked pytest -W error -m perf -p no:cacheprovider

  audit:
    name: audit
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          fetch-depth: 2
      - name: "Scope: may this docs-only change skip the rest?"
        id: scope
        env:
          EVENT_NAME: ${{ github.event_name }}
        run: python3 scripts/ci_scope.py "$EVENT_NAME"
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        if: steps.scope.outputs.docs_only != 'true'
        with:
          version: ${{ env.UV_VERSION }}
          python-version: "3.12"
          enable-cache: true
      - run: uv sync --locked
        if: steps.scope.outputs.docs_only != 'true'
      - name: Audit every locked dependency, dev tools included
        if: steps.scope.outputs.docs_only != 'true'
        run: |
          uv export --locked --format requirements-txt --no-emit-workspace \
            --output-file "${RUNNER_TEMP}/requirements-audit.txt"
          uv run --locked pip-audit --strict --disable-pip -r "${RUNNER_TEMP}/requirements-audit.txt"

  build:
    name: build
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          fetch-depth: 2
      - name: "Scope: may this docs-only change skip the rest?"
        id: scope
        env:
          EVENT_NAME: ${{ github.event_name }}
        run: python3 scripts/ci_scope.py "$EVENT_NAME"
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        if: steps.scope.outputs.docs_only != 'true'
        with:
          version: ${{ env.UV_VERSION }}
          python-version: "3.12"
      - run: uv build --all-packages --out-dir dist
        if: steps.scope.outputs.docs_only != 'true'
      - name: Both packages built a wheel and an sdist
        if: steps.scope.outputs.docs_only != 'true'
        run: |
          ls dist
          test "$(find dist -maxdepth 1 -name '*.whl' | wc -l)" -eq 2
          test "$(find dist -maxdepth 1 -name '*.tar.gz' | wc -l)" -eq 2
      - name: The IDX wheel carries its rule data
        if: steps.scope.outputs.docs_only != 'true'
        run: |
          unzip -l dist/steadyhand_idx-*.whl > "${RUNNER_TEMP}/idx-wheel.txt"
          for table in tick_sizes auto_reject fees holidays; do
            grep -q "steadyhand_idx/data/${table}.toml" "${RUNNER_TEMP}/idx-wheel.txt"
          done
      - name: The engine wheel installs and imports with nothing else
        if: steps.scope.outputs.docs_only != 'true'
        run: |
          uv venv "${RUNNER_TEMP}/engine-only"
          uv pip install --python "${RUNNER_TEMP}/engine-only" dist/steadyhand-*.whl
          "${RUNNER_TEMP}/engine-only/bin/python" -c "import steadyhand; print(steadyhand.__version__)"
      - name: Both wheels ship every lesson, and the catalogue loads from them
        if: steps.scope.outputs.docs_only != 'true'
        run: |
          expected="$(find packages/*/src/*/training/lessons -name '*.md' | wc -l)"
          test "${expected}" -gt 0
          uv venv "${RUNNER_TEMP}/lessons"
          uv pip install --python "${RUNNER_TEMP}/lessons" dist/*.whl
          cd "${RUNNER_TEMP}"
          "${RUNNER_TEMP}/lessons/bin/python" - "${expected}" <<'PY'
          import sys
          from steadyhand_idx.training import catalogue
          lessons = catalogue().lessons()
          outside = [lesson.origin for lesson in lessons if "site-packages" not in lesson.origin]
          assert outside == [], outside
          assert len(lessons) == int(sys.argv[1]), (len(lessons), sys.argv[1])
          print(len(lessons), "lessons load from the installed wheels")
          PY
      - name: The engine wheel ships every strategy guide, and the installed command prints one
        if: steps.scope.outputs.docs_only != 'true'
        run: |
          expected="$(find packages/steadyhand/src/steadyhand/strategies/guides -name '*.md' | wc -l)"
          test "${expected}" -gt 0
          cd "${RUNNER_TEMP}"
          "${RUNNER_TEMP}/lessons/bin/python" - "${expected}" <<'PY'
          import sys
          from steadyhand import GUIDES, STRATEGIES, guide
          assert "site-packages" in str(GUIDES), GUIDES
          shipped = sorted(entry.name for entry in GUIDES.iterdir() if entry.name.endswith(".md"))
          assert shipped == sorted(f"{name}.md" for name in STRATEGIES), shipped
          assert len(shipped) == int(sys.argv[1]), (shipped, sys.argv[1])
          for name in STRATEGIES:
              assert guide(name).startswith(f"# {name}\n"), name
          print(len(shipped), "strategy guides ship in the engine wheel")
          PY
          STEADYHAND_HOME="${RUNNER_TEMP}/home" "${RUNNER_TEMP}/lessons/bin/steadyhand-idx" \
            explain buy-and-hold > "${RUNNER_TEMP}/explain.txt"
          head -1 "${RUNNER_TEMP}/explain.txt" | grep -qx "# buy-and-hold"

  publish-dev:
    name: publish-dev
    if: github.event_name == 'push' && github.ref == 'refs/heads/develop'
    needs: [lint, test, audit, build]
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    environment:
      name: testpypi
      url: https://test.pypi.org/project/steadyhand/
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: "3.12"
      - name: Set the development version
        id: version
        env:
          RUN_NUMBER: ${{ github.run_number }}
        run: |
          version="$(uv run --no-project python scripts/set_dev_version.py "${RUN_NUMBER}")"
          echo "version=${version}" >> "${GITHUB_OUTPUT}"
      - run: uv build --all-packages --out-dir dist
      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2
        with:
          repository-url: https://test.pypi.org/legacy/
          packages-dir: dist/
          # A re-run reuses the run number, so the version: skip what the first attempt uploaded.
          skip-existing: true
      - name: Verify both packages install from TestPyPI
        env:
          VERSION: ${{ steps.version.outputs.version }}
        run: |
          for attempt in 1 2 3 4 5 6 7 8 9 10; do
            rm -rf "${RUNNER_TEMP}/verify"
            uv venv "${RUNNER_TEMP}/verify"
            # PyPI first: uv takes each name from the first index that has it, so real
            # dependencies (yfinance) come from PyPI and only our dev builds, which PyPI lacks,
            # from TestPyPI. Anyone can upload to TestPyPI, so it must never be asked first.
            if uv pip install --refresh --python "${RUNNER_TEMP}/verify" \
                --index https://pypi.org/simple/ \
                --default-index https://test.pypi.org/simple/ \
                "steadyhand==${VERSION}" "steadyhand-idx==${VERSION}"; then
              "${RUNNER_TEMP}/verify/bin/python" -c 'import sys, steadyhand, steadyhand_idx; assert steadyhand.__version__ == steadyhand_idx.__version__ == sys.argv[1], (steadyhand.__version__, steadyhand_idx.__version__)' "${VERSION}"
              exit 0
            fi
            echo "attempt ${attempt}: not installable yet"
            sleep 30
          done
          echo "steadyhand ${VERSION} never became installable from TestPyPI" >&2
          exit 1
```


- [ ] **Step 4: Run the whole gate**, and `actionlint` over every workflow.

Expected: every step exits 0; 2303 passed on 3.12 and on 3.13, branch coverage 100% (verified on `38178d2`).

<!-- check: gate total=2303 passed=2303 -->

- [ ] **Step 5: Mutations.** Run W1–W6 from **Mutation checks**.
- [ ] **Step 6: Commit** `feat(ci): #218 skip the expensive steps on a docs-only pull request (Refs #218)`.

---

### Task 3: No test reads a file on the docs-only fast path

**Acceptance criteria (story text):** AC4 ("Markdown a test reads" derived from what the tests do, with a known positive; Shyden's decision 2026-10-06).

**Files:**
- Create: `tests/meta/file_reads.py`, `tests/meta/test_file_reads.py`, `tests/meta/test_fast_path_reads.py`
- Modify: `tests/conftest.py` (install the recorder; move tests marked `last` to the end), `pyproject.toml` (register `last`)

**Interfaces:**
- Consumes: Task 1's `on_fast_path`; `population.searched`, `population.tracked`, `population.ROOT`; `test_disclaimer.user_docs`.
- Produces: in `file_reads`: `Recorder(root: Path)` (a dataclass, callable as an audit hook, with `opened: frozenset[str]` and `unread: tuple[str, ...]`), `RECORDER`, `install() -> Recorder`; the pytest marker `last`.

Measured on 3.12 and 3.13 before writing it: `open`'s first argument is a `str` for `Path.read_text`, `open(str)`, `io.open_code` (imports) and `os.open`, and a `bytes` for `open(bytes)`. It is an `int` for `open(fd)`, whose path `os.open` already reported. `is_file()` and `exists()` raise no event, which is why Task 1 runs everything when a path goes away. `Path.resolve()` raises no event. On a symlink loop it raises in 3.12 and returns the path in 3.13.

- [ ] **Step 1: Write the failing tests.**

**`tests/meta/test_fast_path_reads.py`** (new)

<!-- file: tests/meta/test_fast_path_reads.py -->
```python
"""No test reads a file on CI's docs-only fast path, judged from what the run opened (#218).

``scripts/ci_scope.py`` lets a pull request that only adds or edits ``HANDOVER.md`` and
``docs/superpowers/**`` skip the tests. That is safe only while no test reads those files, so
the recorder installed by ``tests/conftest.py`` notes every repository file the run opens, and
this guard, moved to the end of the run, judges them against the classifier's own allowlist.
A partial run has not opened what the whole suite opens, so it fails by name; run the whole
suite. Some CLI journeys run the installed console script in its own process
(``tests/cli/cli_world.py``), which the hook cannot see, so a static check covers what that code
could name.
"""

import pytest
from file_reads import RECORDER
from population import ROOT, searched, tracked
from test_disclaimer import user_docs

from ci_scope import on_fast_path

# Measured on 2026-10-06 (#218): the whole run opened 250 of the files git lists, the same with a
# warm bytecode cache and a cold one, and the packages hold 57 Python sources. Lower each only by a
# deliberate edit when the repo shrinks.
OPENED_FLOOR = 249
PACKAGE_SOURCES_FLOOR = 56
WHOLE_SUITE = "run the whole suite: this guard judges what every other test opened"


@pytest.mark.last
def test_the_run_opened_no_file_on_the_docs_only_fast_path(request: pytest.FixtureRequest) -> None:
    items = request.session.items
    last = [item for item in items if item.get_closest_marker("last")]
    assert items[-len(last) :] == last, "a guard marked last ran before other tests"
    # The files git lists, the only ones a diff can name: caches under the root (.venv, bytecode,
    # .hypothesis) come and go with the machine, not with what the tests read.
    listed = {path.relative_to(ROOT).as_posix() for path in tracked(ROOT, "")}
    opened = RECORDER.opened & listed
    on_it = sorted(path for path in opened if on_fast_path(path))
    assert searched(on_it, of=len(opened), what="repository files the run opened") == []
    assert RECORDER.unread == ()
    expected = {path.relative_to(ROOT).as_posix() for path in user_docs(ROOT / "docs")}
    assert "docs/lq45-members.md" in expected
    assert sorted(expected - opened) == [], WHOLE_SUITE
    assert len(opened) >= OPENED_FLOOR


def test_no_package_code_names_a_file_on_the_fast_path() -> None:
    sources = tracked(ROOT / "packages", ".py")
    assert ROOT / "packages/steadyhand/src/steadyhand/__init__.py" in sources
    assert len(sources) >= PACKAGE_SOURCES_FLOOR
    naming = [
        path.relative_to(ROOT).as_posix()
        for path in sources
        if any(name in path.read_text(encoding="utf-8") for name in ("HANDOVER", "superpowers"))
    ]
    assert searched(naming, of=len(sources), what="package sources") == []
```

**`tests/meta/test_file_reads.py`** (new)

<!-- file: tests/meta/test_file_reads.py -->
```python
"""The recorder behind the docs-only read guard, driven with the audit events it receives (#218).

Measured on 3.12 and 3.13 before writing it: ``open``'s first argument is a ``str`` for
``Path.read_text``, ``open(str)``, ``io.open_code`` (imports) and ``os.open``; ``bytes`` for
``open(bytes)``; an ``int`` for ``open(fd)``, whose path ``os.open`` already reported.
``is_file()`` and ``exists()`` raise no event at all, which is why a path that goes away is
never docs-only (``scripts/ci_scope.py``).
"""

import os
from pathlib import Path

import pytest
from file_reads import Recorder


@pytest.fixture
def root(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo.resolve()


def test_a_file_opened_inside_the_repo_is_recorded_by_its_repo_path(root: Path) -> None:
    recorder = Recorder(root)
    recorder("open", (str(root / "docs/a.md"), "r", 0))
    assert recorder.opened == frozenset({"docs/a.md"})


def test_a_bytes_path_is_recorded_like_a_str_path(root: Path) -> None:
    recorder = Recorder(root)
    recorder("open", (os.fsencode(root / "HANDOVER.md"), "r", 0))
    assert recorder.opened == frozenset({"HANDOVER.md"})


def test_a_relative_path_is_resolved_against_the_working_directory(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(root / "..")
    recorder = Recorder(root)
    recorder("open", ("repo/docs/b.md", "r", 0))
    assert recorder.opened == frozenset({"docs/b.md"})


def test_a_dotted_path_is_normalised_before_it_is_placed(root: Path) -> None:
    recorder = Recorder(root)
    recorder("open", (f"{root}/packages/../HANDOVER.md", "r", 0))
    assert recorder.opened == frozenset({"HANDOVER.md"})


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/elsewhere/HANDOVER.md", id="outside"),
        pytest.param("{root}-sibling/HANDOVER.md", id="a-sibling-sharing-the-prefix"),
        pytest.param("{root}", id="the-root-itself"),
    ],
)
def test_a_path_outside_the_repo_is_not_recorded(root: Path, path: str) -> None:
    recorder = Recorder(root)
    recorder("open", (path.format(root=root), "r", 0))
    assert recorder.opened == frozenset()
    assert recorder.unread == ()


def test_an_open_by_descriptor_is_skipped_because_its_path_was_reported(root: Path) -> None:
    recorder = Recorder(root)
    recorder("open", (7, "r", 0))
    assert (recorder.opened, recorder.unread) == (frozenset(), ())


def test_any_other_event_is_ignored(root: Path) -> None:
    recorder = Recorder(root)
    recorder("os.listdir", (str(root / "docs"),))
    assert (recorder.opened, recorder.unread) == (frozenset(), ())


def test_an_argument_of_a_type_it_cannot_place_is_kept_by_name(root: Path) -> None:
    recorder = Recorder(root)
    recorder("open", (root / "HANDOVER.md", "r", 0))
    assert recorder.unread == ("PosixPath",)
    assert recorder.opened == frozenset()


def test_opened_is_a_snapshot_not_a_live_view(root: Path) -> None:
    recorder = Recorder(root)
    before = recorder.opened
    recorder("open", (str(root / "a.md"), "r", 0))
    assert before == frozenset()


def test_a_file_opened_through_a_symlink_is_recorded_by_its_real_path(
    root: Path, tmp_path: Path
) -> None:
    (root / "HANDOVER.md").write_text("x", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(root / "HANDOVER.md")
    recorder = Recorder(root)
    recorder("open", (str(link), "r", 0))
    assert recorder.opened == frozenset({"HANDOVER.md"})


def test_a_symlink_loop_is_placed_by_its_spelling_on_every_python(root: Path) -> None:
    """3.12's resolve raises on a loop and 3.13's returns the path unchanged (measured); the
    open itself then fails, so the spelling is all there is to place, on both."""
    (root / "a").symlink_to(root / "b")
    (root / "b").symlink_to(root / "a")
    recorder = Recorder(root)
    recorder("open", (str(root / "a/x.md"), "r", 0))
    assert (recorder.opened, recorder.unread) == (frozenset({"a/x.md"}), ())
```


- [ ] **Step 2: Write the stubs and the marker.**

**`pyproject.toml`** (changed; configuration, needed to collect the tests: 1 edit)

<!-- edit: pyproject.toml -->
Replace:
```toml
    "perf: times the engine, paper runs and start-up; CI runs it with -m perf, without coverage",
]
```
with:
```toml
    "perf: times the engine, paper runs and start-up; CI runs it with -m perf, without coverage",
    "last: judges what every other test did, so tests/conftest.py runs it at the end (#218)",
]
```

**`tests/meta/file_reads.py`** (new, as stubs)

<!-- file: tests/meta/file_reads.py -->
```python
"""Every repository file the test run opens, recorded as it happens (#218).

The docs-only fast path in CI skips the tests, so it may only hold files no test reads. Shyden
chose to learn that from what the tests do rather than from their source text (2026-10-06):
``tests/conftest.py`` installs one ``Recorder`` as an audit hook before any test module is
collected, and ``test_fast_path_reads.py`` runs last and judges what it saw.

An audit hook cannot be removed and runs inside every audited call, so the recorder does as
little as it can and never raises: anything it cannot place is kept by type name in
``unread``, which the guard requires to be empty (fail closed, never skipped).
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(eq=False)
class Recorder:
    """An audit hook recording each ``open`` of a file under *root*, by its repo path.

    *root* is absolute with its symlinks resolved, as ``Path.resolve`` gives it, because the
    paths it is compared with are. A dataclass, so building one runs no code of this module.
    """

    root: Path
    installed: bool = False
    _opened: set[str] = field(default_factory=set)
    _unread: list[str] = field(default_factory=list)

    def __call__(self, event: str, args: tuple[object, ...]) -> None:
        raise NotImplementedError("Recorder.__call__")

    @property
    def opened(self) -> frozenset[str]:
        raise NotImplementedError("Recorder.opened")

    @property
    def unread(self) -> tuple[str, ...]:
        raise NotImplementedError("Recorder.unread")


def _real(path: str) -> str:
    """*path* with its symlinks followed. A loop makes 3.12 raise and 3.13 return the path
    unchanged; the open then fails, so the absolute spelling is all there is to place."""
    raise NotImplementedError("_real")


RECORDER = Recorder(Path(__file__).resolve().parents[2])


def install() -> Recorder:
    """Install the shared recorder once for this process, and return it."""
    raise NotImplementedError("install")
```


- [ ] **Step 3: Run the whole suite and watch it fail.**

Expected: 2322 tests, 14 failed, by kind {'AssertionError': 1, 'NotImplementedError': 13}. The recorder's 13 unit tests fail on the stub's `NotImplementedError`. The read guard fails on its own first assertion, because the conftest that moves it to the end changes only in the implementation. The static package check passes against the stubs, as it judges code that already obeys it; a planted `"docs/superpowers/x.md"` in package code turns it red (R7).

<!-- check: red total=2322 failed=14 -->

- [ ] **Step 4: Implement, and install the recorder.**

**`tests/conftest.py`** (changed: 2 edits)

<!-- edit: tests/conftest.py -->
Replace:
```python

import pytest
from cli_world import Cli
from hypothesis import settings

```
with:
```python

import file_reads
import pytest
from cli_world import Cli
from hypothesis import settings

# Installed before any test module is collected, so every repository file the run opens is
# recorded for the docs-only fast-path guard, which runs last (tests/meta/test_fast_path_reads.py).
file_reads.install()

```

<!-- edit: tests/conftest.py -->
Replace:
```python

@pytest.fixture
```
with:
```python

@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Move the tests marked ``last`` to the end, keeping every other test's order (#218)."""
    items.sort(key=lambda item: item.get_closest_marker("last") is not None)


@pytest.fixture
```

**`tests/meta/file_reads.py`** (replaces the stubs)

<!-- file: tests/meta/file_reads.py -->
```python
"""Every repository file the test run opens, recorded as it happens (#218).

The docs-only fast path in CI skips the tests, so it may only hold files no test reads. Shyden
chose to learn that from what the tests do rather than from their source text (2026-10-06):
``tests/conftest.py`` installs one ``Recorder`` as an audit hook before any test module is
collected, and ``test_fast_path_reads.py`` runs last and judges what it saw.

An audit hook cannot be removed and runs inside every audited call, so the recorder does as
little as it can and never raises: anything it cannot place is kept by type name in
``unread``, which the guard requires to be empty (fail closed, never skipped).
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(eq=False)
class Recorder:
    """An audit hook recording each ``open`` of a file under *root*, by its repo path.

    *root* is absolute with its symlinks resolved, as ``Path.resolve`` gives it, because the
    paths it is compared with are. A dataclass, so building one runs no code of this module.
    """

    root: Path
    installed: bool = False
    _opened: set[str] = field(default_factory=set)
    _unread: list[str] = field(default_factory=list)

    def __call__(self, event: str, args: tuple[object, ...]) -> None:
        if event != "open":
            return
        target = args[0]
        if isinstance(target, int):
            return  # a descriptor: os.open already reported the path it was opened from
        if isinstance(target, bytes):
            target = os.fsdecode(target)
        if not isinstance(target, str):
            self._unread.append(type(target).__name__)
            return
        full = _real(target)
        prefix = f"{self.root}{os.sep}"
        if full.startswith(prefix):
            self._opened.add(full.removeprefix(prefix).replace(os.sep, "/"))

    @property
    def opened(self) -> frozenset[str]:
        return frozenset(self._opened)

    @property
    def unread(self) -> tuple[str, ...]:
        return tuple(self._unread)


def _real(path: str) -> str:
    """*path* with its symlinks followed. A loop makes 3.12 raise and 3.13 return the path
    unchanged; the open then fails, so the absolute spelling is all there is to place."""
    try:
        return str(Path(path).resolve())
    except RuntimeError:
        return os.path.abspath(path)  # noqa: PTH100 - the spelling, without following links


RECORDER = Recorder(Path(__file__).resolve().parents[2])


def install() -> Recorder:
    """Install the shared recorder once for this process, and return it."""
    if not RECORDER.installed:
        sys.addaudithook(RECORDER)
        RECORDER.installed = True
    return RECORDER
```


- [ ] **Step 5: Run the whole gate.**

Expected: every step exits 0; 2322 passed on 3.12 and on 3.13, branch coverage 100% (verified on `827187f`).

<!-- check: gate total=2322 passed=2322 -->

- [ ] **Step 6: Mutations.** Run R1–R6 from **Mutation checks**; each runs the whole suite, since the guard judges what every test opened. Then R7: add `PLANTED = "docs/superpowers/x.md"` to `packages/steadyhand/src/steadyhand/disclaimer.py`, run `test_no_package_code_names_a_file_on_the_fast_path` alone, watch it fail naming that file, and restore.
- [ ] **Step 7: Commit** `test(meta): #218 no test reads a file on the docs-only fast path (Refs #218)`, then push, open the PR (its body calls out the floor style, below) and merge on green as **Merging** says.

---

## The gate

`uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error -m perf -p no:cacheprovider`, and the same coverage run on 3.13 in its own environment (`UV_PROJECT_ENVIRONMENT=<dir> uv run --locked --python 3.13 …`). Each must exit 0.

## Floors: called out (Shyden, 2026-10-06)

The new guards' floors (`GATED_FLOOR`, `SKIPPED_STEPS_FLOOR`, `OPENED_FLOOR`, `PACKAGE_SOURCES_FLOOR`) use steadyhand's #178 style: measured − 1, typed into the test, with the measurement in a comment. They do not use the global rule's recorded, ratcheted floors file. That tooling comes with the TypeScript rewrite in #221. Until then, these floors catch a reader that goes blind, but they do not notice growth.

## Mutation checks

Each mutation was predicted (the exact failing tests) before it ran, and each turned red exactly those tests, with the total unchanged except where a planted test adds its own. C and W runs read their test file; R runs read the whole suite, since the read guard judges what every test opened.

| Mutation | What it breaks | Red | Total |
|---|---|---|---|
| C1 | allowlist widened to all of docs/ | 6 | 54 |
| C1b | allowlist widened to **/*.md (AC7) | 8 | 54 |
| C2 | a path off the fast path fails open (AC7) | 7 | 54 |
| C3 | an unknown status letter accepted | 1 | 54 |
| C4 | a rename's old side dropped | 5 | 54 |
| C5 | a push run classified like a pull request | 3 | 54 |
| C6 | a diff it cannot compute fails open | 2 | 54 |
| C7 | unterminated output accepted | 1 | 54 |
| C8 | a status with too few paths accepted | 2 | 54 |
| C9 | an empty diff skips the steps | 2 | 54 |
| C10 | an import from outside the standard library | 1 | 54 |
| C11 | the entry point drops the event | 2 | 54 |
| C12 | a non-UTF-8 path read as a path | 1 | 54 |
| C13 | a fast-path file that goes away skips the steps | 3 | 54 |
| C14 | a deletion not marked as going away | 3 | 54 |
| C15 | a rename's old side not marked as going away | 3 | 54 |
| C16 | a copy's source marked as going away | 1 | 54 |
| C17 | a pull request judged against its own branch, not its base | 7 | 54 |
| C18 | any number of arguments accepted | 2 | 54 |
| C19 | a missing GITHUB_OUTPUT not noticed | 1 | 54 |
| W1 | one later step loses its skip | 2 | 16 |
| W2 | a gated checkout loses fetch-depth | 1 | 16 |
| W3 | a job-level condition on a gated job | 1 | 16 |
| W4 | a path filter on pull_request | 1 | 16 |
| W5 | the deploy job gains the skip | 1 | 16 |
| W6 | the event inlined into the script | 1 | 16 |
| R1 | allowlist widened to **/*.md (AC7) | 9 | 2322 |
| R2 | a test reads the handover | 1 | 2325 |
| R3 | the recorder blinded to all but packages/ | 7 | 2322 |
| R4 | the guard no longer moved to the end | 1 | 2322 |
| R5 | the recorder never installed | 1 | 2322 |
| R6 | the recorder blind to bytes paths | 1 | 2322 |
| R7 | a package module names `docs/superpowers/x.md` | 1 | 1 (that test alone) |

## Merging

CI completed on the head SHA read from a file, every job `success` by name, `gh pr merge --squash --match-head-commit "$(cat <file>)"`, then the `develop` run with `publish-dev` read by name. Then AC6: measure a docs-only pull request's run (the handover PR that closes this story's session is one) and post it on #218 beside AC1's 317 s median.

## Plan review log

Each pass ran the mechanical checks first: every name in the Interfaces blocks found exactly once in the code, the commit subjects matched, no placeholder left, and `check_plan.py` rebuilt every task from this document's own text, ran its red phase and gate, and compared its tree with the verified commit. Then the whole document was read against its sources.

- **Pass 1** (replay: 0 problems, three trees identical). 2 findings: Task 1's mutation step named C1–C17 after C18, C19 and C17 had been added, and Task 3's omitted R7. Both were fixed.
- **Pass 2** (prose against sources). 1 finding: "the CLI journeys run the console script in a subprocess" overstated it, because `tests/cli/cli_world.py` runs `steadyhand-idx` in-process by default and only some journeys use the installed script in its own process. It was fixed in Review Focus 4, in the read guard's docstring (Task 3 amended) and in the PR body. Then replayed again: 0 problems, three trees identical.
- **Pass 3**: no findings. The plan is approved under Shyden's rule (plans reviewed to zero, then self-approved).

Found before the plan was written, while building and measuring the code (each is in the code above, not a plan defect): the cited specs under `docs/superpowers/specs/` (a fast-path path that goes away now runs everything, #218 issuecomment-6011927550); the two-parent merge commit CI checks out (Review Focus 1, mutation C17); a red phase that would have broken collection (`Recorder` became a dataclass); and the read guard's population, which counted `.venv`, bytecode and `.hypothesis` files (1,655 in one run, 694 in another) until it was restricted to the files git lists (250 warm and cold).
