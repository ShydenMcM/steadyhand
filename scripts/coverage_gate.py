"""The coverage gate (#381): every suite's report joined per file into untested counts that must
equal the committed record, and every changed line run, or the pull request fails.

Shyden's rulings: "Ratchet to 100%, unmeasured fails now" (2026-10-21); "all. so 1 and 2" (code
is every .py, .ts, .js and workflow file), "Count them as unrun" (a line coverage is told to skip
is unrun), "Untested count" and "Must be recorded" (2026-10-22, global): the number of statements
and branch arms no test runs may never rise, and the record equals what is measured.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

HUNK = re.compile(r"@@ -[0-9]+(?:,[0-9]+)? \+([0-9]+)(?:,([0-9]+))? @@")
IGNORE_HINT = re.compile(r"\b(?:v8|c8|istanbul)\s+ignore\b")


class GateError(Exception):
    """A report, record or diff the gate cannot read, so nothing it says could be trusted."""


@dataclass(frozen=True)
class Unit:
    """A statement or a branch arm: the lines it is written on, and whether any test ran it."""

    first: int
    last: int
    hit: bool


@dataclass
class FileCoverage:
    """One file's statements and branch arms, each by a key stable across the reports joined."""

    statements: dict[str, Unit] = field(default_factory=dict)
    arms: dict[str, Unit] = field(default_factory=dict)


@dataclass(frozen=True)
class Counts:
    statements: int
    untested_statements: int
    arms: int
    untested_arms: int


@dataclass(frozen=True)
class Record:
    """Each file's untested (statements, branch arms), files at zero left out, and every tracked
    code file no suite measures."""

    files: dict[str, tuple[int, int]]
    unmeasured: tuple[str, ...]


def from_python(report: Mapping[str, Any]) -> dict[str, FileCoverage]:
    """A coverage.py JSON report (format 3, with branches). A line coverage was told to skip is
    a statement no test ran ("Count them as unrun"); an arm is placed on the line it leaves."""
    meta = report.get("meta", {})
    if meta.get("format") != 3:  # noqa: PLR2004 - coverage.py's JSON format number
        msg = f"a coverage.py report of format {meta.get('format')!r}, not 3"
        raise GateError(msg)
    if meta.get("branch_coverage") is not True:
        msg = "a coverage.py report without branch data"
        raise GateError(msg)
    found: dict[str, FileCoverage] = {}
    for path, data in report["files"].items():
        coverage = FileCoverage()
        for line in data["executed_lines"]:
            coverage.statements[str(line)] = Unit(line, line, hit=True)
        for line in (*data["missing_lines"], *data["excluded_lines"]):
            coverage.statements[str(line)] = Unit(line, line, hit=False)
        for arms, hit in ((data["executed_branches"], True), (data["missing_branches"], False)):
            for start, end in arms:
                coverage.arms[f"{start}>{end}"] = Unit(start, start, hit=hit)
        found[path] = coverage
    return found


def _lines(location: Mapping[str, Any]) -> tuple[int, int] | None:
    if "start" not in location:
        return None
    return int(location["start"]["line"]), int(location["end"]["line"])


def from_istanbul(report: Mapping[str, Any], root: str) -> dict[str, FileCoverage]:
    """An istanbul ``coverage-final.json`` (vitest's v8 coverage), its absolute paths made
    relative to *root*. An arm with no location of its own is placed on its branch."""
    prefix = root.rstrip("/") + "/"
    found: dict[str, FileCoverage] = {}
    for entry in report.values():
        path = str(entry["path"])
        if not path.startswith(prefix):
            msg = f"the report names {path}, outside {root}"
            raise GateError(msg)
        coverage = FileCoverage()
        for key, location in entry["statementMap"].items():
            placed = _lines(location)
            if placed is None:
                msg = f"{path}: statement {key} has no lines"
                raise GateError(msg)
            first, last = placed
            coverage.statements[key] = Unit(first, last, hit=entry["s"][key] > 0)
        for key, branch in entry["branchMap"].items():
            for index, location in enumerate(branch["locations"]):
                placed = _lines(location) or _lines(branch["loc"])
                if placed is None:
                    msg = f"{path}: branch {key} arm {index} has no lines"
                    raise GateError(msg)
                first = placed[0]
                coverage.arms[f"{key}.{index}"] = Unit(first, first, hit=entry["b"][key][index] > 0)
        found[path.removeprefix(prefix)] = coverage
    return found


def from_workflow(report: Mapping[str, Any]) -> dict[str, FileCoverage]:
    """#384's workflow report: lines only, each line a statement."""
    found: dict[str, FileCoverage] = {}
    for path, data in report["files"].items():
        coverage = FileCoverage()
        for lines, hit in ((data["executed_lines"], True), (data["missing_lines"], False)):
            for line in lines:
                coverage.statements[str(line)] = Unit(line, line, hit=hit)
        found[path] = coverage
    return found


def _merge(path: str, kind: str, into: dict[str, Unit], units: Mapping[str, Unit]) -> None:
    for key, unit in units.items():
        held = into.get(key)
        if held is None:
            into[key] = unit
            continue
        if (held.first, held.last) != (unit.first, unit.last):
            msg = f"{path}: two reports place {kind} {key} on different lines"
            raise GateError(msg)
        into[key] = Unit(unit.first, unit.last, hit=held.hit or unit.hit)


def join(parts: Iterable[Mapping[str, FileCoverage]]) -> dict[str, FileCoverage]:
    """Every report's files together: a statement or arm any report ran has run."""
    joined: dict[str, FileCoverage] = {}
    for part in parts:
        for path, coverage in part.items():
            into = joined.setdefault(path, FileCoverage())
            _merge(path, "statement", into.statements, coverage.statements)
            _merge(path, "branch arm", into.arms, coverage.arms)
    return joined


def counts(coverage: FileCoverage) -> Counts:
    return Counts(
        statements=len(coverage.statements),
        untested_statements=sum(not unit.hit for unit in coverage.statements.values()),
        arms=len(coverage.arms),
        untested_arms=sum(not unit.hit for unit in coverage.arms.values()),
    )


def measured_record(
    measured: Mapping[str, FileCoverage],
    code_files: Iterable[str],
    carried: Mapping[str, tuple[int, int]],
) -> Record:
    """The record as measured: each measured file's untested counts (zero left out), each
    *carried* file's recorded counts (a hand-started workflow not run on this commit), and every
    code file no report holds."""
    listed = set(code_files)
    gone = sorted(set(carried) - listed)
    if gone:
        msg = f"the record carries files git does not list: {gone}"
        raise GateError(msg)
    files: dict[str, tuple[int, int]] = {}
    for path, coverage in measured.items():
        found = counts(coverage)
        if found.untested_statements or found.untested_arms:
            files[path] = (found.untested_statements, found.untested_arms)
    files.update({path: entry for path, entry in carried.items() if any(entry)})
    unmeasured = tuple(sorted(listed - set(measured) - set(carried)))
    return Record(files=dict(sorted(files.items())), unmeasured=unmeasured)


def compare(recorded: Record, measured: Record) -> list[str]:
    """Every way *measured* differs from *recorded*: a rise is refused, a fall must be recorded."""
    said: list[str] = []
    for path in sorted(set(recorded.files) | set(measured.files)):
        old = recorded.files.get(path, (0, 0))
        new = measured.files.get(path, (0, 0))
        for what, before, after in (
            ("statements", old[0], new[0]),
            ("branch arms", old[1], new[1]),
        ):
            if after > before:
                said.append(f"{path}: untested {what} rose from {before} to {after}")
            elif after < before:
                said.append(f"{path}: untested {what} fell from {before} to {after}: record it")
    said += [
        f"{path}: now measured: record it"
        for path in sorted(set(recorded.unmeasured) - set(measured.unmeasured))
    ]
    said += [
        f"{path}: no suite measures it"
        for path in sorted(set(measured.unmeasured) - set(recorded.unmeasured))
    ]
    return said


def percentages(measured: Mapping[str, FileCoverage]) -> str:
    """The whole project's run share of statements and branch arms: shown, never judged."""
    total = [counts(coverage) for coverage in measured.values()]

    def share(run: int, of: int) -> str:
        return f"{100 * run / of if of else 100:.2f}% ({run} of {of})"

    statements = sum(c.statements for c in total)
    arms = sum(c.arms for c in total)
    run_statements = statements - sum(c.untested_statements for c in total)
    run_arms = arms - sum(c.untested_arms for c in total)
    return f"statements {share(run_statements, statements)}, branch arms {share(run_arms, arms)}"


def changed_lines(diff: str) -> dict[str, set[int]]:
    """The lines each file gains in a ``git diff -U0`` (renames under their new name)."""
    changed: dict[str, set[int]] = {}
    path: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            name = line[4:]
            if name.startswith('"'):
                msg = f"a quoted path in the diff, not read: {name}"
                raise GateError(msg)
            path = None if name == "/dev/null" else name.removeprefix("b/")
        elif line.startswith("@@"):
            hunk = HUNK.match(line)
            if hunk is None:
                msg = f"a hunk header that does not parse: {line}"
                raise GateError(msg)
            start, count = int(hunk[1]), int(hunk[2] or "1")
            if path is not None and count:
                changed.setdefault(path, set()).update(range(start, start + count))
    return changed


def _verdict(coverage: FileCoverage, line: int) -> str | None:
    if any(not u.hit for u in coverage.statements.values() if u.first <= line <= u.last):
        return "changed, but no test ran it"
    if any(not u.hit for u in coverage.arms.values() if u.first == line):
        return "changed, and a branch arm it begins no test took"
    return None


def failures_on_changed_lines(
    measured: Mapping[str, FileCoverage],
    code_files: Iterable[str],
    changed: Mapping[str, set[int]],
    texts: Mapping[str, str],
    carried: set[str],
) -> list[str]:
    """Each changed line of a code file that no test ran: in a measured file, one holding an
    untested statement or beginning an untested arm; in a file no suite measured (a carried
    workflow included), every non-blank one."""
    said: list[str] = []
    listed = set(code_files)
    for path in sorted(changed):
        if path not in listed:
            continue
        coverage = measured.get(path)
        for line in sorted(changed[path]):
            if coverage is None or path in carried:
                written = texts[path].splitlines()
                if line > len(written):
                    msg = f"{path}:{line}: the diff names a line the file does not have"
                    raise GateError(msg)
                if written[line - 1].strip():
                    said.append(f"{path}:{line}: changed in a file no suite measures")
                continue
            verdict = _verdict(coverage, line)
            if verdict is not None:
                said.append(f"{path}:{line}: {verdict}")
    return said


def ignore_hints(texts: Mapping[str, str]) -> list[str]:
    """Each coverage-ignore hint in the TypeScript and JavaScript *texts*: it would hide lines
    from the report, an exemption no one granted."""
    return [
        f"{path}:{number}: {line.strip()}"
        for path, text in sorted(texts.items())
        for number, line in enumerate(text.splitlines(), start=1)
        if IGNORE_HINT.search(line)
    ]
