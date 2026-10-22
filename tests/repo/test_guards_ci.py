"""The Python guards run in their own CI job, on every Python the unit suite runs on (#285)."""

from typing import Any

from ci_workflow import ci

GUARDS_RUN = "uv run --locked pytest -W error --suite guards -p no:cacheprovider"


def job(name: str) -> dict[str, Any]:
    jobs: dict[str, dict[str, Any]] = ci()["jobs"]
    assert name in jobs, sorted(jobs)
    return jobs[name]


def runs(name: str) -> list[str]:
    return [str(step["run"]) for step in job(name)["steps"] if "run" in step]


def test_the_guards_run_on_the_pythons_the_unit_suite_runs_on() -> None:
    assert job("guards")["strategy"]["matrix"] == job("test")["strategy"]["matrix"]
    assert job("guards")["name"] == "guards (py${{ matrix.python }})"


GUARDS_MEASURED = (
    'mkdir -p "${RUNNER_TEMP}/coverage-report"\n'
    f'{GUARDS_RUN} --cov --cov-report="json:${{RUNNER_TEMP}}/coverage-report/coverage.json"\n'
    'git rev-parse HEAD > "${RUNNER_TEMP}/coverage-report/sha.txt"\n'
)


def test_the_guards_job_runs_the_guards_once_limited_and_once_measured() -> None:
    """The limit times the suite alone; the coverage run (#381) has no limit of its own, as the
    unit job's has none, so the tracer is never timed."""
    assert [run for run in runs("guards") if "pytest" in run] == [GUARDS_RUN, GUARDS_MEASURED]
    limited = [step for step in job("guards")["steps"] if "timeout-minutes" in step]
    assert [step["run"] for step in limited] == [GUARDS_RUN]
    # Measured on CI on 2026-10-12 (run 38273371897): 6 s on each Python. A step limit is whole
    # minutes, so the least it can be is 1, about ten times the measured run.
    assert limited[0]["timeout-minutes"] == 1


LIMITS_RUN = "uv run --locked pytest -W error -p no:cacheprovider"


def test_the_unit_job_runs_the_default_suite_never_the_guards() -> None:
    tests = [run for run in runs("test") if "pytest" in run]
    assert len(tests) == 4
    assert [run for run in tests if "--suite" in run] == []


def test_the_unit_limits_are_judged_in_a_run_without_coverage() -> None:
    """A load timed under coverage times its tracer too, so that run judges none (#285)."""
    limits = [
        step
        for step in job("test")["steps"]
        if step.get("name") == "Unit limits, judged without coverage"
    ]
    assert [step["run"] for step in limits] == [LIMITS_RUN]
