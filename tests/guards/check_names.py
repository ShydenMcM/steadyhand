"""The reader behind the check-name guard (#444), kept apart so its unit tests run it on plants.

Branch protection matches a required check by name. A run that is not the pull request's own (a
dispatch on ``coverage/<branch>``, whose tip is the pull request's head) reported ``mutations``
beside the pull request's run on PR #415's head, so no job may report, on an event other than
``pull_request``, a name a pull-request job reports. Shyden's ruling of 2026-10-30 (*"Leave trunk
pushes out (Recommended)"*) leaves out one event: a ``push`` limited by ``branches`` to ``develop``
and ``main``, ci.yml's full run of the same commit. Names are read exactly or refused: a literal,
the job's key when it has none, or the one event switch below; a matrix, a reusable workflow and
any other expression are refused by name, never guessed.

``tests/guards/test_no_name_clash.py`` runs it over the repository's workflows;
``tests/guard_helpers/test_check_names.py`` plants every form it must recognise and sees it found.
"""

import re
from collections.abc import Mapping
from typing import Any

PULL_REQUEST = "pull_request"
TRUNK = frozenset({"develop", "main"})
# The one expression a name may be: one name on a pull request, another on every other event.
SWITCH = re.compile(
    r"\$\{\{ github\.event_name == 'pull_request' && '([^'$]+)' \|\| '([^'$]+)' \}\}"
)


class UnreadableNameError(AssertionError):
    """A workflow whose events or job names the guard cannot read exactly."""


def triggers(workflow: Mapping[Any, Any], where: str) -> dict[str, Any]:
    """Each event the workflow runs on, with its filter (``None`` when it has none)."""
    found = workflow.get(True, workflow.get("on"))
    if isinstance(found, str):
        return {found: None}
    if isinstance(found, list) and found and all(isinstance(event, str) for event in found):
        return dict.fromkeys(found)
    if isinstance(found, dict) and found and all(isinstance(event, str) for event in found):
        return dict(found)
    msg = f"{where}: cannot read its events: {found!r}"
    raise UnreadableNameError(msg)


def off_pull_request(events: Mapping[str, Any]) -> list[str]:
    """The events judged: every one but ``pull_request``, and a push only to develop and main."""
    judged = []
    for event, given in events.items():
        if event == PULL_REQUEST:
            continue
        trunk_only = (
            event == "push"
            and isinstance(given, dict)
            and list(given) == ["branches"]
            and isinstance(given["branches"], list)
            and given["branches"]
            and all(isinstance(branch, str) for branch in given["branches"])
            and set(given["branches"]) <= TRUNK
        )
        if not trunk_only:
            judged.append(event)
    return judged


def names(key: str, job: Any, where: str) -> tuple[str, str]:  # noqa: ANN401 - parsed YAML
    """The name *job* reports on a pull request, and on every other event."""
    if not isinstance(job, dict):
        msg = f"{where}: job {key} is not a mapping"
        raise UnreadableNameError(msg)
    if "uses" in job:
        msg = f"{where}: job {key} calls a reusable workflow, whose jobs report as '<name> / <job>'"
        raise UnreadableNameError(msg)
    if "matrix" in (job.get("strategy") or {}):
        msg = f"{where}: job {key} has a matrix, so each run's name gains its values"
        raise UnreadableNameError(msg)
    name = job.get("name", key)
    if not isinstance(name, str) or not name.strip():
        msg = f"{where}: job {key}'s name is not text: {name!r}"
        raise UnreadableNameError(msg)
    switch = SWITCH.fullmatch(name)
    if switch:
        return switch[1], switch[2]
    if "${{" in name:
        msg = f"{where}: job {key}'s name is an expression the guard cannot read: {name!r}"
        raise UnreadableNameError(msg)
    return name, name


def clashes(workflows: Mapping[str, Mapping[Any, Any]]) -> list[str]:
    """Each job that reports, on an event other than a pull request, a name a pull-request job
    reports. Names are compared trimmed and case-folded, the looser reading."""
    on_pull_request: dict[str, list[str]] = {}
    off: list[tuple[str, str, list[str]]] = []
    for where, workflow in workflows.items():
        events = triggers(workflow, where)
        judged = off_pull_request(events)
        jobs = workflow.get("jobs")
        if not isinstance(jobs, dict) or not jobs:
            msg = f"{where}: cannot read its jobs: {jobs!r}"
            raise UnreadableNameError(msg)
        for key, job in jobs.items():
            on_pr, elsewhere = names(key, job, where)
            if PULL_REQUEST in events:
                on_pull_request.setdefault(on_pr.strip().casefold(), []).append(f"{where}:{key}")
            if judged:
                off.append((f"{where}:{key}", elsewhere, judged))
    return [
        f"{job} reports {name!r} on {', '.join(judged)}, the name pull-request job"
        f" {' and '.join(on_pull_request[name.strip().casefold()])} reports"
        for job, name, judged in off
        if name.strip().casefold() in on_pull_request
    ]
