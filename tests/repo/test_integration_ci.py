"""The integration suites run in their own CI jobs, each with one limit at its step (#286): the
Python suite on every Python the unit suite runs on, the extension's in its workspace."""

from typing import Any

from ci_workflow import ci

INTEGRATION_RUN = "uv run --locked pytest -W error --suite integration -p no:cacheprovider"


def job(name: str) -> dict[str, Any]:
    jobs: dict[str, dict[str, Any]] = ci()["jobs"]
    assert name in jobs, sorted(jobs)
    return jobs[name]


def test_the_integration_suite_runs_on_the_pythons_the_unit_suite_runs_on() -> None:
    assert job("integration")["strategy"]["matrix"] == job("test")["strategy"]["matrix"]
    assert job("integration")["name"] == "integration (py${{ matrix.python }})"


def test_the_integration_job_runs_the_integration_suite_alone_with_one_limit() -> None:
    steps = job("integration")["steps"]
    assert [step["run"] for step in steps if "pytest" in str(step.get("run", ""))] == [
        INTEGRATION_RUN
    ]
    limited = [step for step in steps if "timeout-minutes" in step]
    assert [step["run"] for step in limited] == [INTEGRATION_RUN]
    # Measured on the laptop on 2026-10-13: 6 s. A step limit is whole minutes, so the least it
    # can be is 1, about ten times the measured run.
    assert limited[0]["timeout-minutes"] == 1


def test_the_extension_integration_job_installs_then_runs_its_suite_with_one_limit() -> None:
    steps = job("extension-integration")["steps"]
    npm = [step for step in steps if str(step.get("run", "")).startswith("npm ")]
    assert [step["run"] for step in npm] == ["npm ci --ignore-scripts", "npm run test:integration"]
    assert [step.get("working-directory") for step in npm] == ["extension", "extension"]
    limited = [step for step in steps if "timeout-minutes" in step]
    assert limited == [npm[-1]]
    # Measured on the laptop on 2026-10-13: 3 s.
    assert limited[0]["timeout-minutes"] == 1


def test_no_other_job_runs_an_integration_suite() -> None:
    runners = sorted(
        name
        for name, found in ci()["jobs"].items()
        for step in found["steps"]
        if "integration" in str(step.get("run", ""))
    )
    assert runners == ["extension-integration", "integration"]


def test_the_dev_deploy_waits_for_both_integration_jobs() -> None:
    needs = job("deploy-dev")["needs"]
    assert {"integration", "extension-integration"} <= set(needs)
