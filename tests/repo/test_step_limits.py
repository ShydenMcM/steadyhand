"""The suites outside unit keep one limit each, at their CI step, and none inside (#323 AC 5).

The unit limits are per test (``tests/plugins/unit_limits.py``); the guards, integration and
properties suites are pinned in their own files. This file pins the two left: the performance
step, which times the ten-year backtest against its product budget, and the live Yahoo check.
Each limit is whole minutes, set from the step's measured time on CI plus a stated margin.
"""

import shlex
from pathlib import Path
from typing import Any

from ci_workflow import ROOT, ci, parse

from coverage_gate import MEASURED_ONLY_BY

YAHOO_SHAPE = ".github/workflows/yahoo-shape.yml"

PERF_RUN = "uv run --locked pytest -W error -m perf -p no:cacheprovider"
# The same tests again under coverage, judging no time (#374 AC9, perf_budget.py): its own
# report folder, since the unit report's is the test job's too.
PERF_MEASURED = (
    'mkdir -p "${RUNNER_TEMP}/coverage-perf"\n'
    f"{PERF_RUN} --measured --cov "
    '--cov-report="json:${RUNNER_TEMP}/coverage-perf/coverage.json"\n'
    'git rev-parse HEAD > "${RUNNER_TEMP}/coverage-perf/sha.txt"\n'
)
LIVE_RUN = (
    "uv run --locked pytest -W error -m live -p no:cacheprovider tests/idx/test_yahoo_live.py"
)
# The live check again under coverage, judging no time (#374 AC9): workflow_runs.py reads its
# report from a run on the pull request's commit, by the name below.
LIVE_MEASURED = (
    'mkdir -p "${RUNNER_TEMP}/coverage-live"\n'
    "uv run --locked pytest -W error -m live -p no:cacheprovider --measured --cov "
    '--cov-report="json:${RUNNER_TEMP}/coverage-live/coverage.json" tests/idx/test_yahoo_live.py\n'
    'git rev-parse HEAD > "${RUNNER_TEMP}/coverage-live/sha.txt"\n'
)


def shape_steps() -> list[dict[str, Any]]:
    workflow = parse(Path(ROOT / YAHOO_SHAPE).read_text(encoding="utf-8"))
    steps: list[dict[str, Any]] = workflow["jobs"]["shape"]["steps"]
    return steps


def steps_running(steps: list[dict[str, Any]], marker: str) -> list[dict[str, Any]]:
    return [step for step in steps if f"-m {marker} " in str(step.get("run", ""))]


def test_the_performance_step_has_one_limit_of_two_minutes() -> None:
    """Once limited and judged, once measured with no limit of its own, as the guards job runs
    its suite (#374 AC9): the tracer is never timed."""
    steps = ci()["jobs"]["test"]["steps"]
    assert [step["run"] for step in steps_running(steps, "perf")] == [PERF_RUN, PERF_MEASURED]
    perf = [step for step in steps_running(steps, "perf") if "timeout-minutes" in step]
    assert [step["run"] for step in perf] == [PERF_RUN]
    # Measured on CI, 2026-10-15: 13-29 s over 18 job runs (9 develop runs, py3.12 and py3.13,
    # 38288047404 to 38507014020). Two minutes is about four times the slowest; the test's own
    # product budget (30 s) fails it first.
    assert perf[0]["timeout-minutes"] == 2


def test_the_live_step_has_one_limit_of_two_minutes() -> None:
    """Once limited and judged, once measured with no limit of its own (#374 AC9)."""
    assert [step["run"] for step in steps_running(shape_steps(), "live")] == [
        LIVE_RUN,
        LIVE_MEASURED,
    ]
    live = [step for step in steps_running(shape_steps(), "live") if "timeout-minutes" in step]
    assert [step["run"] for step in live] == [LIVE_RUN]
    # Measured on CI, 2026-10-15: 6-9 s over the 8 successful runs (2026-09-27 to 10-04). It
    # waits on Yahoo's network, so its margin is wider than a CPU-bound step's: two minutes.
    assert live[0]["timeout-minutes"] == 2


def test_no_other_step_of_those_jobs_carries_a_limit() -> None:
    test_steps = ci()["jobs"]["test"]["steps"]
    limited = [
        step.get("name", step.get("run"))
        for step in [*test_steps, *shape_steps()]
        if "timeout-minutes" in step
    ]
    assert limited == [
        "Performance, a ten-year backtest in under 30 seconds",
        "Yahoo still gives what the fixtures recorded",
    ]


def test_the_measured_live_report_is_kept_by_the_name_workflow_runs_reads() -> None:
    """workflow_runs.py downloads coverage-python-<workflow stem> from the run (G8)."""
    kept = [
        s
        for s in shape_steps()
        if s.get("with", {}).get("path") == "${{ runner.temp }}/coverage-live"
    ]
    assert [
        (s["uses"].split("@")[0], s["with"]["name"], s["with"]["if-no-files-found"]) for s in kept
    ] == [("actions/upload-artifact", "coverage-python-yahoo-shape", "error")]


def test_the_files_only_yahoo_shape_measures_are_the_files_its_live_steps_run() -> None:
    """MEASURED_ONLY_BY names what the gate carries; the steps name what is run (G9)."""
    named = [
        sorted(word for word in shlex.split(line) if word.endswith(".py"))
        for step in steps_running(shape_steps(), "live")
        for line in step["run"].splitlines()
        if " pytest " in line
    ]
    assert named == [sorted(MEASURED_ONLY_BY[YAHOO_SHAPE])] * 2
    assert list(MEASURED_ONLY_BY) == [YAHOO_SHAPE]
