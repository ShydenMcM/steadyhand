"""Run a story's planted mutations against the non-unit suites, in CI (#288).

Usage: uv run --locked python scripts/run_mutations.py <mutation file>...

Shyden's rule (2026-10-09, every project): only unit tests run on the laptop, so a mutation of a
guards, integration or properties test runs here, in the ``mutations`` workflow. Each file under
``mutations/`` lists a story's mutations as ``[[mutation]]`` tables: an ``id``, ``why`` (the
defect it plants), ``path``, an exact ``old`` anchor and its ``new`` text, the ``suite`` and its
target ``tests`` files, and ``expect``: ``red`` with the node ids that must fail in ``red``, or
``green`` for a change no test should see.

Each target runs clean first and must pass, so a red can only be the mutation's. Each mutation
is then applied to the clean checkout (its anchor must match exactly once), its target files run
as CI runs that suite, and the file is put back byte for byte. A run counts only when pytest
finished: exit 0 is green, exit 1 with named failures is red, and anything else is unread. The
report, a table with a count, goes to ``mutations-report.md`` and the job summary. It exits 1
when any row is not as predicted, and 2 on a usage error.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

USAGE = "usage: run_mutations.py <mutation file>..."
REPORT = "mutations-report.md"
SUITES = ("guards", "integration", "properties")
EXPECTS = ("red", "green")
TEXT_KEYS = ("id", "why", "path", "old", "new", "suite", "expect")
LIST_KEYS = ("tests", "red")
# pytest's exit codes other than 0 (all passed) and 1 (some failed): a run that did not finish.
UNFINISHED = {2: "interrupted", 3: "internal error", 4: "usage error", 5: "no tests ran"}
FAILED_LINE = re.compile(r"(?m)^(?:FAILED|ERROR) (\S+)")
TOTALS_LINE = re.compile(r"(?m)^=*\s*(\d+ [a-z]+(?:, \d+ [a-z]+)*) in [\d.]+s\b")
TAIL = 300
# A file directly in mutations/, so a dispatch's input can name nothing else.
FILE_NAME = re.compile(r"mutations/[A-Za-z0-9][A-Za-z0-9._-]*\.toml")

Runner = Callable[[str, tuple[str, ...]], tuple[int, str]]


class MutationError(Exception):
    """A mutation file, an anchor or a run that cannot be read, so nothing may be judged."""


@dataclass(frozen=True)
class Mutation:
    id: str
    why: str
    path: str
    old: str
    new: str
    suite: str
    tests: tuple[str, ...]
    expect: str
    red: tuple[str, ...]


@dataclass(frozen=True)
class Outcome:
    returncode: int
    failed: frozenset[str]
    totals: str


@dataclass(frozen=True)
class Row:
    id: str
    suite: str
    expect: str
    result: str
    detail: str
    ok: bool


def _entry(table: object, number: int, source: str) -> Mutation:
    where = f"{source}: mutation {number}"
    if not isinstance(table, dict):
        msg = f"{where} is not a table"
        raise MutationError(msg)
    unknown = sorted(set(table) - {*TEXT_KEYS, *LIST_KEYS})
    if unknown:
        msg = f"{where}: unknown key {unknown[0]!r}"
        raise MutationError(msg)
    for key in (*TEXT_KEYS, "tests"):
        if key not in table:
            msg = f"{where}: missing key {key!r}"
            raise MutationError(msg)
    for key in TEXT_KEYS:
        if not isinstance(table[key], str):
            msg = f"{where}: {key} is not a string"
            raise MutationError(msg)
    for key in LIST_KEYS:
        value = table.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            msg = f"{where}: {key} is not a list of strings"
            raise MutationError(msg)
    found = Mutation(
        **{key: table[key] for key in TEXT_KEYS},
        tests=tuple(table["tests"]),
        red=tuple(table.get("red", [])),
    )
    _check(found, f"{source}: {found.id}")
    return found


def _check(found: Mutation, where: str) -> None:
    if found.suite not in SUITES:
        msg = f"{where}: suite {found.suite!r} is not one of {', '.join(SUITES)}"
        raise MutationError(msg)
    if found.expect not in EXPECTS:
        msg = f"{where}: expect {found.expect!r} is neither red nor green"
        raise MutationError(msg)
    if not found.tests:
        msg = f"{where}: tests names no target file"
        raise MutationError(msg)
    if found.old == found.new:
        msg = f"{where}: the mutation changes nothing"
        raise MutationError(msg)
    if found.expect == "red" and not found.red:
        msg = f"{where}: a red expectation names no test in red"
        raise MutationError(msg)
    if found.expect == "green" and found.red:
        msg = f"{where}: a green expectation names tests in red"
        raise MutationError(msg)
    outside = [
        name for name in found.red if name.split("::")[0] not in found.tests or "::" not in name
    ]
    if outside:
        msg = f"{where}: red test {outside[0]} is not in its target files"
        raise MutationError(msg)


def load(text: str, source: str) -> list[Mutation]:
    """Every mutation in a mutation file's *text*, checked; *source* names it in any refusal."""
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        msg = f"{source}: not TOML ({error})"
        raise MutationError(msg) from error
    unknown = sorted(set(parsed) - {"mutation"})
    if unknown:
        msg = f"{source}: unknown key {unknown[0]!r}"
        raise MutationError(msg)
    tables = parsed.get("mutation", [])
    if not isinstance(tables, list):
        msg = f"{source}: mutation is not a list of tables"
        raise MutationError(msg)
    if not tables:
        msg = f"{source}: no mutation"
        raise MutationError(msg)
    found = [_entry(table, number, source) for number, table in enumerate(tables, start=1)]
    seen: set[str] = set()
    for entry in found:
        if entry.id in seen:
            msg = f"{source}: {entry.id} twice"
            raise MutationError(msg)
        seen.add(entry.id)
    return found


def apply(root: Path, mutation: Mutation) -> bytes:
    """Plant *mutation* in its file under *root*; the file's original bytes, to put back."""
    target = root / mutation.path
    try:
        original = target.read_bytes()
    except OSError as error:
        msg = f"{mutation.id}: cannot read {mutation.path} ({error.strerror})"
        raise MutationError(msg) from error
    text = original.decode("utf-8")
    count = text.count(mutation.old)
    if count != 1:
        msg = f"{mutation.id}: the anchor matches {count} times"
        raise MutationError(msg)
    target.write_text(text.replace(mutation.old, mutation.new, 1), encoding="utf-8")
    return original


def parse_outcome(returncode: int, output: str) -> Outcome:
    """pytest's verdict from its exit code and output; a run that did not finish is refused."""
    tail = output[-TAIL:]
    if returncode not in (0, 1):
        meaning = UNFINISHED.get(returncode, "killed or unknown")
        msg = f"exit {returncode} ({meaning}): {tail}"
        raise MutationError(msg)
    totals = TOTALS_LINE.findall(output)
    if not totals:
        msg = f"exit {returncode} with no totals line; the tail: {tail}"
        raise MutationError(msg)
    failed = frozenset(FAILED_LINE.findall(output))
    if returncode == 1 and not failed:
        msg = f"exit 1 but names no failed test; the tail: {tail}"
        raise MutationError(msg)
    if returncode == 0 and failed:
        msg = f"exit 0 but names failed tests; the tail: {tail}"
        raise MutationError(msg)
    return Outcome(returncode, failed, totals[-1])


def _failed(name: str, failed: frozenset[str]) -> bool:
    return any(item == name or item.startswith(f"{name}[") for item in failed)


def judge(mutation: Mutation, outcome: Outcome) -> str | None:
    """None when *outcome* is as *mutation* predicted, else why not."""
    if mutation.expect == "green":
        return None if outcome.returncode == 0 else f"red: {', '.join(sorted(outcome.failed))}"
    if outcome.returncode == 0:
        return "not caught: every test passed"
    missed = [name for name in mutation.red if not _failed(name, outcome.failed)]
    return f"named tests stayed green: {', '.join(missed)}" if missed else None


def _baseline(suite: str, tests: tuple[str, ...], runner: Runner) -> Row:
    try:
        outcome = parse_outcome(*runner(suite, tests))
    except MutationError as error:
        return Row("baseline", suite, "green", "not read", str(error), ok=False)
    if outcome.returncode != 0:
        detail = f"red before any mutation: {', '.join(sorted(outcome.failed))}"
        return Row("baseline", suite, "green", "red", detail, ok=False)
    return Row("baseline", suite, "green", "green", outcome.totals, ok=True)


def _one(root: Path, mutation: Mutation, runner: Runner) -> Row:
    def row(result: str, detail: str, *, ok: bool) -> Row:
        return Row(mutation.id, mutation.suite, mutation.expect, result, detail, ok=ok)

    try:
        original = apply(root, mutation)
    except MutationError as error:
        return row("not run", str(error), ok=False)
    target = root / mutation.path
    try:
        returncode, output = runner(mutation.suite, mutation.tests)
    finally:
        target.write_bytes(original)
    try:
        outcome = parse_outcome(returncode, output)
    except MutationError as error:
        return row("not read", str(error), ok=False)
    result = "green" if outcome.returncode == 0 else "red"
    why_not = judge(mutation, outcome)
    return row(result, why_not or outcome.totals, ok=why_not is None)


def run_all(root: Path, mutations: Sequence[Mutation], runner: Runner) -> list[Row]:
    """A clean run of each distinct target, then each mutation run against its target."""
    rows: list[Row] = []
    clean: dict[tuple[str, tuple[str, ...]], bool] = {}
    for mutation in mutations:
        target = (mutation.suite, mutation.tests)
        if target not in clean:
            baseline = _baseline(*target, runner)
            rows.append(baseline)
            clean[target] = baseline.ok
        if clean[target]:
            rows.append(_one(root, mutation, runner))
        else:
            detail = "its target is red before any mutation"
            rows.append(
                Row(mutation.id, mutation.suite, mutation.expect, "not run", detail, ok=False)
            )
    return rows


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def render(rows: Sequence[Row]) -> str:
    """The report: one row per run, then how many were as predicted."""
    lines = [
        "| Mutation | Suite | Expected | Result | As predicted | Detail |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        verdict = "yes" if row.ok else "**NO**"
        cells = (row.id, row.suite, row.expect, row.result, verdict, _cell(row.detail))
        lines.append(f"| {' | '.join(cells)} |")
    passed = sum(row.ok for row in rows)
    return "\n".join(lines) + f"\n\n**{passed} of {len(rows)} as predicted.**\n"


def command(suite: str, tests: tuple[str, ...]) -> list[str]:
    """The target files run as CI runs *suite*, without coverage."""
    return [
        "uv",
        "run",
        "--locked",
        "pytest",
        "-W",
        "error",
        "--suite",
        suite,
        "-p",
        "no:cacheprovider",
        "-q",
        *tests,
    ]


def run_pytest(args: list[str], cwd: Path) -> tuple[int, str]:
    """One run, with a fresh bytecode prefix: a same-length rewrite within a second could
    otherwise run the previous mutation's cached bytecode."""
    env = {**os.environ, "PYTHONPYCACHEPREFIX": tempfile.mkdtemp(prefix="mutation-")}
    done = subprocess.run(  # noqa: S603 - pytest under uv, with arguments this script chooses
        args, cwd=cwd, capture_output=True, text=True, check=False, env=env
    )
    return done.returncode, done.stdout + done.stderr


def main(argv: Sequence[str], runner: Runner, root: Path, env: Mapping[str, str]) -> int:
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    for name in argv:
        if not FILE_NAME.fullmatch(name):
            print(f"{name} is not a mutations/<name>.toml file; {USAGE}", file=sys.stderr)
            return 2
    sections: list[str] = []
    ok = True
    for name in argv:
        try:
            text = (root / name).read_text(encoding="utf-8")
        except OSError as error:
            print(f"cannot read {name} ({error.strerror})")
            return 1
        try:
            mutations = load(text, name)
        except MutationError as error:
            print(error)
            return 1
        rows = run_all(root, mutations, runner)
        ok = ok and all(row.ok for row in rows)
        sections.append(f"## {name}\n\n{render(rows)}")
    report = "\n".join(sections)
    (root / REPORT).write_text(report, encoding="utf-8")
    if "GITHUB_STEP_SUMMARY" in env:
        with Path(env["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
            summary.write(report)
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    here = Path.cwd()
    raise SystemExit(
        main(
            sys.argv[1:],
            lambda suite, tests: run_pytest(command(suite, tests), here),
            here,
            os.environ,
        )
    )
