"""The docs-only fast path is wired into ci.yml so every required check still reports (#218).

``scripts/ci_scope.py`` decides; this guard checks the workflow obeys. Each job that gates a
merge checks out two commits (the merge commit and its parents, for the diff), runs the scope
step second, and skips every later step on a docs-only verdict, so the job reports success
under its own name instead of being left pending. Deploy jobs (the ones holding an
``environment``) never carry the skip: they always run in full.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from population import searched

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github/workflows/ci.yml"
SKIP = "steps.scope.outputs.docs_only != 'true'"
SCOPE_RUN = 'python3 scripts/ci_scope.py "$EVENT_NAME"'
EVENT = "${{ github.event_name }}"
LOCK = {
    "name": "Lock the docs-only fast path: no later step may read it",
    "if": SKIP,
    "run": "python3 scripts/lock_fast_path.py",
}
# Measured on 2026-10-06 (#218, #264): 4 gated jobs whose later steps number 23, the lock included.
# Lower each only by a deliberate edit when the workflow shrinks.
GATED_FLOOR = 3
SKIPPED_STEPS_FLOOR = 22

# PyYAML reads the bare key `on` as the boolean True, so a key may be a bool.
WORKFLOW: dict[str | bool, Any] = yaml.safe_load(CI.read_text(encoding="utf-8"))
JOBS: dict[str, dict[str, Any]] = WORKFLOW["jobs"]
GATED = sorted(name for name, job in JOBS.items() if "environment" not in job)
DEPLOYS = sorted(name for name, job in JOBS.items() if "environment" in job)


def test_the_gated_and_deploy_jobs_are_the_ones_expected() -> None:
    assert "lint" in GATED
    assert "publish-dev" in DEPLOYS
    assert len(GATED) >= GATED_FLOOR


def test_no_trigger_filters_by_path() -> None:
    """A path filter leaves a required check pending forever; the fast path skips steps instead."""
    triggers: dict[str, Any] = WORKFLOW[True]
    assert set(triggers) == {"pull_request", "push"}
    filtered = [
        f"{event}: {key}"
        for event, spec in triggers.items()
        for key in spec
        if key in {"paths", "paths-ignore"}
    ]
    assert searched(filtered, of=len(triggers), what="triggers") == []


@pytest.mark.parametrize("name", GATED)
def test_a_gated_job_checks_out_the_merge_commit_and_its_parents(name: str) -> None:
    checkout = JOBS[name]["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["fetch-depth"] == 2


@pytest.mark.parametrize("name", GATED)
def test_a_gated_job_runs_the_scope_step_second_and_unconditionally(name: str) -> None:
    scope = JOBS[name]["steps"][1]
    assert scope == {
        "name": "Scope: may this docs-only change skip the rest?",
        "id": "scope",
        "env": {"EVENT_NAME": EVENT},
        "run": SCOPE_RUN,
    }


@pytest.mark.parametrize("name", GATED)
def test_a_gated_job_locks_the_fast_path_before_any_other_step(name: str) -> None:
    """On a full run, every fast-path file is unreadable from the third step on, so a reader in
    any language fails by name (#264). Checkout and scope come first: both read the tree."""
    assert JOBS[name]["steps"][2] == LOCK


# The user flag in a `container:`'s Docker options, spelled either way Docker accepts.
USER_FLAG = re.compile(r"(?:^|\s)(?:--user|-u)(?:=|\s+)(\S+)")
ROOT_USERS = frozenset({"0", "root"})


def container_user(container: object) -> str | None:
    """The user a job's ``container:`` runs as, from its options; None when unset, which leaves
    the image's default user (root, for Playwright's image)."""
    options = container.get("options", "") if isinstance(container, dict) else ""
    found = USER_FLAG.search(str(options))
    return found[1] if found else None


def runs_as_root(container: object) -> bool:
    user = container_user(container)
    return user is None or user.split(":")[0] in ROOT_USERS


@pytest.mark.parametrize(
    ("container", "root"),
    [
        pytest.param("mcr.microsoft.com/playwright:v1.55.0-noble", True, id="an-image-alone"),
        pytest.param({"image": "node:24"}, True, id="no-options"),
        pytest.param({"image": "node:24", "options": "--ipc=host --init"}, True, id="no-user"),
        pytest.param(
            {"image": "node:24", "options": "--ulimit nofile=1024"}, True, id="ulimit-is-not-u"
        ),
        pytest.param({"image": "node:24", "options": "--user 0"}, True, id="uid-0"),
        pytest.param({"image": "node:24", "options": "--user root"}, True, id="root-by-name"),
        pytest.param({"image": "node:24", "options": "--user 0:0"}, True, id="uid-0-with-group"),
        pytest.param({"image": "node:24", "options": "--user=1001"}, False, id="user-equals"),
        pytest.param(
            {"image": "node:24", "options": "--ipc=host --user 1001:1001"}, False, id="uid-and-gid"
        ),
        pytest.param({"image": "node:24", "options": "-u pwuser"}, False, id="short-flag-by-name"),
    ],
)
def test_a_container_runs_as_root_unless_its_options_name_another_user(
    container: object, *, root: bool
) -> None:
    assert runs_as_root(container) is root


@pytest.mark.parametrize("name", GATED)
def test_a_gated_job_runs_no_container_as_root(name: str) -> None:
    """The lock is chmod 000, which root ignores, and container images often run as root by
    default (Playwright's does). Least privilege keeps the lock biting (#264)."""
    container = JOBS[name].get("container")
    assert container is None or not runs_as_root(container), (
        f"{name} runs its container as root: give it `options: --user <a non-root uid>`"
    )


@pytest.mark.parametrize("name", GATED)
def test_a_gated_job_reports_and_skips_every_later_step(name: str) -> None:
    job = JOBS[name]
    assert "if" not in job, "a job-level condition would leave its required check skipped"
    later = job["steps"][2:]
    unguarded = [
        step.get("name", step.get("run", step.get("uses")))
        for step in later
        if step.get("if") != SKIP
    ]
    assert searched(unguarded, of=len(later), what=f"later steps of {name}") == []


def test_the_skip_covers_every_later_step_of_every_gated_job() -> None:
    later = [step for name in GATED for step in JOBS[name]["steps"][2:]]
    assert len(later) >= SKIPPED_STEPS_FLOOR
    assert sum(step.get("if") == SKIP for step in later) == len(later)


@pytest.mark.parametrize("name", DEPLOYS)
def test_a_deploy_job_always_runs_in_full(name: str) -> None:
    steps = JOBS[name]["steps"]
    scoped = [
        step
        for step in steps
        if step.get("id") == "scope" or SKIP in str(step.get("if")) or step == LOCK
    ]
    assert searched(scoped, of=len(steps), what=f"steps of {name}") == []
