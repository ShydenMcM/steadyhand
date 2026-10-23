"""Every job keeps its steps' traces, and the coverage job reads them all (#384)."""

import re
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


# Every coverage report a job keeps, and every one the gate reads (#381, #394): a report kept but
# not judged would pass unread, and one judged but never kept fails only when the run reaches it.
REPORTS = [
    "coverage-extension-guards",
    "coverage-extension-guards-node",
    "coverage-extension-integration-node",
    "coverage-extension-unit",
    "coverage-extension-unit-node",
    "coverage-python-3.12",
    "coverage-python-3.13",
    "coverage-python-guards-3.12",
    "coverage-python-guards-3.13",
]
MATRIX_PYTHON = "${{ matrix.python }}"


def kept_reports() -> list[str]:
    """Each coverage artifact a ci.yml job uploads, one per Python of its matrix."""
    kept: list[str] = []
    for job in ci()["jobs"].values():
        for step in job["steps"]:
            name = str(step.get("with", {}).get("name", ""))
            if str(step.get("uses", "")).startswith("actions/upload-artifact@") and name.startswith(
                "coverage-"
            ):
                pythons = job["strategy"]["matrix"]["python"] if MATRIX_PYTHON in name else [""]
                kept += [name.replace(MATRIX_PYTHON, python) for python in pythons]
    return sorted(kept)


def judged_reports() -> list[str]:
    """Each report folder the gate is given, every --python and --istanbul flag read."""
    gate = ci()["jobs"]["coverage"]["steps"][-1]["run"].splitlines()[1].split(" && ")[1]
    folders = re.findall(r'--(?:python|istanbul) "\$\{RUNNER_TEMP\}/coverage/([^"]+)"', gate)
    assert len(folders) == len(re.findall(r"--(?:python|istanbul) ", gate)), gate
    return sorted(folders)


def test_every_coverage_report_a_job_keeps_is_judged_by_the_gate() -> None:
    assert kept_reports() == REPORTS


def test_the_gate_judges_every_coverage_report_a_job_keeps() -> None:
    assert judged_reports() == REPORTS
