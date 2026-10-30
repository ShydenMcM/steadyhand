"""The Hypothesis properties run in their own CI job, with one limit at its step (#290): every
property at its full count, fresh cases each run, coverage off, on every Python the unit suite
runs on."""

from typing import Any

from ci_workflow import ci

PROPERTIES_RUN = "uv run --locked pytest -W error --suite properties -p no:cacheprovider"
# Measured once, unlimited, its data for the coverage job (#446).
PROPERTIES_MEASURED = (
    'mkdir -p "${RUNNER_TEMP}/coverage-report"\n'
    'COVERAGE_FILE="${RUNNER_TEMP}/coverage-report/.coverage.${GITHUB_JOB}"'
    f" {PROPERTIES_RUN} --cov --cov-report=term\n"
)


def job(name: str) -> dict[str, Any]:
    jobs: dict[str, dict[str, Any]] = ci()["jobs"]
    assert name in jobs, sorted(jobs)
    return jobs[name]


def test_the_properties_run_on_the_python_the_unit_suite_runs_on() -> None:
    """One Python since #382, the one .python-version pins: neither job has a matrix, and both
    names carry its minor (tests/guards/test_versions.py checks it against the pin)."""
    assert "strategy" not in job("properties")
    assert "strategy" not in job("test")
    assert job("test")["name"] == "test (py3.13)"
    assert job("properties")["name"] == "properties (py3.13)"


def test_the_properties_job_runs_the_properties_suite_alone_with_one_limit() -> None:
    steps = job("properties")["steps"]
    assert [step["run"] for step in steps if "pytest" in str(step.get("run", ""))] == [
        PROPERTIES_RUN,
        PROPERTIES_MEASURED,
    ]
    limited = [step for step in steps if "timeout-minutes" in step]
    assert [step["run"] for step in limited] == [PROPERTIES_RUN]
    # Measured on CI (#289, 2026-10-12, three runs a Python): the 33 property cases took 60.5 s
    # together in their worst runs, the slowest alone 19.5 s. Two minutes is about twice that.
    assert limited[0]["timeout-minutes"] == 2


def test_no_other_job_runs_the_properties_suite() -> None:
    # A set: the properties job runs the suite twice, once limited and once measured.
    runners = sorted(
        {
            name
            for name, found in ci()["jobs"].items()
            for step in found["steps"]
            if "--suite properties" in str(step.get("run", ""))
        }
    )
    assert runners == ["properties"]


def test_no_job_chooses_a_hypothesis_profile() -> None:
    # The properties suite loads its one profile itself (tests/properties/hypothesis_profile.py).
    assert "HYPOTHESIS_PROFILE" not in str(ci())


def test_the_dev_deploy_waits_for_the_properties() -> None:
    assert "properties" in job("deploy-dev")["needs"]
