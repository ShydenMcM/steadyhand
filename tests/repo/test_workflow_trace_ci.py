"""Every job keeps its steps' traces, and the coverage job reads them all (#384)."""

from pathlib import Path
from typing import Any

import pytest
from ci_workflow import ci, parse

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))
UPLOAD = {
    "name": "Keep the workflow trace",
    "if": "${{ !cancelled() }}",
    "uses": "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9",
    "with": {
        "name": "workflow-trace-${{ github.job }}-${{ strategy.job-index }}",
        "path": "${{ runner.temp }}/workflow-trace",
        "if-no-files-found": "error",
        "retention-days": 7,
    },
}
JOBS = [
    (path, key, job)
    for path in WORKFLOWS
    for key, job in parse(path.read_text(encoding="utf-8"))["jobs"].items()
    if (path.name, key) != ("ci.yml", "coverage")
]


@pytest.mark.parametrize(
    ("path", "key", "job"), JOBS, ids=[f"{path.name}:{key}" for path, key, _ in JOBS]
)
def test_every_job_ends_by_keeping_its_trace_whatever_its_outcome(
    path: Path, key: str, job: dict[str, Any]
) -> None:
    assert job["steps"][-1] == UPLOAD, (path.name, key)
    assert [step.get("name") for step in job["steps"]].count(UPLOAD["name"]) == 1


def test_the_coverage_job_waits_for_every_other_job_and_keeps_no_trace_of_its_own() -> None:
    jobs: dict[str, dict[str, Any]] = ci()["jobs"]
    coverage = jobs["coverage"]
    assert sorted(coverage["needs"]) == sorted(key for key in jobs if key != "coverage")
    assert coverage["if"] == "${{ !cancelled() }}"
    assert UPLOAD["name"] not in [step.get("name") for step in coverage["steps"]]
    assert coverage["permissions"] == {"contents": "read", "actions": "read"}


def test_the_coverage_jobs_last_step_reads_this_run_then_judges_it_on_one_line() -> None:
    """The step's own trace reaches only the line it is on when the reader reads it, so the
    reader and the gate (#381) begin on one line, and nothing follows (#384)."""
    last = ci()["jobs"]["coverage"]["steps"][-1]
    assert last["name"] == "Every file matches the coverage record and every changed line ran"
    lines = last["run"].splitlines()
    assert len(lines) == 2
    assert "/attempts/${GITHUB_RUN_ATTEMPT}/jobs?per_page=100" in lines[0]
    reader, gate = lines[1].split(" && ")
    assert reader.startswith("uv run --locked python scripts/workflow_coverage.py ")
    assert "--own-traces" in reader
    assert '--traces "${RUNNER_TEMP}/traces"' in reader
    assert gate.startswith("uv run --locked python scripts/coverage_gate.py ")
    assert '--workflow "${RUNNER_TEMP}/workflow-coverage"' in gate
