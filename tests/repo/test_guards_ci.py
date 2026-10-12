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


def test_the_guards_job_runs_the_guards_suite_with_one_limit_and_no_coverage() -> None:
    assert [run for run in runs("guards") if "pytest" in run] == [GUARDS_RUN]
    limited = [step for step in job("guards")["steps"] if "timeout-minutes" in step]
    assert [step["run"] for step in limited] == [GUARDS_RUN]


def test_the_unit_job_runs_the_default_suite_never_the_guards() -> None:
    tests = [run for run in runs("test") if "pytest" in run]
    assert len(tests) == 2
    assert [run for run in tests if "--suite" in run] == []
