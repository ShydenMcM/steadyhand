"""The mutations workflow (#288): a labelled pull request or a dispatch runs a story's mutation
files through ``scripts/run_mutations.py``, with read access alone, the dispatch's input reaching
the shell only through the environment, and one limit at the step that runs them."""

import re
from functools import cache
from typing import Any

from ci_workflow import ROOT, ci, parse

WORKFLOW = ROOT / ".github/workflows/mutations.yml"
RUN = (
    "mapfile -t files < mutation-files.txt\n"
    'uv run --locked python scripts/run_mutations.py "${files[@]}"\n'
)
CHANGED = (
    "git diff --name-only --diff-filter=AM HEAD^1 HEAD -- 'mutations/*.toml' > mutation-files.txt"
)


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


def test_it_runs_on_a_pull_request_labelled_mutations_or_a_dispatch_naming_one_file() -> None:
    assert workflow()[True] == {
        "pull_request": {"types": ["labeled"]},
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
    assert list(workflow()["jobs"]) == ["mutations"]
    assert job()["if"] == (
        "github.event_name == 'workflow_dispatch' || github.event.label.name == 'mutations'"
    )


def test_it_holds_no_key_that_could_push() -> None:
    assert workflow()["permissions"] == {"contents": "read"}
    assert sorted(job()) == ["if", "name", "runs-on", "steps", "timeout-minutes"]
    assert job()["steps"][0]["with"]["persist-credentials"] is False


def test_every_expression_it_reads_is_one_of_the_four_it_needs() -> None:
    found = re.findall(r"\$\{\{(.*?)\}\}", WORKFLOW.read_text(encoding="utf-8"))
    assert sorted({expression.strip() for expression in found}) == [
        "!cancelled()",
        "env.UV_VERSION",
        "github.event_name",
        "inputs.file",
    ]


def test_the_dispatch_input_reaches_the_shell_only_through_the_environment() -> None:
    naming = step("Name the mutation files")
    assert naming["env"] == {"EVENT_NAME": "${{ github.event_name }}", "FILE": "${{ inputs.file }}"}
    assert "${{" not in naming["run"]
    assert "printf '%s\\n' \"$FILE\" > mutation-files.txt" in naming["run"]


def test_a_pull_request_runs_the_mutation_files_it_adds_or_changes() -> None:
    assert CHANGED in step("Name the mutation files")["run"]
    # HEAD^1 is the base side of the pull request's merge commit, so the checkout needs both.
    assert job()["steps"][0]["with"]["fetch-depth"] == 2


def test_the_runner_runs_the_named_files_with_the_one_limit() -> None:
    limited = [found for found in job()["steps"] if "timeout-minutes" in found]
    assert limited == [step("Run the mutations")]
    assert limited[0]["run"] == RUN
    # Assumed until the first runs measure it: #292's 30 mutations and their clean runs, each a
    # uv start and a few integration files (the whole suite took 31 s on CI, PR #316).
    assert limited[0]["timeout-minutes"] == 25


def test_the_report_is_kept_even_when_a_mutation_is_not_as_predicted() -> None:
    upload = job()["steps"][-1]
    assert upload["if"] == "${{ !cancelled() }}"
    assert upload["with"] == {
        "name": "mutations-report",
        "path": "mutations-report.md",
        "if-no-files-found": "error",
    }


def test_it_uses_the_uv_and_a_python_that_ci_uses() -> None:
    assert workflow()["env"]["UV_VERSION"] == ci()["env"]["UV_VERSION"]
    setup = job()["steps"][1]
    assert setup["uses"].startswith("astral-sh/setup-uv@")
    assert (
        setup["with"]["python-version"]
        in ci()["jobs"]["integration"]["strategy"]["matrix"]["python"]
    )
