"""Which workflow lines a run took (#384): a workflow line when any job ran, a job line when its job
ran, a step line when its step started, and a shell line when bash traced its command."""

from functools import cache

import pytest

from workflow_coverage import (
    JobResult,
    RunError,
    StepResult,
    Trace,
    TraceError,
    Workflow,
    judge,
    layout,
    read_trace,
    results_from,
)

SHA = "a" * 40
OTHER = "b" * 40

WORKFLOW = """\
name: ci
jobs:
  lint:
    name: lint (py${{ matrix.python }})
    steps:
      - uses: actions/checkout@abc
      - name: Branch
        id: branch
        run: |
          if [ "$X" = y ]; then
            echo yes
          else
            echo no
          fi
      - run: echo single
      - name: Post results
        run: echo posted
  deploy:
    if: false
    steps:
      - run: echo d
"""


@cache
def flow() -> Workflow:
    """The workflow above, read once on first use (never at import: a red phase collects)."""
    return layout(WORKFLOW)


WORKFLOW_LINES = [1, 2]
LINT_LINES = [3, 4, 5]
DEPLOY_LINES = [18, 19, 20, 21]


def done(name: str, conclusion: str = "success") -> StepResult:
    return StepResult(name=name, status="completed", conclusion=conclusion)


def lint_job(name: str = "lint (py3.12)", **conclusions: str) -> JobResult:
    names = ["Run actions/checkout@abc", "Branch", "Run echo single", "Post results"]
    keys = ["checkout", "branch", "single", "post"]
    steps = (
        done("Set up job"),
        done("Pre Run actions/checkout@abc"),
        *(done(n, conclusions.get(k, "success")) for n, k in zip(names, keys, strict=True)),
        done("Post Run actions/checkout@abc"),
        done("Complete job"),
    )
    return JobResult(name=name, status="completed", conclusion="success", steps=steps)


SKIPPED_DEPLOY = JobResult(name="deploy", status="completed", conclusion="skipped", steps=())


def trace(action: str, lines: int, *traced: int, job: str = "lint", sha: str = SHA) -> Trace:
    return Trace(job=job, action=action, sha=sha, lines=lines, traced=frozenset(traced))


ALL_TRACES = (trace("branch", 5, 1, 4), trace("__run", 1, 1), trace("__run_2", 1, 1))


def test_a_run_that_took_one_arm_of_an_if_leaves_the_other_unrun() -> None:
    verdict = judge(flow(), [lint_job(), SKIPPED_DEPLOY], ALL_TRACES, SHA)
    assert verdict.missing == [11, *DEPLOY_LINES]
    assert verdict.executed == [
        *WORKFLOW_LINES,
        *LINT_LINES,
        6,
        7,
        8,
        9,
        10,
        13,
        15,
        16,
        17,
    ]


def test_keyword_lines_are_neither_run_nor_unrun() -> None:
    verdict = judge(flow(), [lint_job(), SKIPPED_DEPLOY], ALL_TRACES, SHA)
    for keyword_line in (12, 14):
        assert keyword_line not in verdict.executed
        assert keyword_line not in verdict.missing


def test_a_skipped_step_leaves_its_lines_and_its_shell_unrun() -> None:
    verdict = judge(
        flow(),
        [lint_job(single="skipped"), SKIPPED_DEPLOY],
        (trace("branch", 5, 1, 4), trace("__run_2", 1, 1)),
        SHA,
    )
    assert 15 in verdict.missing
    assert 15 not in verdict.executed


def test_a_step_still_running_has_started() -> None:
    job = lint_job()
    steps = list(job.steps)
    steps[5] = StepResult(name="Post results", status="in_progress", conclusion=None)
    running = JobResult(name=job.name, status="in_progress", conclusion=None, steps=tuple(steps))
    verdict = judge(flow(), [running, SKIPPED_DEPLOY], ALL_TRACES, SHA)
    assert 17 in verdict.executed


def test_a_step_not_yet_started_is_unrun() -> None:
    job = lint_job()
    steps = list(job.steps)
    steps[5] = StepResult(name="Post results", status="queued", conclusion=None)
    queued = JobResult(name=job.name, status="in_progress", conclusion=None, steps=tuple(steps))
    verdict = judge(flow(), [queued, SKIPPED_DEPLOY], ALL_TRACES[:2], SHA)
    assert [line for line in verdict.missing if line in (16, 17)] == [16, 17]


def test_a_failed_step_still_ran() -> None:
    verdict = judge(flow(), [lint_job(single="failure"), SKIPPED_DEPLOY], ALL_TRACES, SHA)
    assert 15 in verdict.executed


def test_a_skipped_job_leaves_every_line_of_it_unrun() -> None:
    verdict = judge(flow(), [lint_job(), SKIPPED_DEPLOY], ALL_TRACES, SHA)
    assert all(line in verdict.missing for line in DEPLOY_LINES)


def test_a_workflow_no_job_of_which_ran_is_unrun_from_its_first_line() -> None:
    skipped_lint = JobResult(
        name="lint (py3.12)", status="completed", conclusion="skipped", steps=()
    )
    verdict = judge(flow(), [skipped_lint, SKIPPED_DEPLOY], (), SHA)
    assert verdict.executed == []
    assert verdict.missing[:2] == WORKFLOW_LINES


def test_matrix_legs_join_so_a_line_either_leg_ran_is_run() -> None:
    other_leg = lint_job(name="lint (py3.13)")
    traces = (*ALL_TRACES, trace("branch", 5, 1, 2))
    verdict = judge(flow(), [lint_job(), other_leg, SKIPPED_DEPLOY], traces, SHA)
    assert 11 in verdict.executed
    assert 11 not in verdict.missing


@pytest.mark.parametrize(
    ("traces", "refusal"),
    [
        ((trace("branch", 5, 1, 4), trace("__run", 1, 1)), "no trace"),
        ((*ALL_TRACES, trace("__run_3", 1, 1)), "no step"),
        ((trace("branch", 6, 1, 4), *ALL_TRACES[1:]), "6 lines"),
        ((trace("branch", 5, 1, 4, sha=OTHER), *ALL_TRACES[1:]), OTHER),
        ((*ALL_TRACES, trace("__run", 1, 1, job="nojob")), "nojob"),
    ],
    ids=["missing-trace", "unknown-step", "line-count", "other-commit", "unknown-job"],
)
def test_traces_that_do_not_fit_the_run_are_refused(
    traces: tuple[Trace, ...], refusal: str
) -> None:
    with pytest.raises(TraceError, match=refusal):
        judge(flow(), [lint_job(), SKIPPED_DEPLOY], traces, SHA)


def test_a_job_the_workflow_does_not_name_is_refused() -> None:
    with pytest.raises(RunError, match="stranger"):
        judge(flow(), [lint_job(name="stranger"), SKIPPED_DEPLOY], ALL_TRACES, SHA)


def test_a_workflow_job_with_no_result_is_refused() -> None:
    with pytest.raises(RunError, match="deploy"):
        judge(flow(), [lint_job()], ALL_TRACES, SHA)


def test_steps_that_do_not_line_up_with_the_workflow_are_refused() -> None:
    job = lint_job()
    steps = list(job.steps)
    steps[3] = done("Renamed")
    renamed = JobResult(name=job.name, status="completed", conclusion="success", steps=tuple(steps))
    with pytest.raises(RunError, match="Renamed"):
        judge(flow(), [renamed, SKIPPED_DEPLOY], ALL_TRACES, SHA)


def test_a_step_the_run_lacks_is_refused() -> None:
    job = lint_job()
    short = JobResult(name=job.name, status="completed", conclusion="success", steps=job.steps[:5])
    with pytest.raises(RunError, match="Post results"):
        judge(flow(), [short, SKIPPED_DEPLOY], ALL_TRACES, SHA)


def test_a_trace_reads_its_header_and_line_numbers() -> None:
    read = read_trace("lint", "branch", f"sha {SHA}\nlines 5\n4\n1\n4\n")
    assert read == trace("branch", 5, 1, 4)


@pytest.mark.parametrize(
    ("text", "refusal"),
    [
        ("", "header"),
        (f"sha {SHA}\n", "header"),
        (f"lines 5\nsha {SHA}\n", "header"),
        (f"sha {SHA}\nlines five\n", "header"),
        (f"sha {SHA}\nlines 5\necho secret\n", "not a line number"),
        (f"sha {SHA}\nlines 5\n6\n", "beyond"),
        ("sha short\nlines 5\n", "header"),
    ],
    ids=["empty", "no-lines", "order", "count-text", "command-text", "beyond", "short-sha"],
)
def test_a_malformed_trace_is_refused(text: str, refusal: str) -> None:
    with pytest.raises(TraceError, match=refusal):
        read_trace("lint", "branch", text)


def test_the_bash_c_line_zero_is_dropped() -> None:
    """bash 3.2 traced the prelude's own ``. "$0"`` as line 0 (measured 2026-10-22)."""
    assert read_trace("lint", "x", f"sha {SHA}\nlines 1\n0\n1\n").traced == frozenset({1})


def test_a_step_the_workflow_lacks_is_refused() -> None:
    job = lint_job()
    steps = (*job.steps[:-1], done("Stray"), job.steps[-1])
    extra = JobResult(name=job.name, status="completed", conclusion="success", steps=steps)
    with pytest.raises(RunError, match="Stray"):
        judge(flow(), [extra, SKIPPED_DEPLOY], ALL_TRACES, SHA)


def test_a_trace_for_a_step_the_run_never_started_is_refused() -> None:
    with pytest.raises(TraceError, match="did not start"):
        judge(flow(), [lint_job(single="skipped"), SKIPPED_DEPLOY], ALL_TRACES, SHA)


def test_a_cancelled_step_counts_as_not_run() -> None:
    verdict = judge(
        flow(),
        [lint_job(single="cancelled"), SKIPPED_DEPLOY],
        (trace("branch", 5, 1, 4), trace("__run_2", 1, 1)),
        SHA,
    )
    assert 15 in verdict.missing


def test_the_jobs_listing_is_read_whole_or_refused() -> None:
    job = {"name": "deploy", "status": "completed", "conclusion": "skipped", "steps": []}
    assert results_from({"total_count": 1, "jobs": [job]}) == [SKIPPED_DEPLOY]
    with pytest.raises(RunError, match="lists 2 jobs but 1 were read"):
        results_from({"total_count": 2, "jobs": [job]})


def test_a_line_inside_a_command_that_ran_is_unrun_when_its_own_command_did_not() -> None:
    """``x=$(...)`` spans three lines and was traced; the ``echo`` on its middle line never ran,
    so that line is unrun: every command written on a line must have run."""
    nested = layout(
        "jobs:\n  a:\n    steps:\n      - run: |\n"
        "          x=$(if false; then\n            echo never\n          fi)\n"
    )
    job = JobResult(
        name="a",
        status="completed",
        conclusion="success",
        steps=(done("Set up job"), done("Run x=$(if false; then")),
    )
    verdict = judge(nested, [job], (trace("__run", 3, 1, 3, job="a"),), SHA)
    assert verdict.missing == [6]
    assert verdict.executed == [1, 2, 3, 4, 5, 7]


def test_a_run_job_whose_name_fits_two_workflow_jobs_is_refused() -> None:
    twins = layout("jobs:\n  test:\n    steps: []\n  other:\n    name: test (x)\n    steps: []\n")
    job = JobResult(name="test (x)", status="completed", conclusion="success", steps=())
    with pytest.raises(RunError, match="matches 2 jobs"):
        judge(twins, [job], (), SHA)
