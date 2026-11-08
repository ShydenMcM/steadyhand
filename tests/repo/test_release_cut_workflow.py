"""``release-cut.yml`` (#400): the release-cut check runs on pull requests into ``main`` from the
default branch's own copy, never the pull request's, and posts its verdict as the ``release-cut``
commit status. Ported from the template's ``check-release-cut.yml`` tests."""

import re
from functools import cache
from pathlib import Path
from typing import Any

from ci_workflow import ROOT, ci, parse

WORKFLOW = ROOT / ".github/workflows/release-cut.yml"


@cache
def workflow() -> dict[str | bool, Any]:
    parsed: dict[str | bool, Any] = parse(WORKFLOW.read_text(encoding="utf-8"))
    return parsed


def job() -> dict[str, Any]:
    jobs: dict[str, dict[str, Any]] = workflow()["jobs"]
    return jobs["judge-release-cut"]


def steps() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = job()["steps"]
    return found


def test_it_runs_the_default_branchs_own_copy_on_pull_requests_into_main_only() -> None:
    assert workflow()[True] == {"pull_request_target": {"branches": ["main"]}}


def test_it_can_read_the_repository_and_write_commit_statuses_nothing_more() -> None:
    assert workflow()["permissions"] == {"contents": "read", "statuses": "write"}


def test_it_runs_one_job_named_apart_from_the_status_main_requires() -> None:
    assert list(workflow()["jobs"]) == ["judge-release-cut"]
    assert job().get("name", "judge-release-cut") == "judge-release-cut"


def test_a_job_that_hangs_stops_after_five_minutes() -> None:
    assert job()["timeout-minutes"] == 5


def test_it_runs_on_the_runner_ci_runs_on() -> None:
    assert job()["runs-on"] == ci()["jobs"]["lint"]["runs-on"]


def test_it_checks_out_the_default_branch_with_every_branchs_history_and_no_credential() -> None:
    checkout = steps()[0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"] == {"fetch-depth": 0, "persist-credentials": False}


def test_it_sets_up_uv_at_ci_s_version_with_no_cache() -> None:
    setup = steps()[1]
    assert setup["uses"].startswith("astral-sh/setup-uv@")
    assert setup["with"] == {"version": "${{ env.UV_VERSION }}"}
    assert workflow()["env"]["UV_VERSION"] == ci()["env"]["UV_VERSION"]


def test_it_runs_the_check_outside_the_project_with_every_input_through_env() -> None:
    check = steps()[2]
    assert check["run"] == (
        'uv run --no-project scripts/release_cut.py "$HEAD_REPOSITORY" "$HEAD_REF" "$HEAD_SHA" '
        '"$PR_NUMBER"'
    )
    assert check["env"] == {
        "HEAD_REPOSITORY": "${{ github.event.pull_request.head.repo.full_name }}",
        "HEAD_REF": "${{ github.head_ref }}",
        "HEAD_SHA": "${{ github.event.pull_request.head.sha }}",
        "PR_NUMBER": "${{ github.event.pull_request.number }}",
        "GITHUB_TOKEN": "${{ github.token }}",
    }


def test_no_shell_line_holds_an_expression() -> None:
    runs = [step["run"] for step in steps() if "run" in step]
    assert runs
    assert [run for run in runs if "${{" in run] == []


def test_it_runs_three_steps_checkout_uv_then_the_check() -> None:
    assert len(steps()) == 3


def test_it_pins_the_same_actions_at_the_same_shas_as_ci() -> None:
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    pins = set(re.findall(r"uses: (\S+@[0-9a-f]{40}) # (v\S+)", text))
    own = set(re.findall(r"uses: (\S+@[0-9a-f]{40}) # (v\S+)", WORKFLOW.read_text("utf-8")))
    assert own
    assert own <= pins


def test_the_workflow_file_is_where_the_docs_say() -> None:
    assert Path(".github/workflows/release-cut.yml").name in (ROOT / "RELEASING.md").read_text(
        encoding="utf-8"
    )
