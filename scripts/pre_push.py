"""The pre-push checks (#377): format, lint and types for the Python and the extension, and no
test suite (the laptop runs the unit suites by hand before each push; every other suite is CI's).

Usage: git runs ``.githooks/pre-push``, which runs ``uv run --no-project scripts/pre_push.py``,
once a clone has run ``git config core.hooksPath .githooks`` (README.md, Setting up a clone).

The checks read the files on disk, so the push is refused, before any check runs, unless those
files are the commit being pushed: nothing uncommitted or untracked, and every branch pushed at
the checked-out commit (Shyden, 2026-10-28). Then every check runs, from the repository root or
the extension folder with its output captured, and each one that failed is named with what it
printed. Standard library only: it runs outside the project, so a clone that has synced nothing
still gets a named refusal.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# githooks(5): git writes "<local ref> <local commit> <remote ref> <remote commit>" a line, and
# a deleted branch as "(delete)" with an all-zero commit name.
PUSH_FIELDS = 4
DELETED = "(delete)"
# `git status --porcelain=v1`: two status letters and a space before each path.
STATUS_WIDTH = 3


@dataclass(frozen=True)
class Check:
    name: str
    folder: str
    command: tuple[str, ...]


CHECKS = (
    Check("ruff check", ".", ("uv", "run", "--locked", "ruff", "check")),
    Check("ruff format", ".", ("uv", "run", "--locked", "ruff", "format", "--check")),
    Check("mypy", ".", ("uv", "run", "--locked", "mypy")),
    Check("extension lint", "extension", ("npm", "run", "lint")),
    Check("extension format", "extension", ("npm", "run", "format:check")),
    Check("extension typecheck", "extension", ("npm", "run", "typecheck")),
)


@dataclass(frozen=True)
class Outcome:
    check: Check
    returncode: int
    output: str


def run(root: Path, check: Check) -> Outcome:
    """Run *check* from its folder under *root*. A tool not on the path fails the check, named,
    and starts nothing."""
    tool = shutil.which(check.command[0])
    if tool is None:
        return Outcome(check, 127, f"{check.command[0]} is not on the path\n")
    done = subprocess.run(  # noqa: S603 - one of the CHECKS commands above
        [tool, *check.command[1:]], cwd=root / check.folder, capture_output=True, check=False
    )
    output = (done.stdout + done.stderr).decode("utf-8", errors="replace")
    return Outcome(check, done.returncode, output)


def report(outcome: Outcome) -> str:
    check = outcome.check
    output = outcome.output if outcome.output.endswith("\n") else outcome.output + "\n"
    return (
        f"pre-push: {check.name} failed (exit {outcome.returncode}): "
        f"{' '.join(check.command)}, in {check.folder}/\n{output}"
    )


def run_checks(root: Path, checks: Sequence[Check]) -> list[Outcome]:
    """Run every one of *checks*, in order, after any failure too, so a refused push names
    every check that failed (Shyden, 2026-10-28)."""
    return [run(root, check) for check in checks]


class RefusedError(Exception):
    """The files on disk may not be the commit being pushed, so no check would judge it."""


def pushed_commits(stdin: str) -> list[tuple[str, str]]:
    """Each ``(local ref, commit)`` git is pushing, from the lines it writes to the hook
    (``githooks(5)``): four fields each. A deleted branch pushes no commit, so it is passed
    over; any other line is refused."""
    found: list[tuple[str, str]] = []
    for line in stdin.splitlines():
        fields = line.split(" ")
        if len(fields) != PUSH_FIELDS:
            msg = f"cannot read what git is pushing: {line!r}"
            raise RefusedError(msg)
        local_ref, commit = fields[0], fields[1]
        if local_ref != DELETED or commit.strip("0"):
            found.append((local_ref, commit))
    return found


def git(root: Path, *args: str) -> bytes:
    tool = shutil.which("git")
    if tool is None:
        msg = "git is not on the path"
        raise RefusedError(msg)
    done = subprocess.run(  # noqa: S603 - git, with the arguments written below
        [tool, *args], cwd=root, capture_output=True, check=False
    )
    if done.returncode != 0:
        said = done.stderr.decode("utf-8", errors="replace").strip()
        msg = f"git {args[0]} exited {done.returncode}: {said}"
        raise RefusedError(msg)
    return done.stdout


def refuse_unless_clean(root: Path, pushing: Sequence[tuple[str, str]]) -> None:
    """Refuse unless the files on disk are the commit being pushed."""
    status = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if status:
        first = status.split(b"\0", 1)[0]
        if not status.endswith(b"\0") or len(first) <= STATUS_WIDTH:
            msg = f"cannot read git status: {status!r}"
            raise RefusedError(msg)
        path = first[STATUS_WIDTH:].decode("utf-8", errors="replace")
        msg = (
            f"the tree has uncommitted changes, the first {path}: the checks read the files "
            "on disk, so commit or stash every change before pushing"
        )
        raise RefusedError(msg)
    head = git(root, "rev-parse", "HEAD").decode("ascii", errors="replace").strip()
    for local_ref, commit in pushing:
        if commit != head:
            msg = (
                f"{local_ref} is at {commit}, not the checked-out commit {head}: the checks "
                "read the checked-out files, so check out each branch you push"
            )
            raise RefusedError(msg)


def main(root: Path, stdin: str) -> int:
    try:
        refuse_unless_clean(root, pushed_commits(stdin))
    except RefusedError as refusal:
        sys.stderr.write(f"pre-push: refused: {refusal}\n")
        return 1
    outcomes = run_checks(root, CHECKS)
    failed = [outcome for outcome in outcomes if outcome.returncode != 0]
    for outcome in failed:
        sys.stderr.write(report(outcome))
    if failed:
        return 1
    sys.stderr.write(f"pre-push: {len(outcomes)} checks passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(ROOT, sys.stdin.read()))
