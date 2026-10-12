"""The ``extension`` job runs the TypeScript workspace's checks in CI (#220, spec §12.1).

Each step after the scope and the lock runs one npm script inside ``extension/``, and each script
runs the tool the spec names, so a renamed script or a step dropped from the job goes red here.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from population import searched, tracked

ROOT = Path(__file__).resolve().parents[2]
JOBS: dict[str, dict[str, Any]] = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())[
    "jobs"
]
MANIFEST = ROOT / "extension/package.json"
WORKFLOWS = ROOT / ".github/workflows"

# The floors recorder and its record mode (#221): neither may run in the checks the floors feed,
# or a floor would pass unjudged. Only the recorder's own workflow runs it (#285).
RECORDER = ("floors:record", "record-floors", "STEADYHAND_FLOORS_RECORD")
RECORDER_WORKFLOW = WORKFLOWS / "record-floors.yml"

# The npm commands the job runs, in order, and the tool behind each script (AC4).
COMMANDS = [
    "npm ci --ignore-scripts",
    "npm run lint",
    "npm run format:check",
    "npm run typecheck",
    "npm test",
    "npm run test:limits",
    "npm run build",
]
TOOLS = {
    "lint": "eslint . --max-warnings 0",
    "format:check": "prettier --check .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run --project unit --coverage",
    "test:limits": "vitest run --project unit --mode limits",
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
    return [step for step in job()["steps"] if str(step.get("run", "")).startswith("npm ")]


def test_the_job_runs_the_workspace_checks_in_order() -> None:
    assert [step["run"] for step in npm_steps()] == COMMANDS


def test_every_npm_step_runs_inside_the_workspace() -> None:
    steps = npm_steps()
    assert len(steps) == len(COMMANDS)
    assert [step for step in steps if step.get("working-directory") != "extension"] == []


@pytest.mark.parametrize(("script", "command"), TOOLS.items())
def test_each_script_runs_the_tool_the_spec_names(script: str, command: str) -> None:
    assert manifest()["scripts"].get(script) == command


def test_node_comes_from_setup_node_at_the_engine_floor() -> None:
    setup = [
        step
        for step in job()["steps"]
        if str(step.get("uses", "")).startswith("actions/setup-node@")
    ]
    assert len(setup) == 1
    assert setup[0]["with"]["node-version"] == "24"
    assert manifest().get("engines") == {"node": ">=24"}


def strings_in(node: Any) -> Iterator[str]:  # noqa: ANN401 - parsed YAML is untyped
    """Every key and every string value in a parsed workflow: a run line, an env name, an input."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from strings_in(value)
    elif isinstance(node, list):
        for item in node:
            yield from strings_in(item)
    elif isinstance(node, str):
        yield node


def recorder_mentions(workflow: Any) -> list[str]:  # noqa: ANN401 - parsed YAML is untyped
    """Every key or value in *workflow* that names the floors recorder or its record mode."""
    return [text for text in strings_in(workflow) if any(word in text for word in RECORDER)]


@pytest.mark.parametrize(
    "workflow",
    [
        pytest.param({"jobs": {"j": {"steps": [{"run": "npm run floors:record"}]}}}, id="run"),
        pytest.param(
            {"jobs": {"j": {"steps": [{"run": "node tests/record-floors.ts"}]}}}, id="path"
        ),
        pytest.param({"env": {"STEADYHAND_FLOORS_RECORD": "measurements.jsonl"}}, id="env-name"),
    ],
)
def test_the_recorder_is_found_wherever_a_workflow_names_it(workflow: dict[str, Any]) -> None:
    assert len(recorder_mentions(workflow)) == 1


def test_no_workflow_but_its_own_runs_the_floors_recorder() -> None:
    every = sorted([*tracked(WORKFLOWS, ".yml"), *tracked(WORKFLOWS, ".yaml")])
    assert RECORDER_WORKFLOW in every
    files = [path for path in every if path != RECORDER_WORKFLOW]
    parsed = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in files]
    read = sum(len(list(strings_in(workflow))) for workflow in parsed)
    found = [text for workflow in parsed for text in recorder_mentions(workflow)]
    assert searched(found, of=read, what="workflow keys and values") == []


def test_no_other_npm_script_reaches_the_floors_recorder() -> None:
    scripts: dict[str, str] = manifest()["scripts"]
    assert scripts.get("floors:record") == "node tests/record-floors.ts"
    others = {name: body for name, body in scripts.items() if name != "floors:record"}
    found = [name for name, body in others.items() if any(word in body for word in RECORDER)]
    assert searched(found, of=len(others), what="npm scripts") == []


def recorder_workflow() -> dict[str | bool, Any]:
    found: dict[str | bool, Any] = yaml.safe_load(RECORDER_WORKFLOW.read_text(encoding="utf-8"))
    return found


def test_the_recorder_runs_only_on_a_pull_request_labelled_record_floors() -> None:
    workflow = recorder_workflow()
    assert workflow[True] == {"pull_request": {"types": ["labeled"]}}
    assert list(workflow["jobs"]) == ["record"]
    assert workflow["jobs"]["record"]["if"] == "github.event.label.name == 'record-floors'"


def test_the_recorder_holds_no_key_that_could_push() -> None:
    workflow = recorder_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in workflow["jobs"]["record"]
    assert "environment" not in workflow["jobs"]["record"]
    checkout = workflow["jobs"]["record"]["steps"][0]
    assert str(checkout["uses"]).startswith("actions/checkout@")
    assert checkout["with"] == {"persist-credentials": False}


def test_the_recorder_records_then_uploads_the_floors_file_for_the_laptop() -> None:
    steps = recorder_workflow()["jobs"]["record"]["steps"]
    runs = [step.get("run") for step in steps if "run" in step]
    assert runs == ["npm ci --ignore-scripts", "npm run floors:record"]
    upload = steps[-1]
    assert str(upload["uses"]).startswith("actions/upload-artifact@")
    assert upload["with"] == {
        "name": "floors",
        "path": "extension/tests/floors.json",
        "if-no-files-found": "error",
    }
    assert manifest()["scripts"]["floors:fetch"] == "node tests/fetch-floors.ts"


def guards_job() -> dict[str, Any]:
    assert "extension-guards" in JOBS, sorted(JOBS)
    found: dict[str, Any] = JOBS["extension-guards"]
    return found


def test_the_guards_job_installs_then_runs_the_guards_alone_with_one_limit() -> None:
    steps = [step for step in guards_job()["steps"] if str(step.get("run", "")).startswith("npm ")]
    assert [step["run"] for step in steps] == ["npm ci --ignore-scripts", "npm run test:guards"]
    assert [step.get("working-directory") for step in steps] == ["extension", "extension"]
    limited = [step for step in guards_job()["steps"] if "timeout-minutes" in step]
    assert limited == [steps[-1]]
    # Measured on CI on 2026-10-12 (run 38273371897): 5 s. A step limit is whole minutes, so the
    # least it can be is 1.
    assert limited[0]["timeout-minutes"] == 1
