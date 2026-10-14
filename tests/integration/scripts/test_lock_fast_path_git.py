"""The lock on CI's docs-only fast path against real git and a real Node (#264, moved out of
unit by #286): the files a real repository lists (an untracked plan is not), the lock refusing a
Node read, a tree git cannot list, and the workflow command run by the runner's bare interpreter.
The lock's logic, with git stood in, is unit-tested in ``tests/scripts/test_lock_fast_path.py``.
"""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from lock_fast_path import fast_path_files, lock, main

GIT = shutil.which("git")
NODE = shutil.which("node")
SCRIPT = Path(__file__).resolve().parents[3] / "scripts/lock_fast_path.py"
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


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_the_fast_path_files_are_the_git_listed_ones_the_classifier_names(repo: Path) -> None:
    assert fast_path_files(repo) == ["HANDOVER.md", PLAN]


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


def test_a_tree_git_cannot_list_is_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([], tmp_path) == 1
    err = capsys.readouterr().err
    assert err.startswith(
        "lock-fast-path: refused: cannot list the files: git ls-files exited 128: "
    )


def test_a_lock_reports_what_it_locked(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([], repo) == 0
    assert capsys.readouterr().out == "lock-fast-path: 2 files locked, none readable\n"


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
