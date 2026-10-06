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
