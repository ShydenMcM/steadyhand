"""Where each line of a workflow belongs: the workflow, a job, a step, or a line of a step's shell
(#384). A line no run could take (blank, a YAML comment) is not code."""

import pytest
import yaml

from workflow_coverage import WorkflowError, layout

WORKFLOW = """\
name: ci
# a comment

on:
  push:
jobs:
  lint:
    name: lint (py${{ matrix.python }})
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@abc # v1
        with:
          persist-credentials: false
      - name: Two lines
        id: two
        run: |
          echo one

          echo two
      - run: echo single
  deploy:
    needs: [lint]
    steps:
      - run: echo d
"""


def test_every_code_line_has_its_place_and_blank_and_comment_lines_have_none() -> None:
    flow = layout(WORKFLOW)
    assert flow.lines == {
        1: ("workflow",),
        4: ("workflow",),
        5: ("workflow",),
        6: ("workflow",),
        7: ("job", "lint"),
        8: ("job", "lint"),
        9: ("job", "lint"),
        10: ("job", "lint"),
        11: ("step", "lint", 0),
        12: ("step", "lint", 0),
        13: ("step", "lint", 0),
        14: ("step", "lint", 1),
        15: ("step", "lint", 1),
        16: ("step", "lint", 1),
        17: ("shell", "lint", 1, 1),
        18: ("shell", "lint", 1, 2),
        19: ("shell", "lint", 1, 3),
        20: ("shell", "lint", 2, 1),
        21: ("job", "deploy"),
        22: ("job", "deploy"),
        23: ("job", "deploy"),
        24: ("shell", "deploy", 0, 1),
    }


def test_each_step_is_read_with_its_name_run_uses_and_id() -> None:
    flow = layout(WORKFLOW)
    assert flow.jobs["lint"].name == "lint (py${{ matrix.python }})"
    assert flow.jobs["deploy"].name is None
    steps = flow.jobs["lint"].steps
    assert [(s.name, s.step_id, s.uses) for s in steps] == [
        (None, None, "actions/checkout@abc"),
        ("Two lines", "two", None),
        (None, None, None),
    ]
    assert [s.run for s in steps] == [None, "echo one\n\necho two\n", "echo single"]


def test_a_comment_inside_a_shell_step_is_a_shell_line() -> None:
    flow = layout("jobs:\n  a:\n    steps:\n      - run: |\n          # note\n          echo x\n")
    assert flow.lines[5] == ("shell", "a", 0, 1)


@pytest.mark.parametrize(
    ("text", "refusal"),
    [
        ("jobs:\n  a:\n    steps:\n      - run: >\n          echo x\n          echo y\n", "folded"),
        (
            'jobs:\n  a:\n    steps:\n      - run: "echo x\n          echo y"\n',
            "over several lines",
        ),
        ("jobs:\n  a:\n    steps:\n      - shell: sh\n        run: echo x\n", "its own shell"),
        (
            "jobs:\n  a:\n    defaults:\n      run:\n        shell: sh\n    steps: []\n",
            "its own shell",
        ),
        ("jobs:\n  a:\n    uses: o/r/.github/workflows/w.yml@v1\n", "reusable workflow"),
        ("jobs:\n  a:\n    container: node\n    steps: []\n", "container"),
        ("jobs:\n  a:\n    steps:\n      - run: trap - DEBUG\n", "DEBUG"),
        ("jobs:\n  a:\n    steps:\n      - run: echo 1 >> x/workflow-trace/y\n", "workflow-trace"),
        ("jobs:\n  a:\n    steps:\n      - run: echo $__wt_t\n", "__wt_"),
        ("jobs:\n  a:\n    steps:\n      - run: if then fi (\n", "does not parse"),
        ("jobs: [a]\n", "jobs"),
        ("name: x\n", "jobs"),
        ("jobs:\n  a:\n    steps: {}\n", "steps"),
        ("[]\n", "not a mapping"),
        ("jobs:\n  a: x\n", "job a is not a mapping"),
        ("jobs:\n  a:\n    steps: [echo]\n", "step 1 is not a mapping"),
        ("jobs:\n  a:\n    steps:\n      - run: [echo]\n", "run is not text"),
    ],
    ids=[
        "folded",
        "quoted-multiline",
        "step-shell",
        "job-shell",
        "reusable",
        "container",
        "debug-trap",
        "trace-path",
        "trace-variable",
        "parse-error",
        "jobs-not-a-mapping",
        "no-jobs",
        "steps-not-a-list",
        "workflow-not-a-mapping",
        "job-not-a-mapping",
        "step-not-a-mapping",
        "run-not-text",
    ],
)
def test_a_workflow_the_reader_cannot_judge_is_refused(text: str, refusal: str) -> None:
    with pytest.raises(WorkflowError, match=refusal):
        layout(text)


def test_a_job_with_no_steps_has_only_job_lines() -> None:
    flow = layout("jobs:\n  a:\n    runs-on: x\n")
    assert flow.jobs["a"].steps == ()
    assert flow.lines == {1: ("workflow",), 2: ("job", "a"), 3: ("job", "a")}


def test_job_defaults_that_set_no_shell_are_read() -> None:
    text = "jobs:\n  a:\n    defaults:\n      run:\n        working-directory: x\n    steps: []\n"
    assert layout(text).lines[5] == ("job", "a")


def test_job_defaults_that_are_not_a_mapping_set_no_shell() -> None:
    assert layout("jobs:\n  a:\n    defaults: []\n    steps: []\n").lines[3] == ("job", "a")


def test_a_pyyaml_without_libyaml_is_refused_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(yaml, "CSafeLoader")
    with pytest.raises(WorkflowError, match="no CSafeLoader"):
        layout("jobs: {}\n")
