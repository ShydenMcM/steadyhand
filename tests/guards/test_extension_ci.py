"""The ``extension`` job runs the TypeScript workspace's checks in CI (#220, spec §12.1).

Each step after the scope and the lock runs one npm script inside ``extension/``, and each script
runs the tool the spec names, so a renamed script or a step dropped from the job goes red here.
"""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
JOBS: dict[str, dict[str, Any]] = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())[
    "jobs"
]
MANIFEST = ROOT / "extension/package.json"
WORKFLOWS = ROOT / ".github/workflows"

# The npm commands the job runs, in order, and the tool behind each script (AC4).
COMMANDS = [
    "npm ci --ignore-scripts",
    "npm run lint",
    "npm run format:check",
    "npm run typecheck",
    "npm test",
    "npm run build",
]
TOOLS = {
    "lint": "eslint . --max-warnings 0",
    "format:check": "prettier --check .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run --project unit --coverage",
    "test:guards": "vitest run --project guards --mode guards --coverage",
    "build": "node build.ts",
}


def job() -> dict[str, Any]:
    """The extension job, looked up per test so its absence fails each test by name."""
    assert "extension" in JOBS, sorted(JOBS)
    found: dict[str, Any] = JOBS["extension"]
    return found


def manifest() -> dict[str, Any]:
    found: dict[str, Any] = json.loads(MANIFEST.read_text())
    return found


def npm_steps() -> list[dict[str, Any]]:
    return [step for step in job()["steps"] if "npm " in str(step.get("run", ""))]


def test_the_job_runs_the_workspace_checks_in_order() -> None:
    assert [step["run"] for step in npm_steps()] == COMMANDS


def test_every_npm_step_runs_inside_the_workspace() -> None:
    steps = npm_steps()
    assert len(steps) == len(COMMANDS)
    assert [step for step in steps if step.get("working-directory") != "extension"] == []


@pytest.mark.parametrize(("script", "command"), TOOLS.items())
def test_each_script_runs_the_tool_the_spec_names(script: str, command: str) -> None:
    assert manifest()["scripts"].get(script) == command


def test_node_comes_from_setup_node_reading_the_nvmrc() -> None:
    # The version itself and the engines range are pinned in test_supply_chain.py (#287).
    setup = [
        step
        for step in job()["steps"]
        if str(step.get("uses", "")).startswith("actions/setup-node@")
    ]
    assert len(setup) == 1
    assert setup[0]["with"]["node-version-file"] == ".nvmrc"
    assert "node-version" not in setup[0]["with"]


def guards_job() -> dict[str, Any]:
    assert "extension-guards" in JOBS, sorted(JOBS)
    found: dict[str, Any] = JOBS["extension-guards"]
    return found


def test_the_guards_job_installs_then_runs_the_guards_alone_with_one_limit() -> None:
    steps = [step for step in guards_job()["steps"] if "npm " in str(step.get("run", ""))]
    assert [step["run"] for step in steps] == [
        "npm ci --ignore-scripts",
        "npm run test:guards",
    ]
    assert [step.get("working-directory") for step in steps] == ["extension"] * 2
    limited = [step for step in guards_job()["steps"] if "timeout-minutes" in step]
    assert limited == steps[1:]
    # Measured on CI on 2026-10-12 (run 38273371897): 5 s. A step limit is whole minutes, so the
    # least it can be is 1.
    assert [step["timeout-minutes"] for step in limited] == [1]
