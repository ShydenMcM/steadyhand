"""The coverage gate (#381): every suite's report joined per file into untested counts that must
equal the committed record, and every changed line run, or the pull request fails.

Shyden's rulings: "Ratchet to 100%, unmeasured fails now" (2026-10-21); "all. so 1 and 2" (code
is every .py, .ts, .js and workflow file), "Count them as unrun" (a line coverage is told to skip
is unrun), "Untested count" and "Must be recorded" (2026-10-22, global): the number of statements
and branch arms no test runs may never rise, and the record equals what is measured.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from run_tool import ToolError, run_tool

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

HUNK = re.compile(r"@@ -[0-9]+(?:,[0-9]+)? \+([0-9]+)(?:,([0-9]+))? @@")
IGNORE_HINT = re.compile(r"\b(?:v8|c8|istanbul)\s+ignore\b")
# The committed record the measured counts must equal.
RECORD = "tests/coverage_record.json"
# Code: every Python, TypeScript and JavaScript file, and every workflow ("all. so 1 and 2").
CODE_SUFFIXES = (".py", ".ts", ".js")
WORKFLOWS = ".github/workflows/"
# The workflow whose own run holds the gate; every other one is started by hand (#384).
OWN_WORKFLOW = ".github/workflows/ci.yml"


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
    carried: Mapping[str, tuple[int, int] | None],
) -> Record:
    """The record as measured: each measured file's untested counts (zero left out), each
    *carried* file's recorded counts (a hand-started workflow not run on this commit), and every
    code file no report holds. A carried file recorded as unmeasured (None) stays so."""
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
    files.update(
        {path: entry for path, entry in carried.items() if entry is not None and any(entry)}
    )
    still = {path for path, entry in carried.items() if entry is None}
    unmeasured = tuple(sorted((listed - set(measured) - set(carried)) | still))
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


def ratchet(base: Record, new: Record, renames: Mapping[str, str]) -> list[str]:
    """Each way the pull request's record would let a file's untested count rise above the base
    branch's record, or a file become unmeasured. Without this a record re-made to match a worse
    measurement would pass (the equality alone holds either way). A renamed file keeps its
    base's counts under its new name."""
    files = {renames.get(path, path): entry for path, entry in base.files.items()}
    unmeasured = {renames.get(path, path) for path in base.unmeasured}
    said: list[str] = []
    for path in sorted(new.files):
        before, after = files.get(path, (0, 0)), new.files[path]
        for what, old, now in (
            ("statements", before[0], after[0]),
            ("branch arms", before[1], after[1]),
        ):
            if now > old:
                said.append(f"{path}: untested {what} would rise from {old} to {now}")
    said += [
        f"{path}: would become unmeasured" for path in sorted(set(new.unmeasured) - unmeasured)
    ]
    return said


def renames_in(listing: str) -> dict[str, str]:
    """Each renamed file's old and new path, from ``git diff --name-status -M -z``."""
    words = listing.split("\0")
    if words and not words[-1]:
        words.pop()
    renames: dict[str, str] = {}
    index = 0
    while index < len(words):
        status = words[index]
        taken = 3 if status[:1] in {"R", "C"} else 2
        if index + taken > len(words):
            msg = f"a name-status listing that ends inside an entry: {words[index:]}"
            raise GateError(msg)
        if status.startswith("R"):
            renames[words[index + 1]] = words[index + 2]
        index += taken
    return renames


def is_code(path: str) -> bool:
    return path.endswith(CODE_SUFFIXES) or (
        path.startswith(WORKFLOWS) and path.endswith((".yml", ".yaml"))
    )


def dump_record(record: Record) -> str:
    """*record* as committed: paths sorted, one count pair per file."""
    shaped = {
        "files": {path: list(record.files[path]) for path in sorted(record.files)},
        "unmeasured": sorted(record.unmeasured),
    }
    return json.dumps(shaped, indent=1) + "\n"


def _count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def load_record(text: str) -> Record:
    """The committed record, refused unless it reads exactly as ``dump_record`` writes one."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        msg = f"the record is not JSON: {error}"
        raise GateError(msg) from error
    if not isinstance(data, dict) or set(data) != {"files", "unmeasured"}:
        msg = "the record must hold exactly files and unmeasured"
        raise GateError(msg)
    files, unmeasured = data["files"], data["unmeasured"]
    for path, entry in files.items():
        if not (isinstance(entry, list) and len(entry) == 2 and all(_count(n) for n in entry)):  # noqa: PLR2004 - (statements, branch arms)
            msg = f"the record's entry for {path} is not two counts"
            raise GateError(msg)
        if not any(entry):
            msg = f"the record names {path} at zero: a file at zero is left out"
            raise GateError(msg)
    if not all(isinstance(path, str) for path in unmeasured) or unmeasured != sorted(
        set(unmeasured)
    ):
        msg = "the record's unmeasured files must be paths, sorted, each once"
        raise GateError(msg)
    return Record(
        files={path: (entry[0], entry[1]) for path, entry in files.items()},
        unmeasured=tuple(unmeasured),
    )


def _read_json(path: Path) -> Any:  # noqa: ANN401 - a report's JSON is untyped
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        msg = f"cannot read {path}: {error}"
        raise GateError(msg) from error


def _same_commit(name: object, sha: object, allowed: set[str]) -> None:
    if sha not in allowed:
        msg = f"the report {name} is from commit {sha}, not {' or '.join(sorted(allowed))}"
        raise GateError(msg)


def _from_folder(folder: Path, report: str, sha: str) -> Any:  # noqa: ANN401 - untyped JSON
    try:
        written = (folder / "sha.txt").read_text(encoding="utf-8").strip()
    except OSError as error:
        msg = f"the report in {folder} names no commit: {error}"
        raise GateError(msg) from error
    _same_commit(folder / report, written, {sha})
    return _read_json(folder / report)


def _measure(args: argparse.Namespace, root: Path) -> dict[str, FileCoverage]:
    parts: list[Mapping[str, FileCoverage]] = []
    parts += [from_python(_from_folder(f, "coverage.json", args.sha)) for f in args.python]
    parts += [
        from_istanbul(_from_folder(f, "coverage-final.json", args.sha), str(root))
        for f in args.istanbul
    ]
    for folder in args.workflow:
        for path in sorted(folder.glob("*.json")):
            report = _read_json(path)
            # ci.yml's own run is on the merge commit; a hand-started one on the head (#384).
            _same_commit(path, report.get("meta", {}).get("sha"), {args.sha, args.head_sha})
            parts.append(from_workflow(report))
    return join(parts)


def _carried(
    measured: Mapping[str, FileCoverage], code_files: list[str], record: Record
) -> dict[str, tuple[int, int] | None]:
    """Each hand-started workflow with no report on this commit, as the record holds it."""
    hand_started = [p for p in code_files if p.startswith(WORKFLOWS) and p != OWN_WORKFLOW]
    return {
        path: None if path in record.unmeasured else record.files.get(path, (0, 0))
        for path in hand_started
        if path not in measured
    }


@dataclass(frozen=True)
class _Run:
    """What one run measured: its files' coverage, the code files git lists, the hand-started
    workflows carried from the record, and the record as measured."""

    measured: Mapping[str, FileCoverage]
    code_files: list[str]
    carried: set[str]
    now: Record


def _failures(args: argparse.Namespace, root: Path, run: _Run) -> list[str]:
    measured, code_files, carried, now = run.measured, run.code_files, run.carried, run.now
    scripts = [p for p in code_files if p.endswith((".ts", ".js"))]
    said = ignore_hints({p: (root / p).read_text(encoding="utf-8") for p in scripts})
    if args.event == "pull_request":
        # A pull request's checkout is its merge commit, whose first parent is the base.
        diff = run_tool(
            root, "git", "diff", "-U0", "--no-color", "--no-ext-diff", "-M", "HEAD^1", "HEAD"
        )
        changed = changed_lines(diff.decode("utf-8"))
        unmeasured = {p for p in changed if p in code_files and (p not in measured or p in carried)}
        texts = {p: (root / p).read_text(encoding="utf-8") for p in unmeasured}
        said += failures_on_changed_lines(measured, code_files, changed, texts, carried)
        said += _against_base(root, now)
    return said


def _against_base(root: Path, now: Record) -> list[str]:
    """The pull request's record held to the base branch's: no count above it, no file newly
    unmeasured (``ratchet``). Only the record's first pull request finds no base record."""
    present = run_tool(root, "git", "ls-tree", "--name-only", "HEAD^1", "--", RECORD)
    if not present.strip():
        print(f"the base has no {RECORD} yet, so this, its first pull request, has none to keep to")
        return []
    base = load_record(run_tool(root, "git", "show", f"HEAD^1:{RECORD}").decode("utf-8"))
    listing = run_tool(root, "git", "diff", "--name-status", "-M", "-z", "HEAD^1", "HEAD")
    return ratchet(base, now, renames_in(listing.decode("utf-8")))


def _code_files(root: Path, measured: Mapping[str, FileCoverage]) -> list[str]:
    """Every code file git lists; a report measuring a file git does not list is refused."""
    listing = run_tool(root, "git", "ls-files", "-z").decode("utf-8")
    code_files = sorted(p for p in listing.split("\0") if p and is_code(p))
    strays = sorted(set(measured) - set(code_files))
    if strays:
        msg = f"the reports measure files git does not list: {strays}"
        raise GateError(msg)
    return code_files


def main(argv: Sequence[str], root: Path) -> int:
    parser = argparse.ArgumentParser(prog="coverage_gate.py")
    parser.add_argument("--event", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--python", type=Path, action="append", default=[])
    parser.add_argument("--istanbul", type=Path, action="append", default=[])
    parser.add_argument("--workflow", type=Path, action="append", default=[])
    parser.add_argument("--write-record", type=Path)
    args = parser.parse_args(argv)
    try:
        measured = _measure(args, root)
        code_files = _code_files(root, measured)
        record = load_record((root / RECORD).read_text(encoding="utf-8"))
        carried = _carried(measured, code_files, record)
        now = measured_record(measured, code_files, carried)
        differences = compare(record, now)
        print(percentages(measured))
        if args.write_record is not None:
            args.write_record.write_text(dump_record(now), encoding="utf-8")
            print("\n".join(differences) or "the record is unchanged")
            return 0
        run = _Run(measured=measured, code_files=code_files, carried=set(carried), now=now)
        failures = differences + _failures(args, root, run)
    except (GateError, ToolError, OSError) as error:
        print(f"coverage gate: {error}", file=sys.stderr)
        return 1
    for failure in failures:
        print(f"coverage gate: {failure}", file=sys.stderr)
    if differences:
        # The job keeps nothing after its last step, so the laptop folds this measurement in.
        print(f"the measured record, to fold into {RECORD}:\n{dump_record(now)}", end="")
    if not failures:
        print("every file matches the record and every changed line ran")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], Path.cwd()))
