"""The integration suites run in their own CI jobs, each with one limit at its step (#286): the
Python suite on every Python the unit suite runs on, the extension's in its workspace."""

import re
from typing import Any

from ci_workflow import ci

INTEGRATION_RUN = "uv run --locked pytest -W error --suite integration -p no:cacheprovider"
# The suite again under coverage, unlimited, so the limit never times the tracer (#374); its data
# goes to the coverage job (#446).
INTEGRATION_MEASURED = (
    'mkdir -p "${RUNNER_TEMP}/coverage-report"\n'
    'COVERAGE_FILE="${RUNNER_TEMP}/coverage-report/.coverage.${GITHUB_JOB}"'
    f" {INTEGRATION_RUN} --cov --cov-report=term\n"
)
# What runs a suite: pytest's suite option, vitest's project option, or an npm script for either.
SUITE_RUN = re.compile(r"--suite integration|--project integration|test:integration")


def job(name: str) -> dict[str, Any]:
    jobs: dict[str, dict[str, Any]] = ci()["jobs"]
    assert name in jobs, sorted(jobs)
    return jobs[name]


def test_the_integration_suite_runs_on_the_python_the_unit_suite_runs_on() -> None:
    """One Python since #382, the one .python-version pins: neither job has a matrix, and both
    names carry its minor (tests/guards/test_versions.py checks it against the pin)."""
    assert "strategy" not in job("integration")
    assert "strategy" not in job("test")
    assert job("test")["name"] == "test (py3.13)"
    assert job("integration")["name"] == "integration (py3.13)"


def test_the_integration_job_runs_the_integration_suite_alone_with_one_limit() -> None:
    steps = job("integration")["steps"]
    assert [step["run"] for step in steps if "pytest" in str(step.get("run", ""))] == [
        INTEGRATION_RUN,
        INTEGRATION_MEASURED,
    ]
    limited = [step for step in steps if "timeout-minutes" in step]
    assert [step["run"] for step in limited] == [INTEGRATION_RUN]
    # #292 moved the long real runs here (the golden window's CLI, paper and backtest runs). The
    # step took 31 s on CI on both Pythons (PR #316, run 38331680081), against #286's 6 s; a step
    # limit is whole minutes, and 3 is about six times the measured run.
    assert limited[0]["timeout-minutes"] == 3


def test_the_extension_integration_job_runs_its_two_suites_each_with_one_limit() -> None:
    steps = job("extension-integration")["steps"]
    npm = [step for step in steps if "npm " in str(step.get("run", ""))]
    assert [step["run"] for step in npm] == [
        "npm ci --ignore-scripts",
        "npm run test:integration",
        "npm run test:browser",
    ]
    assert [step.get("working-directory") for step in npm] == ["extension"] * 3
    limited = [step for step in steps if "timeout-minutes" in step]
    assert limited == npm[1:]
    # The integration suite measured on the laptop on 2026-10-13: 3 s. The browser suite runs
    # only in CI (#231): its limit is set from its first CI run.
    assert [step["timeout-minutes"] for step in limited] == [1, 2]


def test_chromium_is_installed_by_the_locked_playwright_before_the_browser_suite() -> None:
    steps = job("extension-integration")["steps"]
    runs = [step.get("run") for step in steps]
    install = runs.index("npx playwright install --with-deps chromium")
    assert install < runs.index("npm run test:browser")
    assert steps[install].get("working-directory") == "extension"


def test_no_other_job_runs_an_integration_suite() -> None:
    # A set: the integration job runs the suite twice, limited and measured (#374).
    runners = sorted(
        {
            name
            for name, found in ci()["jobs"].items()
            for step in found["steps"]
            if SUITE_RUN.search(str(step.get("run", "")))
        }
    )
    assert runners == ["extension-integration", "integration"]


def test_the_dev_deploy_waits_for_both_integration_jobs() -> None:
    needs = job("deploy-dev")["needs"]
    assert {"integration", "extension-integration"} <= set(needs)
