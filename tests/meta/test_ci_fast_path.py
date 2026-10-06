"""The docs-only fast path is wired into ci.yml so every required check still reports (#218).

``scripts/ci_scope.py`` decides; this guard checks the workflow obeys. Each job that gates a
merge checks out two commits (the merge commit and its parents, for the diff), runs the scope
step second, and skips every later step on a docs-only verdict, so the job reports success
under its own name instead of being left pending. Deploy jobs (the ones holding an
``environment``) never carry the skip: they always run in full.
"""

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
# Measured on 2026-10-06 (#218): 4 gated jobs whose later steps number 19. Lower each only by
# a deliberate edit when the workflow shrinks.
GATED_FLOOR = 3
SKIPPED_STEPS_FLOOR = 18

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
    scoped = [step for step in steps if step.get("id") == "scope" or SKIP in str(step.get("if"))]
    assert searched(scoped, of=len(steps), what=f"steps of {name}") == []
