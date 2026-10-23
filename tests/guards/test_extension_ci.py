"""The ``extension`` job runs the TypeScript workspace's checks in CI (#220, spec §12.1).

Each step after the scope and the lock runs one npm script inside ``extension/``, and each script
runs the tool the spec names, so a renamed script or a step dropped from the job goes red here.
"""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from config_strings import strings_in
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

# Each coverage run also writes the istanbul report and the commit it measured, for the coverage
# job to join (#381).
KEEP_REPORT = (
    " -- --coverage.reporter=text --coverage.reporter=json"
    ' --coverage.reportsDirectory="${RUNNER_TEMP}/coverage-report"\n'
    'git rev-parse HEAD > "${RUNNER_TEMP}/coverage-report/sha.txt"\n'
)


def native(project: str, mode: str = "") -> str:
    """A project run natively under Node's own coverage, then its report of the test, setup and
    config files written with the commit it measured (#394)."""
    return (
        'NODE_V8_COVERAGE="${RUNNER_TEMP}/node-coverage-raw" npm run test:native'
        f" -- --project {project}{mode}\n"
        'node tests/node-coverage-report.ts --raw "${RUNNER_TEMP}/node-coverage-raw"'
        f' --out "${{RUNNER_TEMP}}/node-coverage-report" --project {project}\n'
        'git rev-parse HEAD > "${RUNNER_TEMP}/node-coverage-report/sha.txt"\n'
    )


# The npm commands the job runs, in order, and the tool behind each script (AC4).
COMMANDS = [
    "npm ci --ignore-scripts",
    "npm run lint",
    "npm run format:check",
    "npm run typecheck",
    "npm test" + KEEP_REPORT,
    native("unit"),
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
    "test:native": (
        "vitest run --experimental.viteModuleRunner=false --experimental.nodeLoader=false"
        " --configLoader native"
    ),
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


# The scratch ref the recorder measures (#367). GitHub starts no run on a push to it and its
# dispatch API refuses it (measured 2026-10-21), so the recorder is dispatched from develop with the
# ref as its input, refuses any other namespace, and checks the ref out. Every shell line is pinned
# whole, so none can interpolate the input.
SCRATCH_INPUT = "${{ inputs.ref }}"
REFUSE_OTHER_REFS = (
    'case "$REF" in\n'
    "  refs/floors/?*) ;;\n"
    '  *) echo "::error::record-floors measures only a scratch ref refs/floors/<branch>,'
    " not '$REF'\"; exit 1 ;;\n"
    "esac\n"
)


def test_the_recorder_is_dispatched_with_a_scratch_ref_as_its_only_input() -> None:
    workflow = recorder_workflow()
    assert workflow[True] == {
        "workflow_dispatch": {
            "inputs": {
                "ref": {
                    "description": "The scratch ref to measure: refs/floors/<branch>",
                    "required": True,
                    "type": "string",
                }
            }
        }
    }
    assert list(workflow["jobs"]) == ["record"]
    assert "if" not in workflow["jobs"]["record"]


def test_the_recorder_refuses_a_ref_outside_the_scratch_namespace_before_checking_out() -> None:
    refuse = recorder_workflow()["jobs"]["record"]["steps"][0]
    assert refuse["env"] == {"REF": SCRATCH_INPUT}
    assert refuse["run"] == REFUSE_OTHER_REFS


def test_the_recorder_holds_no_key_that_could_push() -> None:
    workflow = recorder_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in workflow["jobs"]["record"]
    assert "environment" not in workflow["jobs"]["record"]
    checkout = workflow["jobs"]["record"]["steps"][1]
    assert str(checkout["uses"]).startswith("actions/checkout@")
    assert checkout["with"] == {"ref": SCRATCH_INPUT, "persist-credentials": False}


def test_the_recorder_records_then_uploads_the_floors_and_commit_lines_for_the_laptop() -> None:
    steps = recorder_workflow()["jobs"]["record"]["steps"]
    runs = [step.get("run") for step in steps if "run" in step]
    assert runs == [REFUSE_OTHER_REFS, "npm ci --ignore-scripts", "npm run floors:record"]
    # The last step keeps the workflow trace, as every job's does (#384, test_workflow_trace_ci).
    assert steps[-1]["name"] == "Keep the workflow trace"
    upload = steps[-2]
    assert str(upload["uses"]).startswith("actions/upload-artifact@")
    assert upload["with"] == {
        "name": "floors",
        "path": "extension/tests/floors.json\nextension/tests/floors-commit-lines.txt\n",
        "if-no-files-found": "error",
    }
    assert manifest()["scripts"]["floors:fetch"] == "node tests/fetch-floors.ts"


def guards_job() -> dict[str, Any]:
    assert "extension-guards" in JOBS, sorted(JOBS)
    found: dict[str, Any] = JOBS["extension-guards"]
    return found


def test_the_guards_job_installs_then_runs_the_guards_alone_with_one_limit() -> None:
    steps = [step for step in guards_job()["steps"] if "npm " in str(step.get("run", ""))]
    assert [step["run"] for step in steps] == [
        "npm ci --ignore-scripts",
        "npm run test:guards" + KEEP_REPORT,
        native("guards", " --mode guards"),
    ]
    assert [step.get("working-directory") for step in steps] == ["extension"] * 3
    limited = [step for step in guards_job()["steps"] if "timeout-minutes" in step]
    assert limited == steps[1:]
    # Measured on CI on 2026-10-12 (run 38273371897): 5 s. A step limit is whole minutes, so the
    # least it can be is 1; the native run (#394), measured on CI on 2026-10-23 (run 39931521186)
    # at 10 s, is held to the same.
    assert [step["timeout-minutes"] for step in limited] == [1, 1]
