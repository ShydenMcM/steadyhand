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
