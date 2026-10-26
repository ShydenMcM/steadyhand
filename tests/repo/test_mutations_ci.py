"""The mutations workflow (#288), a required check: every pull request plans which mutation files it
must run (failing when it changes a non-unit test none targets) and runs them through
``scripts/run_mutations.py``; a dispatch runs one named file. It reads only, the dispatch's input
reaches the shell only through the environment, and one limit sits at the step that runs them."""

import re
from functools import cache
from typing import Any

from ci_workflow import ROOT, ci, parse

WORKFLOW = ROOT / ".github/workflows/mutations.yml"
PLAN = 'uv run --no-project scripts/run_mutations.py --plan "$EVENT_NAME"'
RUN = (
    "mapfile -t files < mutation-files.txt\n"
    'uv run --locked python scripts/run_mutations.py "${files[@]}"\n'
)
PLANNED = "steps.plan.outputs.run == 'true'"


@cache
def workflow() -> dict[str | bool, Any]:
    parsed: dict[str | bool, Any] = parse(WORKFLOW.read_text(encoding="utf-8"))
    return parsed


def job() -> dict[str, Any]:
    found: dict[str, Any] = workflow()["jobs"]["mutations"]
    return found


def step(name: str) -> dict[str, Any]:
    named: list[dict[str, Any]] = [found for found in job()["steps"] if found.get("name") == name]
    assert len(named) == 1, [found.get("name") for found in job()["steps"]]
    return named[0]


def test_it_runs_on_every_pull_request_ci_runs_on_and_on_a_dispatch_naming_one_file() -> None:
    assert workflow()[True] == {
        "pull_request": ci()[True]["pull_request"],
        "workflow_dispatch": {
            "inputs": {
                "file": {
                    "description": "The mutation file to run, such as mutations/288.toml",
                    "required": True,
                    "type": "string",
                }
            }
        },
    }
    assert ci()[True]["pull_request"] == {"branches": ["develop", "main"]}
    assert list(workflow()["jobs"]) == ["mutations"]
    # A required check reports under its job's name on every pull request: no job condition.
    assert job()["name"] == "mutations"


def test_it_holds_no_key_that_could_push() -> None:
    assert workflow()["permissions"] == {"contents": "read"}
    assert sorted(job()) == ["name", "runs-on", "steps", "timeout-minutes"]
    assert job()["steps"][0]["with"]["persist-credentials"] is False


def test_every_expression_it_reads_is_one_it_needs() -> None:
    """Its own four, and the trace upload's four, which every job ends with (#384)."""
    found = re.findall(r"\$\{\{(.*?)\}\}", WORKFLOW.read_text(encoding="utf-8"))
    assert sorted({expression.strip() for expression in found}) == [
        "!cancelled()",
        f"!cancelled() && {PLANNED}",
        "env.UV_VERSION",
        "github.event_name",
        "github.job",
        "inputs.file",
        "runner.temp",
        "strategy.job-index",
    ]


def test_the_plan_runs_first_on_the_pinned_python_with_the_input_in_the_environment() -> None:
    """uv comes before it, unconditionally, so the plan runs on the Python .python-version pins,
    never the runner image's own (#382)."""
    plan = step("Plan: which mutation files must run?")
    assert job()["steps"].index(plan) == 2
    assert plan["id"] == "plan"
    assert plan["run"] == PLAN
    assert plan["env"] == {"EVENT_NAME": "${{ github.event_name }}", "FILE": "${{ inputs.file }}"}
    # HEAD^1 is the base side of the pull request's merge commit, so the checkout needs both.
    assert job()["steps"][0]["with"]["fetch-depth"] == 2


def test_every_step_after_the_plan_runs_only_when_it_planned_a_run() -> None:
    # The last step keeps the workflow trace whatever ran (#384, test_workflow_trace_ci.py).
    assert job()["steps"][-1]["name"] == "Keep the workflow trace"
    later = job()["steps"][3:-1]
    assert [found.get("if") for found in later[:-1]] == [PLANNED] * (len(later) - 1)
    assert later[-1]["if"] == f"${{{{ !cancelled() && {PLANNED} }}}}"


def test_the_runner_runs_the_planned_files_with_the_one_limit() -> None:
    limited = [found for found in job()["steps"] if "timeout-minutes" in found]
    assert limited == [step("Run the mutations")]
    assert limited[0]["run"] == RUN
    # Measured on PR #342, every mutation file run: 5 min 35 s (50 mutations, run 38868589129),
    # 4 min 43 s and 3 min 49 s (56, runs 38871773290 and 38872705889). About four times the
    # slowest, as ci.yml's limits are; a corpus past that is re-measured, never the limit raised.
    assert limited[0]["timeout-minutes"] == 23


def test_the_report_is_kept_even_when_a_mutation_is_not_as_predicted() -> None:
    upload = job()["steps"][-2]
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["with"] == {
        "name": "mutations-report",
        "path": "mutations-report.md",
        "if-no-files-found": "error",
    }


def test_it_uses_the_uv_and_the_python_that_ci_uses() -> None:
    """The uv CI pins, set up second whatever the plan says; it names no Python, so uv reads
    .python-version as every CI job does (#382)."""
    assert workflow()["env"]["UV_VERSION"] == ci()["env"]["UV_VERSION"]
    setup = job()["steps"][1]
    assert setup["uses"].startswith("astral-sh/setup-uv@")
    assert setup["with"] == {"version": "${{ env.UV_VERSION }}", "enable-cache": True}
    assert "if" not in setup


def test_it_installs_the_extension_workspace_as_ci_does_with_no_install_script() -> None:
    steps = job()["steps"]
    node = [
        found for found in steps if str(found.get("uses", "")).startswith("actions/setup-node@")
    ]
    assert [found["with"] for found in node] == [
        {
            "node-version-file": ".nvmrc",
            "cache": "npm",
            "cache-dependency-path": "extension/package-lock.json",
        }
    ]
    install = [found for found in steps if str(found.get("run", "")).startswith("npm ")]
    assert [{key: found[key] for key in ("run", "working-directory")} for found in install] == [
        {"run": "npm ci --ignore-scripts", "working-directory": "extension"}
    ]
    # Both before the runner, which starts vitest from the workspace.
    runner = steps.index(step("Run the mutations"))
    assert steps.index(node[0]) < steps.index(install[0]) < runner
