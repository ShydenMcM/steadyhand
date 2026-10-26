"""The integration suites run in their own CI jobs, each with one limit at its step (#286): the
Python suite on every Python the unit suite runs on, the extension's in its workspace."""

import re
from typing import Any

from ci_workflow import ci

INTEGRATION_RUN = "uv run --locked pytest -W error --suite integration -p no:cacheprovider"
# The suite again under coverage, unlimited, so the limit never times the tracer (#374).
INTEGRATION_MEASURED = (
    'mkdir -p "${RUNNER_TEMP}/coverage-report"\n'
    f'{INTEGRATION_RUN} --cov --cov-report="json:${{RUNNER_TEMP}}/coverage-report/coverage.json"\n'
    'git rev-parse HEAD > "${RUNNER_TEMP}/coverage-report/sha.txt"\n'
)
# The extension's suite runs natively under Node's own coverage, its report naming its commit
# (#394).
NATIVE_INTEGRATION = (
    'NODE_V8_COVERAGE="${RUNNER_TEMP}/node-coverage-raw" npm run test:native'
    " -- --project integration\n"
    'node tests/node-coverage-report.ts --raw "${RUNNER_TEMP}/node-coverage-raw"'
    ' --out "${RUNNER_TEMP}/node-coverage-report" --project integration\n'
    'git rev-parse HEAD > "${RUNNER_TEMP}/node-coverage-report/sha.txt"\n'
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


def test_the_extension_integration_job_installs_then_runs_its_suite_with_one_limit() -> None:
    steps = job("extension-integration")["steps"]
    npm = [step for step in steps if "npm " in str(step.get("run", ""))]
    assert [step["run"] for step in npm] == ["npm ci --ignore-scripts", NATIVE_INTEGRATION]
    assert [step.get("working-directory") for step in npm] == ["extension", "extension"]
    limited = [step for step in steps if "timeout-minutes" in step]
    assert limited == [npm[-1]]
    # Measured on the laptop on 2026-10-13: 3 s. Native, with its report (#394), on CI on 2026-10-23
    # (run 39921986342): 5 s.
    assert limited[0]["timeout-minutes"] == 1


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
