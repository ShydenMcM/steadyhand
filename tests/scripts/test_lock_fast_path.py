"""The lock on CI's docs-only fast path: on a full run, before any step that could read them, every
git-listed file a docs-only pull request may change without running the tests is made unreadable,
so a reader in any language fails by name (#264).

Measured on 2026-10-06 before writing it: after ``chmod 000``, Python raises ``PermissionError`` and
Node raises ``EACCES``, while ``is_file()``, ``existsSync`` and directory listing still work. A
deletion already runs everything (#218), so existence checks need no lock.

A unit test starts no process (#286): here git's listing is stood in (``tests/scripts/conftest.py``)
over files written straight to disk. The real git and Node cases are in
``tests/integration/scripts/test_lock_fast_path_git.py``.
"""

import runpy
import stat
import sys
from pathlib import Path

import pytest
from script_imports import imported_modules
from stood_in_git import FakeGit

from lock_fast_path import LockError, fast_path_files, lock, main

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/lock_fast_path.py"
PLAN = "docs/superpowers/plans/p.md"
LISTED = ("HANDOVER.md", PLAN, "docs/lq45-members.md", "packages/a.py", "README.md")


def listing(*names: str) -> bytes:
    """``git ls-files -z`` naming *names*."""
    return b"".join(name.encode("utf-8") + b"\0" for name in names)


def files(repo: Path, *names: str) -> None:
    for name in names:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path, fake_git: FakeGit) -> Path:
    """The listed files on disk and git listing them, beside a plan git does not list."""
    files(tmp_path, *LISTED, "docs/superpowers/unlisted.md")
    fake_git.stdout = listing(*LISTED)
    return tmp_path


def no_chmod(path: Path, mode: int, *, follow_symlinks: bool = True) -> None:
    """``Path.chmod`` as root sees it, near enough: nothing changes."""
    del path, mode, follow_symlinks


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_the_fast_path_files_are_the_ones_git_lists_that_the_classifier_names(
    repo: Path, fake_git: FakeGit
) -> None:
    assert fast_path_files(repo) == ["HANDOVER.md", PLAN]
    assert fake_git.called_in(repo, "ls-files", "-z")


def test_a_listed_name_keeps_its_accents(tmp_path: Path, fake_git: FakeGit) -> None:
    fake_git.stdout = listing("docs/superpowers/plans/café plan.md", "packages/a.py")
    assert fast_path_files(tmp_path) == ["docs/superpowers/plans/café plan.md"]


def test_every_fast_path_file_is_locked_and_nothing_else(repo: Path) -> None:
    assert lock(repo) == ["HANDOVER.md", PLAN]
    assert [mode(repo / name) for name in ("HANDOVER.md", PLAN)] == [0, 0]
    untouched = (
        "docs/lq45-members.md",
        "packages/a.py",
        "README.md",
        "docs/superpowers/unlisted.md",
    )
    assert [mode(repo / name) & stat.S_IRUSR for name in untouched] == [stat.S_IRUSR] * 4


def test_a_locked_file_refuses_a_python_read_and_still_exists(repo: Path) -> None:
    lock(repo)
    assert (repo / "HANDOVER.md").is_file()
    with pytest.raises(PermissionError):
        (repo / "HANDOVER.md").read_text(encoding="utf-8")


def test_no_fast_path_file_is_refused_by_name(
    tmp_path: Path, fake_git: FakeGit, capsys: pytest.CaptureFixture[str]
) -> None:
    files(tmp_path, "packages/a.py")
    fake_git.stdout = listing("packages/a.py")
    assert main([], tmp_path) == 1
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


def test_a_listing_git_refuses_is_refused_with_its_exit_code_and_message(
    tmp_path: Path, fake_git: FakeGit, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_git.returncode = 128
    fake_git.stderr = b"fatal: not a git repository\n  (or any of the parent directories)\n"
    assert main([], tmp_path) == 1
    assert capsys.readouterr().err == (
        "lock-fast-path: refused: cannot list the files: git ls-files exited 128: "
        "fatal: not a git repository (or any of the parent directories)\n"
    )


def test_without_git_on_the_path_it_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "no-tools-here"))
    with pytest.raises(LockError, match=r"^cannot list the files: git is not on the path$"):
        lock(tmp_path)


def test_a_lock_reports_what_it_locked(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([], repo) == 0
    assert capsys.readouterr().out == "lock-fast-path: 2 files locked, none readable\n"


def test_it_takes_no_arguments(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match=r"^usage: lock_fast_path\.py$"):
        main(["extra"], tmp_path)


def test_the_workflow_command_imports_the_standard_library_and_ci_scope_alone() -> None:
    """CI runs it with the runner's system python3, the script's own directory on the path for
    ``ci_scope``. The run under that bare interpreter is in the integration suite."""
    imported = imported_modules(SCRIPT)
    assert {"subprocess", "ci_scope"} <= imported
    assert sorted(imported - sys.stdlib_module_names - {"ci_scope"}) == []


def test_run_as_a_script_it_locks_the_working_directory(
    repo: Path,
    fake_git: FakeGit,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exited.value.code == 0
    assert capsys.readouterr().out == "lock-fast-path: 2 files locked, none readable\n"
    assert mode(repo / PLAN) == 0
    assert fake_git.called_in(repo, "ls-files", "-z")
