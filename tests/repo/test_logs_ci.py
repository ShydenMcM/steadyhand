"""The logs suite runs in its own hand-started workflow, never on a pull request (#336): one job,
one limit at its suite step, and the same suite again under coverage for the gate to read."""

from functools import cache
from typing import Any

from ci_workflow import ROOT, ci, parse

from coverage_gate import MEASURED_ONLY_BY

LOGS = ".github/workflows/logs.yml"
LOGS_RUN = "uv run --locked pytest -W error --suite logs -p no:cacheprovider"
# The suite again under coverage, unlimited, its report kept by the name workflow_runs.py reads.
LOGS_MEASURED = (
    'mkdir -p "${RUNNER_TEMP}/coverage-logs"\n'
    f'{LOGS_RUN} --cov --cov-report="json:${{RUNNER_TEMP}}/coverage-logs/coverage.json"\n'
    'git rev-parse HEAD > "${RUNNER_TEMP}/coverage-logs/sha.txt"\n'
)


@cache
def logs() -> dict[str | bool, Any]:
    parsed: dict[str | bool, Any] = parse((ROOT / LOGS).read_text(encoding="utf-8"))
    return parsed


def steps() -> list[dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = logs()["jobs"]
    assert list(jobs) == ["logs"]
    found: list[dict[str, Any]] = jobs["logs"]["steps"]
    return found


def test_the_logs_workflow_is_started_by_hand_alone() -> None:
    # YAML reads the bare key on as True.
    assert logs()[True] == {"workflow_dispatch": None}


def test_the_logs_workflow_reads_and_writes_nothing_else() -> None:
    assert logs()["permissions"] == {"contents": "read"}
    assert logs()["jobs"]["logs"]["permissions"] == {"contents": "read"}


def test_the_logs_job_runs_the_logs_suite_alone_with_one_limit() -> None:
    assert [step["run"] for step in steps() if "pytest" in str(step.get("run", ""))] == [
        LOGS_RUN,
        LOGS_MEASURED,
    ]
    limited = [step for step in steps() if "timeout-minutes" in step]
    assert [step["run"] for step in limited] == [LOGS_RUN]
    # PROVISIONAL until the first run on CI is measured (#336).
    assert limited[0]["timeout-minutes"] == 10


def test_the_logs_suites_coverage_report_is_kept_by_the_name_the_gate_reads() -> None:
    kept = [step for step in steps() if "upload-artifact" in str(step.get("uses", ""))]
    assert [step["with"]["name"] for step in kept] == [
        "coverage-python-logs",
        "workflow-trace-${{ github.job }}-${{ strategy.job-index }}",
    ]
    assert kept[0]["with"]["path"] == "${{ runner.temp }}/coverage-logs"
    assert kept[0]["with"]["if-no-files-found"] == "error"


def test_the_logs_workflow_alone_measures_every_file_under_tests_logs() -> None:
    assert MEASURED_ONLY_BY[LOGS] == ("tests/logs/",)


def test_no_ci_job_runs_the_logs_suite() -> None:
    """The logs suite runs before each release, not on every pull request (AC 5)."""
    assert "--suite logs" not in str(ci())
