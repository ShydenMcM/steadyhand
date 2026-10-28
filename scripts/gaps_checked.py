"""Every commit carries its gap check (#378): the ``Gaps checked:`` section the global rule asks
for (Shyden, 2026-10-21, every project;
``~/.claude/global-rules/no-holes-check-before-and-after.md``), judged by the rule the Claude hook
``~/.claude/hooks/gaps-checked-in-commits.py`` checks. A commit of only ``.md`` files needs none.

Usage:
  ``gaps_checked.py commit-msg <message file>``: git's commit-msg hook (``.githooks/commit-msg``,
  installed by ``git config core.hooksPath .githooks``; README.md, Setting up a clone). It judges
  the message as git will keep it (comment lines and everything below the scissors line dropped)
  and the files the index holds against HEAD.
  ``gaps_checked.py range <base commit> <head commit>``: CI's ``gaps-checked`` job on a pull
  request, a required check. It judges every commit in ``base..head``, each by its own files
  against its first parent, and names each one without a whole section.
  ``gaps_checked.py landed <base commit> <head commit>``: the same job on a push to ``develop`` or
  ``main``, judging the commits the push landed on the branch's first-parent line (Shyden,
  2026-10-28, "Judge it at merge + after", then "First-parent on a push"): on ``develop`` the
  squash commit a merge writes, on ``main`` the release merge commit, so ``develop``'s commits
  are judged once, as they land there.

A git hook can be skipped (``git commit --no-verify``), so the CI check is the gate. The hook's
one known limit (Shyden, 2026-10-28, "Name it, CI is the gate"): git tells a commit-msg hook
nothing of ``--amend``, so an amend adding only ``.md`` files to a code commit is judged by what
it adds and passes without a section; the CI check, judging the amended commit against its
parent, refuses it. Standard library only: it runs outside the project, so a clone that has
synced nothing still gets a named refusal.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TEMPLATE = (
    "Gaps checked:\n"
    "- Before: <every way the change could let through what is refused today, each planted as a\n"
    "  failing test first>\n"
    "- After: <the attack on the diff, the old-vs-new verdicts, coverage of the changed code>\n"
    "- New passes: <each verdict the change turns into a pass and the ruling that allows it,"
    " or none>"
)
USAGE = (
    "usage: gaps_checked.py commit-msg <message file>"
    " | range <base commit> <head commit> | landed <base commit> <head commit>"
)
# The rule, as the global Claude hook checks it: the header alone on its line, then each entry a
# line starting "- <name>:", carried on by indented lines.
HEADER = re.compile(r"^Gaps checked:[ \t]*$", re.MULTILINE)
ENTRY = re.compile(r"^- (Before|After|New passes):(.*(?:\n(?!- |\S).*)*)", re.MULTILINE)
FILLER = frozenset({"na", "none", "tbd", "todo", "same", "nothing", "xxx", "see", "above", "etc"})
MIN_CHARACTERS = 20
MIN_WORDS = 3
MARKDOWN = ".md"
# git-commit(1), --cleanup: an edited message loses its comment lines and, with --verbose,
# everything from this line on.
COMMENT = "#"
SCISSORS = "# ------------------------ >8 ------------------------"
COMMENT_SETTINGS = ("core.commentChar", "core.commentString")
# `git config --get` exits 1 when the key is unset.
UNSET = 1
COMMIT_NAME = re.compile(r"[0-9a-f]{40}")


class RefusedError(Exception):
    """What the check would judge cannot be read, so nothing is judged."""


@dataclass(frozen=True)
class Verdict:
    commit: str
    subject: str
    problem: str | None


def section_problem(message: str) -> str | None:
    """Why *message*'s section is missing or incomplete, or ``None`` when it is whole."""
    header = HEADER.search(message)
    if header is None:
        return 'it has no "Gaps checked:" section'
    entries = {name: value.strip() for name, value in ENTRY.findall(message[header.end() :])}
    for name in ("Before", "After"):
        value = entries.get(name)
        if value is None:
            return f'its section has no "- {name}:" line'
        words = [w for w in re.findall(r"[A-Za-z]{2,}", value) if w.lower() not in FILLER]
        if len(value) < MIN_CHARACTERS or len(words) < MIN_WORDS:
            return f'its "- {name}:" line says too little to be a check ({value[:40]!r})'
    if not entries.get("New passes"):
        return 'its section has no "- New passes:" entry (write "none" when there is none)'
    return None


def cleaned(message: str) -> str:
    """*message* as git keeps an edited one: the scissors line and all below it dropped, and
    every line starting with the comment character."""
    kept: list[str] = []
    for line in message.splitlines(keepends=True):
        if line.rstrip("\n") == SCISSORS:
            break
        if not line.startswith(COMMENT):
            kept.append(line)
    return "".join(kept)


def only_markdown(files: list[str]) -> bool:
    return bool(files) and all(name.endswith(MARKDOWN) for name in files)


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    tool = shutil.which("git")
    if tool is None:
        msg = "git is not on the path"
        raise RefusedError(msg)
    return subprocess.run(  # noqa: S603 - git, with the arguments written below
        [tool, *args], cwd=root, capture_output=True, check=False
    )


def failed(args: tuple[str, ...], done: subprocess.CompletedProcess[bytes]) -> RefusedError:
    said = done.stderr.decode("utf-8", errors="replace").strip()
    return RefusedError(f"git {args[0]} exited {done.returncode}: {said}")


def git(root: Path, *args: str) -> str:
    done = run_git(root, *args)
    if done.returncode != 0:
        raise failed(args, done)
    return done.stdout.decode("utf-8", errors="replace")


def names(output: str) -> list[str]:
    """The paths of a ``-z`` listing: each ends in a NUL."""
    return output.split("\0")[:-1]


def refuse_another_comment_character(root: Path) -> None:
    """Git drops lines starting with the comment character from an edited message; one other
    than ``#`` would leave lines this hook reads but git does not keep."""
    for key in COMMENT_SETTINGS:
        args = ("config", "--get", key)
        done = run_git(root, *args)
        if done.returncode == UNSET:
            continue
        if done.returncode != 0:
            raise failed(args, done)
        value = done.stdout.decode("utf-8", errors="replace").strip()
        if value != COMMENT:
            msg = (
                f"{key} is {value!r}: git drops lines starting with it, which this hook cannot "
                "tell from the message, so set it back to '#'"
            )
            raise RefusedError(msg)


def commit_msg(root: Path, message_file: Path) -> str | None:
    """Why the commit being made lacks its section, or ``None``: the message in *message_file*
    as git will keep it, and the files the index holds against HEAD."""
    refuse_another_comment_character(root)
    try:
        message = message_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        msg = f"cannot read the message file {message_file}: {error}"
        raise RefusedError(msg) from error
    if only_markdown(names(git(root, "diff", "--cached", "--name-only", "--no-renames", "-z"))):
        return None
    return section_problem(cleaned(message))


def landed(root: Path, base: str, head: str, *, first_parent: bool) -> list[Verdict]:
    """A verdict on every commit in ``base..head``, or only those on *head*'s first-parent line,
    oldest first: its message as stored, judged unless its own files against its first parent
    are only markdown."""
    if not COMMIT_NAME.fullmatch(base) or not base.strip("0"):
        msg = f"the range starts at {base!r}, not a commit's full name"
        raise RefusedError(msg)
    if not COMMIT_NAME.fullmatch(head):
        msg = f"the range ends at {head!r}, not a commit's full name"
        raise RefusedError(msg)
    verdicts: list[Verdict] = []
    line = ("--first-parent",) if first_parent else ()
    for commit in git(root, "rev-list", "--reverse", *line, f"{base}..{head}").split():
        message = git(root, "log", "-1", "--format=%B", commit)
        # Against its first parent as two trees: diff-tree ignores --first-parent, and with -m
        # a merge would list its diff against every parent. A root commit has none.
        parents = git(root, "log", "-1", "--format=%P", commit).split()
        against = (parents[0], commit) if parents else ("--root", commit)
        files = names(
            git(
                root,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "--no-renames",
                "-r",
                "-z",
                *against,
            )
        )
        problem = None if only_markdown(files) else section_problem(message)
        verdicts.append(Verdict(commit, message.split("\n", 1)[0], problem))
    return verdicts


def hook(root: Path, message_file: Path) -> int:
    try:
        problem = commit_msg(root, message_file)
    except RefusedError as refusal:
        sys.stderr.write(f"commit-msg: refused: {refusal}\n")
        return 1
    if problem is None:
        return 0
    sys.stderr.write(
        f"commit-msg: refused: the message: {problem}.\n"
        "Every commit message carries this section (#378), unless the commit holds only .md"
        f" files:\n\n{TEMPLATE}\n"
    )
    return 1


def check_range(root: Path, base: str, head: str, *, first_parent: bool) -> int:
    try:
        verdicts = landed(root, base, head, first_parent=first_parent)
    except RefusedError as refusal:
        sys.stderr.write(f"gaps-checked: refused: {refusal}\n")
        return 1
    if not verdicts:
        sys.stderr.write(
            f"gaps-checked: refused: {base}..{head} holds no commit, so nothing was judged\n"
        )
        return 1
    lacking = [v for v in verdicts if v.problem is not None]
    for verdict in lacking:
        sys.stderr.write(f"gaps-checked: {verdict.commit} {verdict.subject}: {verdict.problem}\n")
    if lacking:
        sys.stderr.write(
            "Every commit carries this section (#378), unless it holds only .md files:\n\n"
            f"{TEMPLATE}\n"
        )
    sys.stdout.write(
        f"gaps-checked: {len(verdicts)} commits judged, {len(lacking)} without a whole section\n"
    )
    return 1 if lacking else 0


def main(root: Path, argv: list[str]) -> int:
    match argv:
        case ["commit-msg", message_file]:
            return hook(root, Path(message_file))
        case ["range", base, head]:
            return check_range(root, base, head, first_parent=False)
        case ["landed", base, head]:
            return check_range(root, base, head, first_parent=True)
        case _:
            sys.stderr.write(f"{USAGE}\n")
            return 2


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parents[1], sys.argv[1:]))
