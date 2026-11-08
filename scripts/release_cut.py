"""Judge a pull request into ``main`` (#400, shyden-labs/repo-template#86).

Usage: uv run --no-project scripts/release_cut.py <head repository> <head ref> <40-hex head sha>
<pull request number>

``main`` takes only a frozen ``release/*`` cut, by merge commit. ``main`` is not strict, because
each release merge lands on ``main`` and never on squash-only ``develop``, so from the second
release on a strict ``main`` would refuse every cut. This check proves instead what strict
proved, that what lands is what CI tested:

  (a) the head branch is a ``release/`` branch, and origin holds it at the head;
  (b) the head is on ``origin/develop``, where CI tested it;
  (c) the pull request's merge ref is GitHub's merge of the head into ``main``, and it lands
      exactly the head's tree;
  (d) every commit ``main`` holds beyond ``develop`` is a two-parent merge whose second parent is
      on ``develop``, so ``main`` never took anything else.

Run by ``.github/workflows/release-cut.yml`` from the default branch's own copy
(``pull_request_target``), never the pull request's: it fetches the pull request's merge ref as
git data, runs none of its code, and posts its verdict as the ``release-cut`` commit status on
the head, which ``main`` requires. A status belongs to a SHA, which a fork's pull request can
share with a release's, so a pull request from any other repository is refused before anything
is posted. Ported from the template's ``scripts/release-cut.ts``; ``RELEASING.md`` says how the
rules are set.

Standard library only: it runs outside the project, on the ``.python-version`` pin uv installs.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.request import Request, urlopen

RELEASE_CUT = "release-cut"
# Where the pull request's merge commit is fetched to.
MERGE_REF = "refs/remotes/pull/merge"
USAGE = "usage: release_cut.py <head repository> <head ref> <40-hex head sha> <pull request number>"
# GitHub refuses a commit status description longer than this.
DESCRIPTION_LIMIT = 140
# A release merge, and GitHub's merge ref, has two parents: main's tip, then the cut.
MERGE_PARENTS = 2
ARGUMENTS = 4
DEVELOP = "origin/develop"
DEVELOP_BRANCH = "refs/heads/develop"
BEYOND_DEVELOP = "origin/develop..origin/main"
SHA = re.compile(r"[0-9a-f]{40}")
PULL_NUMBER = re.compile(r"[1-9][0-9]*")
REMOTE_LINE = re.compile(r"([0-9a-f]{40})\t(refs/[^\t]+)")
ENV = ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "GITHUB_API_URL", "GITHUB_SERVER_URL", "GITHUB_RUN_ID")


class ReleaseCutError(Exception):
    """The merge is refused, or could not be judged; the message says why."""


@dataclass(frozen=True)
class MainCommit:
    """A commit ``main`` holds that ``develop`` lacks; ``second_parent_on_develop`` is ``None``
    unless it has two parents."""

    sha: str
    parents: tuple[str, ...]
    second_parent_on_develop: bool | None


@dataclass(frozen=True)
class Facts:
    """What git says about the pull request, as ``gather_facts`` reads it."""

    head_ref: str
    head_sha: str
    # Where origin's ``refs/heads/<head_ref>`` is now; ``None`` when origin holds no such branch.
    origin_head_sha: str | None
    head_on_develop: bool
    # The merge ref's parents: main's tip, then the head.
    merge_parents: tuple[str, ...]
    merge_tree: str
    head_tree: str
    main_commits: tuple[MainCommit, ...]


@dataclass(frozen=True)
class Status:
    """The commit status a verdict posts; GitHub shows its description beside the check."""

    state: str
    description: str


def audit(facts: Facts) -> list[str]:
    """Every reason the merge is not a release cut, in the order (a)-(d); empty when it is one."""
    problems: list[str] = []
    if not re.match(r"release/.", facts.head_ref):
        problems.append(f"the head branch is {facts.head_ref}, not a release/ branch")
    if facts.origin_head_sha is None:
        problems.append(f"origin holds no branch {facts.head_ref}")
    elif facts.origin_head_sha != facts.head_sha:
        problems.append(
            f"origin's {facts.head_ref} is at {facts.origin_head_sha}, "
            f"not the head {facts.head_sha}"
        )
    if not facts.head_on_develop:
        problems.append(f"the head {facts.head_sha} is not on {DEVELOP}")
    if len(facts.merge_parents) != MERGE_PARENTS or facts.merge_parents[1] != facts.head_sha:
        problems.append(
            f"the checked-out commit is not GitHub's merge of the head {facts.head_sha} into main "
            f"(its parents: {' '.join(facts.merge_parents)})"
        )
    if facts.merge_tree != facts.head_tree:
        problems.append(
            f"the merge would land tree {facts.merge_tree}, not the head's tree {facts.head_tree}"
        )
    for commit in facts.main_commits:
        count = len(commit.parents)
        if count != MERGE_PARENTS:
            plural = "" if count == 1 else "s"
            problems.append(
                f"main holds {commit.sha}, which has {count} parent{plural}, "
                "not a merge of a release cut"
            )
        elif commit.second_parent_on_develop is not True:
            problems.append(
                f"main holds the merge {commit.sha}, whose second parent {commit.parents[1]} "
                f"is not on {DEVELOP}"
            )
    return problems


def parse_parents(text: str) -> list[tuple[str, tuple[str, ...]]]:
    """Read ``git rev-list --parents``: each line a commit then its parents, all 40 hex."""
    if text == "":
        return []
    # Only git's final newline is dropped: any other empty line is unreadable.
    commits = []
    for line in text.removesuffix("\n").split("\n"):
        shas = line.split(" ")
        if not all(SHA.fullmatch(sha) for sha in shas):
            msg = f"unreadable rev-list line: {line}"
            raise ReleaseCutError(msg)
        commits.append((shas[0], tuple(shas[1:])))
    return commits


def parse_remote_head(text: str, ref: str, question: str) -> str | None:
    """Where origin holds *ref*, from ``git ls-remote`` asked for develop and *ref*. ls-remote
    matches each pattern by its tail, so only a line naming *ref* exactly is it. develop is always
    there: an answer without it is not read as *ref*'s absence."""
    lines = [] if text == "" else text.removesuffix("\n").split("\n")
    refs = []
    for line in lines:
        match = REMOTE_LINE.fullmatch(line)
        if match is None:
            msg = f"unreadable ls-remote line: {line}"
            raise ReleaseCutError(msg)
        refs.append((match[1], match[2]))
    if not any(name == DEVELOP_BRANCH for _, name in refs):
        msg = f"git {question} named no {DEVELOP_BRANCH}, so its answer cannot be read"
        raise ReleaseCutError(msg)
    named = [sha for sha, name in refs if name == ref]
    if len(named) > 1:
        msg = f"git {question} named {ref} twice"
        raise ReleaseCutError(msg)
    return named[0] if named else None


def _git(*args: str, allowed: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git")
    if git is None:
        msg = "release-cut needs git on the PATH"
        raise ReleaseCutError(msg)
    done = subprocess.run(  # noqa: S603 - git, with arguments this script chooses
        [git, *args], capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL
    )
    if done.returncode not in allowed:
        msg = f"git {' '.join(args)} failed: {done.stderr.strip()}"
        raise ReleaseCutError(msg)
    return done


def _on_develop(sha: str) -> bool:
    """Whether *sha* is on develop: git answers 0 (yes) or 1 (no); anything else is an error,
    never a no."""
    return _git("merge-base", "--is-ancestor", sha, DEVELOP, allowed=(0, 1)).returncode == 0


def gather_facts(head_ref: str, head_sha: str, pull_number: int) -> Facts:
    """Fetch the pull request's merge ref as data, then ask git about it, the head and main."""
    _git("fetch", "--no-tags", "origin", f"+refs/pull/{pull_number}/merge:{MERGE_REF}")
    # The head ref is only a name the pull request gives, so origin is asked where it is now.
    remote = ("ls-remote", "origin", DEVELOP_BRANCH, f"refs/heads/{head_ref}")
    origin_head_sha = parse_remote_head(
        _git(*remote).stdout, f"refs/heads/{head_ref}", " ".join(remote)
    )
    head_on_develop = _on_develop(head_sha)
    merged = parse_parents(_git("rev-list", "--parents", "-n", "1", MERGE_REF).stdout)
    merge_parents = merged[0][1] if merged else ()
    merge_tree = _git("rev-parse", f"{MERGE_REF}^{{tree}}").stdout.strip()
    head_tree = _git("rev-parse", f"{head_sha}^{{tree}}").stdout.strip()
    main_commits = tuple(
        MainCommit(sha, parents, _on_develop(parents[1]) if len(parents) == MERGE_PARENTS else None)
        for sha, parents in parse_parents(_git("rev-list", "--parents", BEYOND_DEVELOP).stdout)
    )
    return Facts(
        head_ref,
        head_sha,
        origin_head_sha,
        head_on_develop,
        merge_parents,
        merge_tree,
        head_tree,
        main_commits,
    )


def _clip(text: str) -> str:
    return text if len(text) <= DESCRIPTION_LIMIT else f"{text[: DESCRIPTION_LIMIT - 1]}…"


def status_for(problems: list[str]) -> Status:
    """Success for a release cut; otherwise failure, naming the first reason and how many more
    the log holds."""
    if not problems:
        return Status("success", "a tested release cut: the merge lands the head's tree")
    first, rest = problems[0], len(problems) - 1
    return Status("failure", _clip(first if rest == 0 else f"{first} (and {rest} more in the log)"))


def _post(env: Mapping[str, str], head_sha: str, status: Status) -> None:
    """Post the verdict as the ``release-cut`` status on the head, failing unless GitHub took it."""
    url = f"{env['GITHUB_API_URL']}/repos/{env['GITHUB_REPOSITORY']}/statuses/{head_sha}"
    body = {
        "state": status.state,
        "description": status.description,
        "context": RELEASE_CUT,
        "target_url": (
            f"{env['GITHUB_SERVER_URL']}/{env['GITHUB_REPOSITORY']}/actions/runs/"
            f"{env['GITHUB_RUN_ID']}"
        ),
    }
    if not url.startswith("https://"):
        msg = f"release-cut posts only to an https:// GITHUB_API_URL, not {env['GITHUB_API_URL']}"
        raise ReleaseCutError(msg)
    request = Request(  # noqa: S310 - https alone, checked above
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {env['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30):  # noqa: S310 - https alone, checked above
            pass
    except urllib.error.HTTPError as error:
        msg = f"POST {url} answered {error.code}; the pull request has no {RELEASE_CUT} status"
        raise ReleaseCutError(msg) from error


def main(args: list[str], environ: Mapping[str, str]) -> int:
    """Judge the pull request, post the verdict on its head, and refuse a merge that is not a
    release cut."""
    if len(args) != ARGUMENTS or not SHA.fullmatch(args[2]) or not PULL_NUMBER.fullmatch(args[3]):
        raise ReleaseCutError(USAGE)
    head_repository, head_ref, head_sha, pull_number = args
    env = {}
    for name in ENV:
        value = environ.get(name, "")
        if value == "":
            msg = f"release-cut needs {name}, which GitHub Actions sets"
            raise ReleaseCutError(msg)
        env[name] = value
    # Any verdict, a failure too, would land on a SHA a release's pull request may share.
    if head_repository != env["GITHUB_REPOSITORY"]:
        msg = (
            f"release-cut posts nothing for a pull request from {json.dumps(head_repository)}: "
            "a release cut comes from this repository's own release/ branch, not a fork"
        )
        raise ReleaseCutError(msg)
    try:
        facts = gather_facts(head_ref, head_sha, int(pull_number))
    except ReleaseCutError as error:
        # A verdict git could not reach is posted as an error, so the pull request says why.
        _post(env, head_sha, Status("error", _clip(f"could not judge: {error}")))
        raise
    problems = audit(facts)
    _post(env, head_sha, status_for(problems))
    if problems:
        msg = "release-cut refuses this merge:\n  " + "\n  ".join(problems)
        raise ReleaseCutError(msg)
    print(
        f"release-cut: {head_ref} at {head_sha}; judged {len(facts.main_commits)} commit(s) in "
        f"{BEYOND_DEVELOP}; the merge lands the head's tree."
    )
    return 0


def run(args: list[str], environ: Mapping[str, str]) -> int:
    """``main``, with a refusal printed on stderr and exit status 1."""
    try:
        return main(args, environ)
    except ReleaseCutError as refused:
        print(refused, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:], os.environ))
