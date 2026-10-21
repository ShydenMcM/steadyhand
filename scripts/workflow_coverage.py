"""Which lines of our GitHub workflows a run took, as a coverage report (#384).

Shyden's rulings of 2026-10-22: workflow files are code ("all. so 1 and 2"), measured from a run on
the same commit, its shell traced line by line ("Own story, before #381"). Each workflow's shell
(``defaults.run.shell``) writes, per step, ``$RUNNER_TEMP/workflow-trace/<job>/<GITHUB_ACTION>``:
a header (``sha``, then ``lines``, the script's line count) and the line number of every command
bash's DEBUG trap saw, never its text, since a traced command shows secrets expanded.

A line of the workflow ran when:
- a workflow-level line: any of its jobs ran;
- a job-level line: that job ran (in any matrix leg);
- a step-level line: that step started;
- a line of a step's shell: every command written on it was traced. A line holding no command
  (a keyword, a bare case pattern, a comment) is not code.

Usage: workflow_coverage.py --workflow PATH --jobs JOBS.json --sha SHA --traces DIR [--traces DIR]
       --out REPORT.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tree_sitter_bash
import yaml
from tree_sitter import Language, Parser

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from tree_sitter import Node

BASH = Language(tree_sitter_bash.language())

# A simple command bash's DEBUG trap fires for, spanning every line it is written on.
LEAF = frozenset({"command", "declaration_command", "unset_command", "test_command"})
# Assignments: alone they are a command; inside one of these they are part of it.
ASSIGNMENT_OWNERS = frozenset(
    {"command", "declaration_command", "variable_assignments", "c_style_for_statement"}
)
# Compound commands the trap fires for once per pass, at their header.
HEADED = frozenset({"for_statement", "c_style_for_statement", "case_statement"})

# Text a step's shell may not hold: each could forge or silence its own trace.
FORGERIES = (
    ("DEBUG", "touches the DEBUG trap the trace is made by"),
    ("workflow-trace", "names the workflow-trace directory"),
    ("__wt_", "names a __wt_ variable of the tracing shell"),
)
# Steps GitHub adds around a job's own: set-up, tear-down, and actions' pre and post steps.
BOOKKEEPING = re.compile(r"Set up job|Complete job|(Pre|Post) .*")
HEADER = re.compile(r"sha ([0-9a-f]{40})\nlines ([0-9]+)\n")
LINE_NUMBER = re.compile(r"[0-9]+")
EXPRESSION = re.compile(r"\$\{\{.*?\}\}")

# The shell every workflow sets as defaults.run.shell (see the header of each workflow), exactly.
TRACING_SHELL = (
    "bash --noprofile --norc -eo pipefail -c "
    '"__wt_t=\\"$RUNNER_TEMP/workflow-trace/$GITHUB_JOB/$GITHUB_ACTION\\"; '
    'mkdir -p \\"$(dirname \\"$__wt_t\\")\\"; '
    "printf 'sha %s\\nlines %s\\n' \\\"$GITHUB_SHA\\\" "
    '\\"$(grep -c \'\' \\"$0\\")\\" > \\"$__wt_t\\"; '
    '__wt_s=\\"$0\\"; '
    "set -T; "
    'trap \'if [ \\"$BASH_SOURCE\\" = \\"$__wt_s\\" ]; '
    'then echo \\"$LINENO\\" >> \\"$__wt_t\\"; '
    "fi' DEBUG; "
    '. \\"$0\\"" {0}'
)
# GitHub fills a custom shell with string.Format: a brace other than {0} would break it.
FORMAT_PLACEHOLDER = "{0}"

Where = tuple[str | int, ...]


class ShellParseError(Exception):
    """A shell step tree-sitter-bash cannot read, so its lines cannot be judged."""


class WorkflowError(Exception):
    """A workflow written in a form whose lines cannot be judged."""


class TraceError(Exception):
    """A trace that does not fit the workflow or the run: its lines cannot be trusted."""


class RunError(Exception):
    """A run's jobs or steps that do not line up with the workflow."""


@dataclass(frozen=True)
class Step:
    """One step as the workflow writes it, with its shell's commands when it runs one."""

    name: str | None
    step_id: str | None
    uses: str | None
    run: str | None
    units: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Job:
    name: str | None
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class Workflow:
    """Each code line's place (``lines``) and each job's steps (``jobs``)."""

    lines: dict[int, Where]
    jobs: dict[str, Job]


@dataclass(frozen=True)
class StepResult:
    name: str
    status: str
    conclusion: str | None


@dataclass(frozen=True)
class JobResult:
    name: str
    status: str
    conclusion: str | None
    steps: tuple[StepResult, ...]


@dataclass(frozen=True)
class Trace:
    job: str
    action: str
    sha: str
    lines: int
    traced: frozenset[int]


@dataclass(frozen=True)
class Verdict:
    executed: list[int]
    missing: list[int]


def shell_units(script: str) -> list[tuple[int, int]]:
    """Each place bash's DEBUG trap can fire in *script*, as a 1-based (first, last) line range,
    in the order written. A traced line inside a range means that unit ran."""
    root = Parser(BASH).parse(script.encode("utf-8")).root_node
    if root.has_error:
        line = _first_error(root).start_point.row + 1
        msg = f"the shell step does not parse at line {line}"
        raise ShellParseError(msg)
    units: list[tuple[int, int]] = []
    _collect(root, units)
    return units


def _first_error(node: Node) -> Node:
    for child in node.children:
        if child.has_error:
            return _first_error(child)
    return node


def _rows(node: Node) -> tuple[int, int]:
    """*node*'s 1-based first and last line. No unit ends at a line's start (measured
    2026-10-22: only the whole program, a heredoc body and a parse error do), so its end row is
    its last line."""
    return node.start_point.row + 1, node.end_point.row + 1


def _unit(node: Node) -> tuple[int, int] | None:
    parent = node.parent
    kind = node.type
    if (
        kind in LEAF
        or kind == "variable_assignments"
        or (
            kind == "variable_assignment"
            and parent is not None
            and parent.type not in ASSIGNMENT_OWNERS
        )
    ):
        # A heredoc body belongs to the command that reads it.
        owner = parent if parent is not None and parent.type == "redirected_statement" else node
        return _rows(owner)
    if kind in HEADED:
        # The header runs from the keyword to `do` (a loop) or to `in` (a case).
        end = "in" if kind == "case_statement" else "do_group"
        # tree-sitter-bash parses no loop without `do` nor case without `in`: one is always there.
        body = next(child for child in node.children if child.type == end)
        return node.start_point.row + 1, body.start_point.row + 1
    if kind == "compound_statement" and node.children[0].type == "((":
        return _rows(node)
    return None


def _collect(node: Node, units: list[tuple[int, int]]) -> None:
    found = _unit(node)
    if found is not None:
        units.append(found)
    for child in node.children:
        _collect(child, units)


def _compose(text: str) -> yaml.MappingNode:
    loader = getattr(yaml, "CSafeLoader", None)
    if loader is None:
        msg = "PyYAML has no CSafeLoader: install a PyYAML built with libyaml"
        raise WorkflowError(msg)
    node = yaml.compose(text, Loader=loader)
    if not isinstance(node, yaml.MappingNode):
        msg = "the workflow is not a mapping, so it has no jobs"
        raise WorkflowError(msg)
    return node


def _get(mapping: yaml.MappingNode, key: str) -> yaml.Node | None:
    return next((value for k, value in mapping.value if k.value == key), None)


def _text(mapping: yaml.MappingNode, key: str) -> str | None:
    node = _get(mapping, key)
    return None if node is None else str(node.value)


def _script(run: yaml.Node, where: str) -> tuple[str, int]:
    """The step's shell and the 0-based file line its first line is on."""
    if not isinstance(run, yaml.ScalarNode):
        msg = f"{where}: run is not text"
        raise WorkflowError(msg)
    if run.style == ">":
        msg = f"{where}: a folded run (>) joins lines, so its trace cannot be mapped back"
        raise WorkflowError(msg)
    if run.style == "|":
        return run.value, run.start_mark.line + 1
    if run.end_mark.line != run.start_mark.line:
        msg = f"{where}: a run written over several lines without | cannot be mapped back"
        raise WorkflowError(msg)
    return run.value, run.start_mark.line


def _step(
    item: yaml.Node, where: str, lines: dict[int, Where], place: tuple[str, str, int]
) -> Step:
    if not isinstance(item, yaml.MappingNode):
        msg = f"{where} is not a mapping"
        raise WorkflowError(msg)
    if _get(item, "shell") is not None:
        msg = f"{where} sets its own shell, so it would not be traced"
        raise WorkflowError(msg)
    run_node = _get(item, "run")
    run: str | None = None
    units: tuple[tuple[int, int], ...] = ()
    if run_node is not None:
        run, first = _script(run_node, where)
        for needle, why in FORGERIES:
            if needle in run:
                msg = f"{where}: its shell {why}"
                raise WorkflowError(msg)
        try:
            units = tuple(shell_units(run))
        except ShellParseError as error:
            msg = f"{where}: {error}"
            raise WorkflowError(msg) from error
        for number in range(1, len(run.splitlines()) + 1):
            lines[first + number] = (*place, number)
    return Step(
        name=_text(item, "name"),
        step_id=_text(item, "id"),
        uses=_text(item, "uses"),
        run=run,
        units=units,
    )


def _job(
    key: str, node: yaml.Node, openers: list[tuple[int, Where]], lines: dict[int, Where]
) -> Job:
    if not isinstance(node, yaml.MappingNode):
        msg = f"job {key} is not a mapping"
        raise WorkflowError(msg)
    if _get(node, "uses") is not None:
        msg = f"job {key} calls a reusable workflow, whose lines this reader cannot see"
        raise WorkflowError(msg)
    if _get(node, "container") is not None:
        msg = f"job {key} runs in a container, whose shell is not the tracing one"
        raise WorkflowError(msg)
    defaults = _get(node, "defaults")
    if isinstance(defaults, yaml.MappingNode):
        run_defaults = _get(defaults, "run")
        if isinstance(run_defaults, yaml.MappingNode) and _get(run_defaults, "shell") is not None:
            msg = f"job {key} sets its own shell, so its steps would not be traced"
            raise WorkflowError(msg)
    for child_key, _ in node.value:
        openers.append((child_key.start_mark.line, ("job", key)))
    steps_node = _get(node, "steps")
    steps: list[Step] = []
    if steps_node is not None:
        if not isinstance(steps_node, yaml.SequenceNode):
            msg = f"job {key}: steps is not a list"
            raise WorkflowError(msg)
        for index, item in enumerate(steps_node.value):
            openers.append((item.start_mark.line, ("step", key, index)))
            steps.append(_step(item, f"job {key}, step {index + 1}", lines, ("shell", key, index)))
    return Job(name=_text(node, "name"), steps=tuple(steps))


def layout(text: str) -> Workflow:
    """Where each code line of the workflow *text* belongs, and each job's steps."""
    root = _compose(text)
    jobs_node = _get(root, "jobs")
    if jobs_node is None:
        msg = "the workflow has no jobs"
        raise WorkflowError(msg)
    if not isinstance(jobs_node, yaml.MappingNode):
        msg = "the workflow's jobs are not a mapping"
        raise WorkflowError(msg)
    openers: list[tuple[int, Where]] = [
        (key.start_mark.line, ("workflow",)) for key, _ in root.value
    ]
    shell: dict[int, Where] = {}
    jobs: dict[str, Job] = {}
    for key_node, node in jobs_node.value:
        key = str(key_node.value)
        openers.append((key_node.start_mark.line, ("job", key)))
        jobs[key] = _job(key, node, openers, shell)
    openers.sort(key=lambda opener: opener[0])
    lines: dict[int, Where] = {}
    place: Where = ("workflow",)
    cursor = 0
    for index, raw in enumerate(text.splitlines()):
        while cursor < len(openers) and openers[cursor][0] <= index:
            place = openers[cursor][1]
            cursor += 1
        if index + 1 in shell:
            lines[index + 1] = shell[index + 1]
        elif raw.strip() and not raw.lstrip().startswith("#"):
            lines[index + 1] = place
    return Workflow(lines=lines, jobs=jobs)


def require_traced(text: str) -> None:
    """Refuse a workflow whose steps would run without the tracing shell, so leave no trace."""
    root = _compose(text)
    defaults = _get(root, "defaults")
    run = _get(defaults, "run") if isinstance(defaults, yaml.MappingNode) else None
    shell = _get(run, "shell") if isinstance(run, yaml.MappingNode) else None
    if not isinstance(shell, yaml.ScalarNode) or shell.value != TRACING_SHELL:
        msg = "the workflow does not set the tracing shell as defaults.run.shell"
        raise WorkflowError(msg)


def runner_argv(shell: str, script: str) -> list[str]:
    """The command GitHub's runner starts for a step of custom *shell* whose script is at
    *script*: the first word is the program, the rest is filled by string.Format and split by
    .NET's rules (whitespace splits outside double quotes; 2n backslashes before a quote are n
    and the quote toggles, 2n+1 are n and a literal quote; other backslashes are literal)."""
    program, _, rest = shell.partition(" ")
    if rest.replace(FORMAT_PLACEHOLDER, "").count("{") or rest.count("}") != rest.count(
        FORMAT_PLACEHOLDER
    ):
        msg = "a custom shell may hold no brace but {0}: GitHub fills it with string.Format"
        raise WorkflowError(msg)
    filled = rest.replace(FORMAT_PLACEHOLDER, script)
    words: list[str] = []
    current: list[str] = []
    quoted = False
    started = False
    index = 0
    while index < len(filled):
        char = filled[index]
        if char == "\\":
            end = index
            while end < len(filled) and filled[end] == "\\":
                end += 1
            count = end - index
            if end < len(filled) and filled[end] == '"':
                current.append("\\" * (count // 2))
                if count % 2:
                    current.append('"')
                    end += 1
            else:
                current.append("\\" * count)
            index = end
            started = True
        elif char == '"':
            quoted = not quoted
            started = True
            index += 1
        elif char in " \t" and not quoted:
            if started:
                words.append("".join(current))
                current = []
                started = False
            index += 1
        else:
            current.append(char)
            started = True
            index += 1
    if started:
        words.append("".join(current))
    return [program, *words]


def read_trace(job: str, action: str, text: str) -> Trace:
    """The trace bash wrote for step *action* of *job*: its header, then line numbers only."""
    header = HEADER.match(text)
    if header is None:
        msg = f"the trace of {job}/{action} has no header (sha, then lines)"
        raise TraceError(msg)
    count = int(header[2])
    traced: set[int] = set()
    for number, raw in enumerate(text[header.end() :].splitlines(), start=3):
        if LINE_NUMBER.fullmatch(raw) is None:
            # Never echo the text: it could be a command with a secret expanded.
            msg = f"line {number} of the trace of {job}/{action} is not a line number"
            raise TraceError(msg)
        value = int(raw)
        if value > count:
            msg = f"the trace of {job}/{action} names line {value}, beyond its {count} lines"
            raise TraceError(msg)
        if value:
            traced.add(value)
    return Trace(job=job, action=action, sha=header[1], lines=count, traced=frozenset(traced))


def _pattern(template: str) -> re.Pattern[str]:
    """A job or step name as written, with each ``${{ }}`` standing for any text."""
    parts = EXPRESSION.split(template)
    return re.compile(".*".join(re.escape(part) for part in parts))


def _job_key(flow: Workflow, name: str) -> str:
    keys = [
        key
        for key, job in flow.jobs.items()
        # GitHub names a matrix leg "<name> (<values>)" when the name does not use the matrix.
        if re.fullmatch(rf"(?:{_pattern(job.name or key).pattern})(?: \(.*\))?", name)
    ]
    if len(keys) != 1:
        msg = f"the run's job {name!r} matches {len(keys)} jobs of the workflow: {keys}"
        raise RunError(msg)
    return keys[0]


def _expected(step: Step) -> tuple[str, re.Pattern[str]]:
    """The name GitHub shows for *step*, as written and as a pattern: its own name (any
    ``${{ }}`` in it standing for any text), else "Run " and its action or its first line."""
    if step.name is not None:
        return step.name, _pattern(step.name)
    shown = (
        f"Run {step.uses}" if step.uses is not None else f"Run {(step.run or '').splitlines()[0]}"
    )
    return shown, re.compile(re.escape(shown))


def _started(step: StepResult) -> bool:
    return step.status == "in_progress" or (
        step.status == "completed" and step.conclusion in {"success", "failure"}
    )


def _aligned(key: str, job: Job, result: JobResult) -> list[bool]:
    """Whether each of the workflow's steps started in *result*, matched to the run's steps in
    order, GitHub's own steps passed over."""
    if not result.steps:
        return [False] * len(job.steps)
    pending = list(result.steps)
    cursor = 0
    started: list[bool] = []
    for step in job.steps:
        shown, expected = _expected(step)
        while (
            cursor < len(pending)
            and not expected.fullmatch(pending[cursor].name)
            and BOOKKEEPING.fullmatch(pending[cursor].name)
        ):
            cursor += 1
        if cursor == len(pending):
            msg = f"job {key} ({result.name}): the run has no step {shown!r}"
            raise RunError(msg)
        if not expected.fullmatch(pending[cursor].name):
            msg = (
                f"job {key} ({result.name}): the run's step {pending[cursor].name!r} stands where"
                f" the workflow has {shown!r}"
            )
            raise RunError(msg)
        started.append(_started(pending[cursor]))
        cursor += 1
    extra = [step.name for step in pending[cursor:] if not BOOKKEEPING.fullmatch(step.name)]
    if extra:
        msg = f"job {key} ({result.name}): the run has steps the workflow does not: {extra}"
        raise RunError(msg)
    return started


def _actions(job: Job) -> dict[str, int]:
    """Each run step's ``GITHUB_ACTION``: its id, else ``__run``, ``__run_2``, ... in order."""
    actions: dict[str, int] = {}
    unnamed = 0
    for index, step in enumerate(job.steps):
        if step.run is None:
            continue
        if step.step_id is not None:
            actions[step.step_id] = index
            continue
        unnamed += 1
        actions["__run" if unnamed == 1 else f"__run_{unnamed}"] = index
    return actions


def _traced(flow: Workflow, traces: Iterable[Trace], sha: str) -> dict[tuple[str, int], set[int]]:
    traced: dict[tuple[str, int], set[int]] = {}
    for trace in traces:
        name = f"{trace.job}/{trace.action}"
        if trace.sha != sha:
            msg = f"the trace {name} is from commit {trace.sha}, not {sha}"
            raise TraceError(msg)
        if trace.job not in flow.jobs:
            msg = f"the trace {name} is for job {trace.job}, which the workflow does not name"
            raise TraceError(msg)
        job = flow.jobs[trace.job]
        index = _actions(job).get(trace.action)
        if index is None:
            msg = f"the trace {name} fits no step of job {trace.job}"
            raise TraceError(msg)
        written = len((job.steps[index].run or "").splitlines())
        if trace.lines != written:
            msg = f"the trace {name} counts {trace.lines} lines; its step has {written}"
            raise TraceError(msg)
        traced.setdefault((trace.job, index), set()).update(trace.traced)
    return traced


def judge(flow: Workflow, jobs: Sequence[JobResult], traces: Sequence[Trace], sha: str) -> Verdict:
    """Which of *flow*'s code lines the run's *jobs* and *traces*, on commit *sha*, took."""
    results: dict[str, list[JobResult]] = {key: [] for key in flow.jobs}
    for result in jobs:
        results[_job_key(flow, result.name)].append(result)
    absent = [key for key, found in results.items() if not found]
    if absent:
        msg = f"the run has no result for the workflow's jobs {absent}"
        raise RunError(msg)
    job_ran = {
        key: any(r.steps and _started(r.steps[0]) for r in found) for key, found in results.items()
    }
    step_started: dict[tuple[str, int], bool] = {}
    for key, found in results.items():
        for result in found:
            for index, started in enumerate(_aligned(key, flow.jobs[key], result)):
                step_started[key, index] = step_started.get((key, index), False) or started
    traced = _traced(flow, traces, sha)
    for key, index in traced:
        if not step_started[key, index]:
            msg = f"job {key} has a trace for step {index + 1}, which the run did not start"
            raise TraceError(msg)
    for key, job in flow.jobs.items():
        for index, step in enumerate(job.steps):
            if step.run is not None and step_started[key, index] and (key, index) not in traced:
                msg = f"job {key}, step {index + 1} ran, but no trace of it was kept"
                raise TraceError(msg)
    took = _Took(job_ran=job_ran, step_started=step_started, traced=traced)
    executed: list[int] = []
    missing: list[int] = []
    for line, where in sorted(flow.lines.items()):
        ran = _ran(flow, where, took)
        if ran is None:
            continue
        (executed if ran else missing).append(line)
    return Verdict(executed=executed, missing=missing)


@dataclass(frozen=True)
class _Took:
    """What one run did: each job ran, each step started, each step's traced lines."""

    job_ran: dict[str, bool]
    step_started: dict[tuple[str, int], bool]
    traced: dict[tuple[str, int], set[int]]


def _ran(flow: Workflow, where: Where, took: _Took) -> bool | None:
    """Whether the line at *where* ran; None when it holds no command bash could run."""
    kind = where[0]
    if kind == "workflow":
        return any(took.job_ran.values())
    key = str(where[1])
    if kind == "job":
        return took.job_ran[key]
    index = int(where[2])
    if kind == "step":
        return took.step_started[key, index]
    line = int(where[3])
    holding = [unit for unit in flow.jobs[key].steps[index].units if unit[0] <= line <= unit[1]]
    if not holding:
        return None
    hits = took.traced.get((key, index), set())
    return all(any(first <= hit <= last for hit in hits) for first, last in holding)


def results_from(payload: dict[str, Any]) -> list[JobResult]:
    jobs = payload["jobs"]
    if payload["total_count"] != len(jobs):
        msg = f"the run lists {payload['total_count']} jobs but {len(jobs)} were read"
        raise RunError(msg)
    return [
        JobResult(
            name=job["name"],
            status=job["status"],
            conclusion=job["conclusion"],
            steps=tuple(
                StepResult(name=step["name"], status=step["status"], conclusion=step["conclusion"])
                for step in job["steps"]
            ),
        )
        for job in jobs
    ]


def traces_in(roots: Iterable[Path]) -> list[Trace]:
    found = [path for root in roots for path in sorted(root.rglob("*")) if path.is_file()]
    return [
        read_trace(path.parent.name, path.name, path.read_text(encoding="utf-8")) for path in found
    ]


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="workflow_coverage.py")
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--traces", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        text = args.workflow.read_text(encoding="utf-8")
        require_traced(text)
        flow = layout(text)
        jobs = results_from(json.loads(args.jobs.read_text(encoding="utf-8")))
        verdict = judge(flow, jobs, traces_in(args.traces), args.sha)
    except (WorkflowError, TraceError, RunError) as error:
        print(f"workflow coverage: {error}", file=sys.stderr)
        return 1
    path = args.workflow.as_posix()
    report = {
        "meta": {"sha": args.sha, "workflow": path},
        "files": {path: {"executed_lines": verdict.executed, "missing_lines": verdict.missing}},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    total = len(verdict.executed) + len(verdict.missing)
    print(f"{path}: {len(verdict.executed)} of {total} lines ran; unrun: {verdict.missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
