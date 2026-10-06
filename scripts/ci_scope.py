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
    paths = "1 path" if len(found) == 1 else f"{len(found)} paths"
    return Verdict(docs_only=True, reason=f"docs-only: {paths}, all on the fast path")


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
