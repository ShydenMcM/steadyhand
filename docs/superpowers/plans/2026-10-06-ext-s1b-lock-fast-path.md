# EXT S1b #264 Lock The Docs-Only Fast Path During Every Full CI Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On every full CI run, before any step that could read them, make every file on the docs-only fast path unreadable. Any test or tool that reads one then fails by name, in any language, and the fast path's safety no longer rests on a Python-only recorder.

**Architecture:** `scripts/lock_fast_path.py` (standard library only) lists the files git tracks, keeps those `ci_scope.on_fast_path` names, `chmod 000`s each, and proves none can be read. It fails the job by name when there is nothing to lock, git fails, or the lock does not bite (Task 1). Each gated job in `ci.yml` runs it third, after checkout and the scope step (both of which read the tree), and the wiring guard requires that of every gated job, so the coming `extension` job inherits it. Root ignores file modes, so the guard also refuses a gated job whose `container:` runs as root (least privilege; Playwright's image runs as root by default) (Task 2). On its first measurement the lock found `ruff format --check` reading `HANDOVER.md`, because ruff 0.16 formats Markdown. Task 1 excludes it, as `docs/superpowers` already was.

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18, pytest, Node for the cross-language test (the Ubuntu 24.04 runner image lists Node.js 22.23.3, read from actions/runner-images on 2026-10-06; this machine has it too), GitHub Actions. No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md` §12.1 and the story #264 (Shyden, 2026-10-06: *"cover everything you can"*, on a side agent's note that #218's recorder watches only the Python tests). Builds on `docs/superpowers/plans/2026-10-06-ext-s1-ci-fast-path.md`. Every code block below was generated from a commit that passed the whole gate, not typed.

## Global Constraints

- Language-agnostic. Measured on 2026-10-06: after `chmod 000`, Python raises `PermissionError` and Node raises `EACCES`, while `is_file()`, `existsSync` and directory listing still work. A deletion already runs everything (#218), so existence checks need no lock.
- `git diff` cannot hash a locked file (measured: exit 128, `cannot hash HANDOVER.md`), so the lock comes after every step that diffs the tree. Today that is only the scope step.
- Fail closed and by name. A lock that cannot prove itself fails the job; it never passes quietly.
- The allowlist has one home: `ci_scope.on_fast_path`.
- One test per case; every quality gate is green at 100% branch coverage on 3.12 and 3.13.

## Review Focus

1. **A tool, not a test, that reads the fast path.** Formatters and linters walk the tree, and ruff already did. Pinned by the measurement before merge (the whole gate run on a locked tree) and, on every full run, by the lock itself.
2. **Root, or a filesystem that ignores modes.** `chmod 000` stops neither. So the wiring guard refuses a gated job whose container runs as root (`test_a_gated_job_runs_no_container_as_root`, mutations W9–W12), and at runtime the lock proves each file unreadable and refuses otherwise (`test_a_lock_that_does_not_bite_is_refused_by_name`, mutation L3).
3. **A reader outside Python.** Pinned by `test_a_locked_file_refuses_a_node_read_and_still_exists`.
4. **A new gated job without the lock.** Pinned by `test_a_gated_job_locks_the_fast_path_before_any_other_step` over the jobs derived from the workflow (mutations W7, W8).
5. **A Python read whose error a test swallows.** The lock cannot see a read that fails quietly; #218's read guard, which stays, does.

---

### Task 1: The docs-only fast-path lock

**Acceptance criteria (story text):** AC1 (the script), AC2 (fails closed by name), AC3 (language-agnostic, proved in Python and Node).

**Files:**
- Create: `scripts/lock_fast_path.py`, `tests/scripts/test_lock_fast_path.py`
- Modify: `pyproject.toml` (`lock_fast_path` in `known-first-party` and `source_pkgs`; `HANDOVER.md` in ruff's `extend-exclude`)

**Interfaces:**
- Consumes: `ci_scope.on_fast_path(path: str) -> bool` (EXT S1).
- Produces: in `lock_fast_path`: `USAGE`, `LockError`, `fast_path_files(repo: Path) -> list[str]`, `lock(repo: Path) -> list[str]`, `main(argv: list[str], repo: Path) -> int`; run as `python3 scripts/lock_fast_path.py`.

- [ ] **Step 1: Branch.** `git switch -c ext/s1b-lock-fast-path origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/scripts/test_lock_fast_path.py`** (new)

<!-- file: tests/scripts/test_lock_fast_path.py -->
```python
"""The lock on CI's docs-only fast path: on a full run, before any step that could read them, every
git-listed file a docs-only pull request may change without running the tests is made unreadable,
so a reader in any language fails by name (#264).

Measured on 2026-10-06 before writing it: after ``chmod 000``, Python raises ``PermissionError`` and
Node raises ``EACCES``, while ``is_file()``, ``existsSync`` and directory listing still work. A
deletion already runs everything (#218), so existence checks need no lock.
"""

import os
import runpy
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from lock_fast_path import LockError, fast_path_files, lock, main

GIT = shutil.which("git")
NODE = shutil.which("node")
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/lock_fast_path.py"
PLAN = "docs/superpowers/plans/p.md"


def git(repo: Path, *args: str) -> None:
    assert GIT is not None, "git is not on the path"
    subprocess.run(  # noqa: S603 - git, with arguments written in the tests
        [GIT, "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def repo_with(tmp_path: Path, *names: str) -> Path:
    """A repo with *names* committed, each holding its own name, and one untracked plan."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    for name in names:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    (repo / "docs/superpowers").mkdir(parents=True, exist_ok=True)
    (repo / "docs/superpowers/untracked.md").write_text("new", encoding="utf-8")
    return repo


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return repo_with(
        tmp_path, "HANDOVER.md", PLAN, "docs/lq45-members.md", "packages/a.py", "README.md"
    )


def no_chmod(path: Path, mode: int, *, follow_symlinks: bool = True) -> None:
    """``Path.chmod`` as root sees it, near enough: nothing changes."""
    del path, mode, follow_symlinks


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_the_fast_path_files_are_the_git_listed_ones_the_classifier_names(repo: Path) -> None:
    assert fast_path_files(repo) == ["HANDOVER.md", PLAN]


def test_every_fast_path_file_is_locked_and_nothing_else(repo: Path) -> None:
    assert lock(repo) == ["HANDOVER.md", PLAN]
    assert [mode(repo / name) for name in ("HANDOVER.md", PLAN)] == [0, 0]
    untouched = (
        "docs/lq45-members.md",
        "packages/a.py",
        "README.md",
        "docs/superpowers/untracked.md",
    )
    assert [mode(repo / name) & stat.S_IRUSR for name in untouched] == [stat.S_IRUSR] * 4


def test_a_locked_file_refuses_a_python_read_and_still_exists(repo: Path) -> None:
    lock(repo)
    assert (repo / "HANDOVER.md").is_file()
    with pytest.raises(PermissionError):
        (repo / "HANDOVER.md").read_text(encoding="utf-8")


def test_a_locked_file_refuses_a_node_read_and_still_exists(repo: Path) -> None:
    assert NODE is not None, "node is not on the path: the lock's cross-language proof needs it"
    lock(repo)
    script = (
        "const fs = require('fs');"
        "console.log(fs.existsSync('HANDOVER.md'));"
        "try { fs.readFileSync('HANDOVER.md'); console.log('read'); }"
        "catch (error) { console.log(error.code); }"
    )
    done = subprocess.run(  # noqa: S603 - node, with a script written in the test
        [NODE, "-e", script], cwd=repo, capture_output=True, text=True, check=True
    )
    assert done.stdout == "true\nEACCES\n"


def test_no_fast_path_file_is_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bare = repo_with(tmp_path, "packages/a.py")
    (bare / "docs/superpowers/untracked.md").unlink()
    assert main([], bare) == 1
    assert capsys.readouterr().err == (
        "lock-fast-path: refused: git lists no file on the docs-only fast path, "
        "so there is nothing to lock and the lock would prove nothing\n"
    )


def test_a_lock_that_does_not_bite_is_refused_by_name(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """As root, or on a filesystem that ignores modes, chmod 000 stops nothing."""
    monkeypatch.setattr(Path, "chmod", no_chmod)
    assert main([], repo) == 1
    assert capsys.readouterr().err == (
        "lock-fast-path: refused: still readable after chmod 000: HANDOVER.md, "
        f"{PLAN} (root, or a filesystem that ignores modes, is not stopped by a lock)\n"
    )


def test_a_tree_git_cannot_list_is_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([], tmp_path) == 1
    err = capsys.readouterr().err
    assert err.startswith(
        "lock-fast-path: refused: cannot list the files: git ls-files exited 128: "
    )


def test_without_git_on_the_path_it_is_refused_by_name(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(repo / "no-tools-here"))
    with pytest.raises(LockError, match=r"^cannot list the files: git is not on the path$"):
        lock(repo)


def test_a_lock_reports_what_it_locked(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([], repo) == 0
    assert capsys.readouterr().out == "lock-fast-path: 2 files locked, none readable\n"


def test_it_takes_no_arguments(repo: Path) -> None:
    with pytest.raises(SystemExit, match=r"^usage: lock_fast_path\.py$"):
        main(["extra"], repo)


def test_the_workflow_command_runs_on_the_standard_library_alone(repo: Path) -> None:
    """CI runs it with the runner's system python3: -S drops site-packages and -E the PYTHON*
    variables, while the script's own directory stays on the path for ``ci_scope``."""
    done = subprocess.run(  # noqa: S603 - this interpreter, running the script under test
        [sys.executable, "-E", "-S", str(SCRIPT)],
        cwd=repo,
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (
        0,
        "lock-fast-path: 2 files locked, none readable\n",
        "",
    )
    assert mode(repo / "HANDOVER.md") == 0


def test_run_as_a_script_it_locks_the_working_directory(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exited.value.code == 0
    assert capsys.readouterr().out == "lock-fast-path: 2 files locked, none readable\n"
    assert mode(repo / PLAN) == 0
```


- [ ] **Step 3: Write the stubs and the configuration.**

**`pyproject.toml`** (changed; configuration, needed to collect the tests: 3 edits)

<!-- edit: pyproject.toml -->
Replace:
```toml
# Specs and plans hold hand-aligned sketches for reading, not shipped code; READMEs stay checked.
extend-exclude = ["docs/superpowers"]

```
with:
```toml
# Specs and plans hold hand-aligned sketches for reading, not shipped code; READMEs stay checked.
# Both are on CI's docs-only fast path (#218), where nothing runs ruff: ruff formats Markdown, and
# the fast-path lock found `ruff format --check` reading HANDOVER.md (#264).
extend-exclude = ["docs/superpowers", "HANDOVER.md"]

```

<!-- edit: pyproject.toml -->
Replace:
```toml
[tool.ruff.lint.isort]
known-first-party = ["steadyhand", "steadyhand_idx", "set_dev_version", "ci_scope"]

```
with:
```toml
[tool.ruff.lint.isort]
known-first-party = ["steadyhand", "steadyhand_idx", "set_dev_version", "ci_scope", "lock_fast_path"]

```

<!-- edit: pyproject.toml -->
Replace:
```toml
branch = true
source_pkgs = ["steadyhand", "steadyhand_idx", "ci_scope"]

```
with:
```toml
branch = true
source_pkgs = ["steadyhand", "steadyhand_idx", "ci_scope", "lock_fast_path"]

```

**`scripts/lock_fast_path.py`** (new, as stubs)

<!-- file: scripts/lock_fast_path.py -->
```python
"""Make every file on CI's docs-only fast path unreadable before a full run's later steps (#264).

Usage: python3 scripts/lock_fast_path.py

``scripts/ci_scope.py`` lets a pull request that only adds or edits files on the fast path skip
the tests, which is safe only while no test reads them. On every full run, each gated job runs
this right after its scope step: every git-listed fast-path file becomes ``chmod 000``, so a later
step that reads one fails by name in any language (Python raises ``PermissionError``, Node
``EACCES``), while existence checks and directory listings still work. The fast path is
``ci_scope.on_fast_path``, its one home. Anything that would leave a reader unseen fails the job:
no file to lock, a tree git cannot list, or a lock that does not bite (root, or a filesystem that
ignores modes).

Standard library only: it runs on the runner's system ``python3`` before uv is installed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from ci_scope import on_fast_path

USAGE = "usage: lock_fast_path.py"


class LockError(Exception):
    """The fast path could not be locked, so a reader could go unseen."""


def fast_path_files(repo: Path) -> list[str]:
    """Every file git lists in *repo* that is on the docs-only fast path, in git's order."""
    raise NotImplementedError("fast_path_files")


def _readable(path: Path) -> bool:
    raise NotImplementedError("_readable")


def lock(repo: Path) -> list[str]:
    """Lock every fast-path file in *repo* and prove none can be read; return their names."""
    raise NotImplementedError("lock")


def main(argv: list[str], repo: Path) -> int:
    if argv:
        raise SystemExit(USAGE)
    try:
        names = lock(repo)
    except LockError as error:
        print(f"lock-fast-path: refused: {error}", file=sys.stderr)
        return 1
    print(f"lock-fast-path: {len(names)} files locked, none readable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], Path.cwd()))
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider --continue-on-collection-errors`

Expected: 2336 tests, 11 failed, by kind {'AssertionError': 1, 'NotImplementedError': 10}. Ten failures are the stub's `NotImplementedError`; the eleventh is the `python -E -S` entry-point test failing on its own assertion (the subprocess reports the stub's traceback). `test_it_takes_no_arguments` passes against the stubs: stubgen keeps `main`, which the `__main__` guard calls, and its argument check is real. Mutation L6 turns it red.

<!-- check: red total=2336 failed=11 -->

- [ ] **Step 5: Implement.**

**`scripts/lock_fast_path.py`** (replaces the stubs)

<!-- file: scripts/lock_fast_path.py -->
```python
"""Make every file on CI's docs-only fast path unreadable before a full run's later steps (#264).

Usage: python3 scripts/lock_fast_path.py

``scripts/ci_scope.py`` lets a pull request that only adds or edits files on the fast path skip
the tests, which is safe only while no test reads them. On every full run, each gated job runs
this right after its scope step: every git-listed fast-path file becomes ``chmod 000``, so a later
step that reads one fails by name in any language (Python raises ``PermissionError``, Node
``EACCES``), while existence checks and directory listings still work. The fast path is
``ci_scope.on_fast_path``, its one home. Anything that would leave a reader unseen fails the job:
no file to lock, a tree git cannot list, or a lock that does not bite (root, or a filesystem that
ignores modes).

Standard library only: it runs on the runner's system ``python3`` before uv is installed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from ci_scope import on_fast_path

USAGE = "usage: lock_fast_path.py"


class LockError(Exception):
    """The fast path could not be locked, so a reader could go unseen."""


def fast_path_files(repo: Path) -> list[str]:
    """Every file git lists in *repo* that is on the docs-only fast path, in git's order."""
    git = shutil.which("git")
    if git is None:
        msg = "cannot list the files: git is not on the path"
        raise LockError(msg)
    done = subprocess.run(  # noqa: S603 - git, with arguments this script chooses
        [git, "ls-files", "-z"], cwd=repo, capture_output=True, check=False
    )
    if done.returncode != 0:
        stderr = " ".join(done.stderr.decode("utf-8", errors="replace").split())
        msg = f"cannot list the files: git ls-files exited {done.returncode}: {stderr}"
        raise LockError(msg)
    names = (name.decode("utf-8") for name in done.stdout.split(b"\0") if name)
    return [name for name in names if on_fast_path(name)]


def _readable(path: Path) -> bool:
    try:
        path.open("rb").close()
    except PermissionError:
        return False
    return True


def lock(repo: Path) -> list[str]:
    """Lock every fast-path file in *repo* and prove none can be read; return their names."""
    names = fast_path_files(repo)
    if not names:
        msg = (
            "git lists no file on the docs-only fast path, "
            "so there is nothing to lock and the lock would prove nothing"
        )
        raise LockError(msg)
    for name in names:
        (repo / name).chmod(0)
    readable = [name for name in names if _readable(repo / name)]
    if readable:
        msg = (
            f"still readable after chmod 000: {', '.join(readable)} "
            "(root, or a filesystem that ignores modes, is not stopped by a lock)"
        )
        raise LockError(msg)
    return names


def main(argv: list[str], repo: Path) -> int:
    if argv:
        raise SystemExit(USAGE)
    try:
        names = lock(repo)
    except LockError as error:
        print(f"lock-fast-path: refused: {error}", file=sys.stderr)
        return 1
    print(f"lock-fast-path: {len(names)} files locked, none readable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], Path.cwd()))
```


- [ ] **Step 6: Run the whole gate** (as **The gate** says).

Expected: every step exits 0; 2336 passed on 3.12 and on 3.13, branch coverage 100% (verified on `62d17bc`).

<!-- check: gate total=2336 passed=2336 -->

- [ ] **Step 7: Mutations.** Run L1–L6 from **Mutation checks**.
- [ ] **Step 8: Commit** `feat(ci): #264 the docs-only fast-path lock, and ruff no longer reads the handover (Refs #264)`.

---

### Task 2: Lock the fast path third in every gated job

**Acceptance criteria (story text):** AC1 (the step), AC4 (the wiring guard, with a gated job's container never run as root: #264 issuecomment-6015764109), AC5 (measured on a locked tree before merge; the count in every gated job after).

**Files:**
- Modify: `.github/workflows/ci.yml`, `tests/meta/test_ci_fast_path.py`

**Interfaces:**
- Consumes: Task 1's `scripts/lock_fast_path.py`.
- Produces: the step `Lock the docs-only fast path: no later step may read it` third in every gated job; in the guard, `container_user(container) -> str | None` and `runs_as_root(container) -> bool`.

- [ ] **Step 1: Write the failing guard.**

**`tests/meta/test_ci_fast_path.py`** (changed: 4 edits)

<!-- edit: tests/meta/test_ci_fast_path.py -->
Replace:
```python

from pathlib import Path
```
with:
```python

import re
from pathlib import Path
```

<!-- edit: tests/meta/test_ci_fast_path.py -->
Replace:
```python
EVENT = "${{ github.event_name }}"
# Measured on 2026-10-06 (#218): 4 gated jobs whose later steps number 19. Lower each only by
# a deliberate edit when the workflow shrinks.
GATED_FLOOR = 3
SKIPPED_STEPS_FLOOR = 18

```
with:
```python
EVENT = "${{ github.event_name }}"
LOCK = {
    "name": "Lock the docs-only fast path: no later step may read it",
    "if": SKIP,
    "run": "python3 scripts/lock_fast_path.py",
}
# Measured on 2026-10-06 (#218, #264): 4 gated jobs whose later steps number 23, the lock included.
# Lower each only by a deliberate edit when the workflow shrinks.
GATED_FLOOR = 3
SKIPPED_STEPS_FLOOR = 22

```

<!-- edit: tests/meta/test_ci_fast_path.py -->
Replace:
```python
@pytest.mark.parametrize("name", GATED)
def test_a_gated_job_reports_and_skips_every_later_step(name: str) -> None:
```
with:
```python
@pytest.mark.parametrize("name", GATED)
def test_a_gated_job_locks_the_fast_path_before_any_other_step(name: str) -> None:
    """On a full run, every fast-path file is unreadable from the third step on, so a reader in
    any language fails by name (#264). Checkout and scope come first: both read the tree."""
    assert JOBS[name]["steps"][2] == LOCK


# The user flag in a `container:`'s Docker options, spelled either way Docker accepts.
USER_FLAG = re.compile(r"(?:^|\s)(?:--user|-u)(?:=|\s+)(\S+)")
ROOT_USERS = frozenset({"0", "root"})


def container_user(container: object) -> str | None:
    """The user a job's ``container:`` runs as, from its options; None when unset, which leaves
    the image's default user (root, for Playwright's image)."""
    options = container.get("options", "") if isinstance(container, dict) else ""
    found = USER_FLAG.search(str(options))
    return found[1] if found else None


def runs_as_root(container: object) -> bool:
    user = container_user(container)
    return user is None or user.split(":")[0] in ROOT_USERS


@pytest.mark.parametrize(
    ("container", "root"),
    [
        pytest.param("mcr.microsoft.com/playwright:v1.55.0-noble", True, id="an-image-alone"),
        pytest.param({"image": "node:24"}, True, id="no-options"),
        pytest.param({"image": "node:24", "options": "--ipc=host --init"}, True, id="no-user"),
        pytest.param(
            {"image": "node:24", "options": "--ulimit nofile=1024"}, True, id="ulimit-is-not-u"
        ),
        pytest.param({"image": "node:24", "options": "--user 0"}, True, id="uid-0"),
        pytest.param({"image": "node:24", "options": "--user root"}, True, id="root-by-name"),
        pytest.param({"image": "node:24", "options": "--user 0:0"}, True, id="uid-0-with-group"),
        pytest.param({"image": "node:24", "options": "--user=1001"}, False, id="user-equals"),
        pytest.param(
            {"image": "node:24", "options": "--ipc=host --user 1001:1001"}, False, id="uid-and-gid"
        ),
        pytest.param({"image": "node:24", "options": "-u pwuser"}, False, id="short-flag-by-name"),
    ],
)
def test_a_container_runs_as_root_unless_its_options_name_another_user(
    container: object, *, root: bool
) -> None:
    assert runs_as_root(container) is root


@pytest.mark.parametrize("name", GATED)
def test_a_gated_job_runs_no_container_as_root(name: str) -> None:
    """The lock is chmod 000, which root ignores, and container images often run as root by
    default (Playwright's does). Least privilege keeps the lock biting (#264)."""
    container = JOBS[name].get("container")
    assert container is None or not runs_as_root(container), (
        f"{name} runs its container as root: give it `options: --user <a non-root uid>`"
    )


@pytest.mark.parametrize("name", GATED)
def test_a_gated_job_reports_and_skips_every_later_step(name: str) -> None:
```

<!-- edit: tests/meta/test_ci_fast_path.py -->
Replace:
```python
    steps = JOBS[name]["steps"]
    scoped = [step for step in steps if step.get("id") == "scope" or SKIP in str(step.get("if"))]
    assert searched(scoped, of=len(steps), what=f"steps of {name}") == []
```
with:
```python
    steps = JOBS[name]["steps"]
    scoped = [
        step
        for step in steps
        if step.get("id") == "scope" or SKIP in str(step.get("if")) or step == LOCK
    ]
    assert searched(scoped, of=len(steps), what=f"steps of {name}") == []
```


- [ ] **Step 2: Run the whole suite and watch it fail.**

Expected: 2354 tests, 5 failed, by kind {'AssertionError': 4, 'assert 19 >= 22': 1}. Each failure is the guard's own assertion against the unchanged workflow: no lock step third in each of the four gated jobs, and the skipped steps (19) under the new floor (22). The ten container-parser cases and the four per-job container checks pass, as they should: they test a helper in the guard itself, and no gated job runs a container today. Mutations W9-W12 prove each can fail.

<!-- check: red total=2354 failed=5 -->

- [ ] **Step 3: Add the step.**

**`.github/workflows/ci.yml`** (changed: 4 edits)

<!-- edit: .github/workflows/ci.yml -->
Replace:
```yaml
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
```
with:
```yaml
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          fetch-depth: 2
      - name: "Scope: may this docs-only change skip the rest?"
        id: scope
        env:
          EVENT_NAME: ${{ github.event_name }}
        run: python3 scripts/ci_scope.py "$EVENT_NAME"
      - name: "Lock the docs-only fast path: no later step may read it"
        if: steps.scope.outputs.docs_only != 'true'
        run: python3 scripts/lock_fast_path.py
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        if: steps.scope.outputs.docs_only != 'true'
        with:
          version: ${{ env.UV_VERSION }}
          python-version: "3.12"
          enable-cache: true
      - run: uv sync --locked
        if: steps.scope.outputs.docs_only != 'true'
      - run: uv run --locked ruff check
```

<!-- edit: .github/workflows/ci.yml -->
Replace:
```yaml
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
```
with:
```yaml
      - name: "Scope: may this docs-only change skip the rest?"
        id: scope
        env:
          EVENT_NAME: ${{ github.event_name }}
        run: python3 scripts/ci_scope.py "$EVENT_NAME"
      - name: "Lock the docs-only fast path: no later step may read it"
        if: steps.scope.outputs.docs_only != 'true'
        run: python3 scripts/lock_fast_path.py
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        if: steps.scope.outputs.docs_only != 'true'
        with:
          version: ${{ env.UV_VERSION }}
          python-version: ${{ matrix.python }}
```

<!-- edit: .github/workflows/ci.yml -->
Replace:
```yaml
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
```
with:
```yaml
          fetch-depth: 2
      - name: "Scope: may this docs-only change skip the rest?"
        id: scope
        env:
          EVENT_NAME: ${{ github.event_name }}
        run: python3 scripts/ci_scope.py "$EVENT_NAME"
      - name: "Lock the docs-only fast path: no later step may read it"
        if: steps.scope.outputs.docs_only != 'true'
        run: python3 scripts/lock_fast_path.py
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        if: steps.scope.outputs.docs_only != 'true'
        with:
          version: ${{ env.UV_VERSION }}
          python-version: "3.12"
          enable-cache: true
```

<!-- edit: .github/workflows/ci.yml -->
Replace:
```yaml
        run: python3 scripts/ci_scope.py "$EVENT_NAME"
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
```
with:
```yaml
        run: python3 scripts/ci_scope.py "$EVENT_NAME"
      - name: "Lock the docs-only fast path: no later step may read it"
        if: steps.scope.outputs.docs_only != 'true'
        run: python3 scripts/lock_fast_path.py
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
```


- [ ] **Step 4: Run the whole gate**, and `actionlint` over every workflow.

Expected: every step exits 0; 2354 passed on 3.12 and on 3.13, branch coverage 100% (verified on `1742115`).

<!-- check: gate total=2354 passed=2354 -->

- [ ] **Step 5: Mutations.** Run W7–W12 from **Mutation checks**.
- [ ] **Step 6: Measure on a locked tree:** run every gated step with the fast path locked (`.superpowers/sdd/264-lock/measure_locked.sh`) and confirm each exits 0.

Measured on the final commit, locked by the real script (`lock-fast-path: 23 files locked, none readable`): lock, ruff, format, mypy, pytest312, pytest313, build, wheels, export, audit each exited 0. The perf step once ran over its budget (32.2 s against 30 s) with the machine's load average between 29 and 47 from other sessions, and with no permission error in its output; measured again on the same locked tree at load 46 to 47, its 12 tests passed. Its time, not the lock, was the cause. A planted pytest test reading `HANDOVER.md` then failed with `PermissionError`. Measured the same way on `develop` before this story, every step passed except `ruff format --check`, which read `HANDOVER.md` and exited 2: the finding Task 1 fixes.

- [ ] **Step 7: Commit** `feat(ci): #264 lock the fast path third in every gated job (Refs #264)`, push, open the PR, and merge on green.

---

## The gate

`uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error -m perf -p no:cacheprovider`, and the same coverage run on 3.13 in its own environment. Each must exit 0.

## Mutation checks

Each mutation was predicted (the exact failing tests) before it ran, and turned exactly those red with the total unchanged.

| Mutation | What it breaks | Red | Total |
|---|---|---|---|
| L1 | the lock misses the handover | 8 | 46 |
| L2 | chmod skipped (the self-check must refuse) | 6 | 46 |
| L3 | the self-check removed | 1 | 46 |
| L4 | nothing to lock accepted | 1 | 46 |
| L5 | a git failure unchecked | 1 | 46 |
| L6 | arguments accepted | 1 | 46 |
| W7 | the lock missing from the first gated job | 1 | 46 |
| W8 | the lock moved after setup-uv in the first gated job | 1 | 46 |
| W9 | a root container on the first gated job | 1 | 46 |
| W10 | the parser blind to -u | 1 | 46 |
| W11 | uid 0 not counted as root | 2 | 46 |
| W12 | an unset user taken as non-root | 4 | 46 |

## Plan review log

Each pass ran the mechanical checks first: every name in the Interfaces blocks found exactly once in the code, the commit subjects matched, the mutation ranges matched the table, no placeholder left, and `check_plan.py` rebuilt both tasks from this document's own text, ran each red phase and gate, and compared each tree with its verified commit. Then the document was read against its sources.

- **Pass 1** (replay: 0 problems, both trees identical). No findings.
- **Pass 2** (prose against sources). 1 finding: "Node (preinstalled on the runner)" had not been read. It was read from actions/runner-images (the Ubuntu 24.04 image lists Node.js 22.23.3) and cited. That changed only prose, and the re-render differs from the replayed plan in that one line.
- **Pass 3**: no findings. Checked that no gated step runs git after the lock: the only git calls are the four scope steps, which come before it. The plan is approved under Shyden's rule (plans reviewed to zero, then self-approved).

Found while building, each in the code above, not a plan defect: `ruff format --check` reading `HANDOVER.md` (the lock's first measurement; Task 1 excludes it); root containers, which a side agent raised (Task 2's container rule, mutations W9–W12); and the perf step's single over-budget run under machine load, read as timing and not the lock (see Task 2, Step 6).
