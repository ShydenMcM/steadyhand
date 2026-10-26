"""The versions guard's readers, each seen finding a plant of every form it must recognise (#382).

The guard (``tests/guards/test_versions.py``) runs them over the repository's workflows and
pyproject files; here each form is written out by hand, never generated from a reader's own list.
"""

from typing import Any

import pytest
from workflow_versions import (
    NAMED_MINOR,
    RUNNER,
    SETUP_UV,
    UnreadableShellError,
    exact_version,
    pyproject_findings,
    python_findings,
    python_version_keys,
    runner_findings,
    step_findings,
    strings,
    venvs_made,
)


def jobs_on(runs_on: object) -> dict[str, Any]:
    second: dict[str, Any] = {} if runs_on is None else {"runs-on": runs_on}
    return {"jobs": {"a": {"runs-on": RUNNER}, "b": second}}


@pytest.mark.parametrize(
    "runs_on",
    [
        pytest.param("ubuntu-24.04", id="an-older-image"),
        pytest.param("ubuntu-latest", id="a-floating-image"),
        pytest.param("UBUNTU-26.04", id="another-case"),
        pytest.param([RUNNER], id="a-list"),
        pytest.param({"group": "big", "labels": [RUNNER]}, id="a-group"),
        pytest.param("${{ matrix.os }}", id="an-expression"),
        pytest.param(None, id="none-at-all"),
    ],
)
def test_a_job_on_any_other_runner_is_found(runs_on: object) -> None:
    assert runner_findings(jobs_on(runs_on)) == [f"b: {runs_on!r}"]


def test_jobs_on_the_one_runner_are_not_found() -> None:
    assert runner_findings(jobs_on(RUNNER)) == []


@pytest.mark.parametrize(
    "script",
    [
        pytest.param("python3 scripts/ci_scope.py", id="python3"),
        pytest.param("python scripts/x.py", id="python"),
        pytest.param("python3.12 -m pip list", id="a-versioned-name"),
        pytest.param("/usr/bin/python3 x.py", id="a-path"),
        pytest.param("scripts/ci_scope.py push", id="a-script-run-as-a-program"),
        pytest.param("./x.py", id="a-script-by-relative-path"),
        pytest.param("echo a; python3 x.py", id="after-a-semicolon"),
        pytest.param("true && python3 x.py", id="after-and"),
        pytest.param("true || python3 x.py", id="after-or"),
        pytest.param("echo a | python3 x.py", id="after-a-pipe"),
        pytest.param('X="$(python3 x.py)"', id="in-a-quoted-command-substitution"),
        pytest.param("X=$(python3 x.py)", id="in-a-command-substitution"),
        pytest.param("X=$(true); python3 x.py", id="after-grouped-punctuation"),
        pytest.param("X=$(true)&& python3 x.py", id="after-grouped-and"),
        pytest.param("echo `python3 x.py`", id="in-backticks"),
        pytest.param('echo "`python3 x.py`"', id="in-quoted-backticks"),
        pytest.param('echo "$(echo $(python3 x.py))"', id="in-a-nested-substitution"),
        pytest.param('echo "a $(true) b $(python3 x.py)"', id="in-a-second-substitution"),
        pytest.param("if python3 x.py; then echo; fi", id="after-if"),
        pytest.param("while python3 x.py; do echo; done", id="after-while"),
        pytest.param("! python3 x.py", id="after-not"),
        pytest.param("{ python3 x.py; }", id="in-a-group"),
        pytest.param("env A=1 python3 x.py", id="after-env"),
        pytest.param("A=1 python3 x.py", id="after-an-assignment"),
        pytest.param("time python3 x.py", id="after-time"),
        pytest.param("exec python3 x.py", id="after-exec"),
        pytest.param("echo a \\\n  && python3 x.py", id="on-a-continued-line"),
        pytest.param("echo a\npython3 x.py", id="on-a-later-line"),
        pytest.param("python3 - <<'EOF'\nprint(1)\nEOF", id="a-heredoc"),
        pytest.param("cat <<'EOF'\npython3 here is input\nEOF\npython3 x.py", id="after-a-heredoc"),
        pytest.param("cat <<-EOF\n\tinput\n\tEOF\npython3 x.py", id="after-a-tab-heredoc"),
        pytest.param("cat <(python3 x.py)", id="in-a-process-substitution"),
        pytest.param(
            "echo EOF; cat <<EOF\ninput\nEOF\npython3 x.py", id="a-delimiter-seen-earlier"
        ),
        pytest.param("echo a > out.txt; python3 x.py", id="after-a-redirect"),
        pytest.param("echo a 2>&1 | python3 x.py", id="after-a-descriptor-redirect"),
        pytest.param('"$PY" x.py', id="a-program-in-a-variable"),
        pytest.param("$(which python3) x.py", id="a-program-from-a-substitution"),
        pytest.param("uv run --python 3.12 x.py", id="uv-asked-for-a-version"),
        pytest.param("uv run -p 3.12 x.py", id="uv-asked-for-a-version-short"),
        pytest.param("uv run --python=3.12 x.py", id="uv-asked-for-a-version-equals"),
        pytest.param("uv sync --python cpython-3.12", id="uv-sync-asked-for-a-version"),
        pytest.param("uv venv --python python3.12 v", id="uv-venv-asked-for-an-interpreter"),
        pytest.param("uvx --python 3.12 ruff", id="uvx-asked-for-a-version"),
    ],
)
def test_python_run_outside_uv_is_found(script: str) -> None:
    assert len(python_findings(script)) == 1


@pytest.mark.parametrize(
    "script",
    [
        pytest.param("uv run --no-project scripts/ci_scope.py push", id="uv-run-a-script"),
        pytest.param("uv run --locked python scripts/run_mutations.py", id="uv-run-python"),
        pytest.param('uv pip install --python "$T/x" a.whl', id="uv-pip-an-environment"),
        pytest.param("echo python3 is not run here", id="python-as-an-argument"),
        pytest.param("ruff check scripts/x.py", id="a-py-file-as-an-argument"),
        pytest.param("# python3 x.py", id="a-comment"),
        pytest.param("", id="an-empty-script"),
        pytest.param("echo a > out.py", id="a-py-file-as-a-redirect-target"),
        pytest.param(
            "cat <<'PY'\nimport sys; print('unclosed\npython3 x.py\nPY", id="a-heredoc-body"
        ),
        pytest.param('uv venv "$T/v"\n"$T/v/bin/python" -c 1', id="a-venv-uv-made"),
        pytest.param('uv venv "$T/v"\n"$T/v/bin/tool" run', id="a-venv-entry-point"),
    ],
)
def test_python_through_uv_or_named_as_an_argument_is_not_found(script: str) -> None:
    assert python_findings(script, venvs_made(script)) == []


def test_a_venv_is_made_only_by_uv_venv() -> None:
    made = venvs_made('uv venv "$T/a"\nuv venv --seed b\nuv venv\nmkdir c')
    assert made == {"$T/a", "b", ".venv"}


def test_a_venv_python_with_no_uv_venv_is_found() -> None:
    assert python_findings('"$T/v/bin/python" -c 1') == ["$T/v/bin/python -c 1"]


@pytest.mark.parametrize(
    "script",
    [
        pytest.param("echo 'unclosed", id="an-unclosed-quote"),
        pytest.param('echo "$(python3 x.py"', id="an-unclosed-substitution"),
        # Inside $( ), bash starts its quoting afresh; shlex cannot, so the line is refused.
        pytest.param('echo "$(echo "$(python3 x.py)")"', id="quotes-inside-a-substitution"),
    ],
)
def test_an_unreadable_shell_line_is_refused_by_name(script: str) -> None:
    with pytest.raises(UnreadableShellError, match=r"^cannot read the shell line "):
        python_findings(script)


def steps(*listed: dict[str, Any], **workflow: object) -> dict[str, Any]:
    return {**workflow, "jobs": {"j": {"runs-on": RUNNER, "steps": list(listed)}}}


SHA = "0" * 40
UV = {"uses": f"{SETUP_UV}{SHA}"}


@pytest.mark.parametrize(
    ("workflow", "finding"),
    [
        pytest.param(steps({"run": "uv sync"}, UV), "j step 1: uv before setup-uv", id="uv-first"),
        pytest.param(steps({"run": "uv sync"}), "j step 1: uv before setup-uv", id="no-setup"),
        pytest.param(
            steps({"run": "uvx ruff"}), "j step 1: uv before setup-uv", id="uvx-with-no-setup"
        ),
        pytest.param(
            steps({"uses": f"actions/setup-python@{SHA}"}),
            f"j step 1: actions/setup-python@{SHA}",
            id="setup-python",
        ),
        pytest.param(
            steps({"uses": f"Actions/Setup-Python@{SHA}"}),
            f"j step 1: Actions/Setup-Python@{SHA}",
            id="setup-python-another-case",
        ),
        pytest.param(
            steps({"run": "print(1)", "shell": "python"}),
            "j step 1: shell 'python'",
            id="a-python-shell",
        ),
        pytest.param(
            steps(defaults={"run": {"shell": "python {0}"}}),
            "defaults: shell 'python {0}'",
            id="a-python-default-shell",
        ),
        pytest.param(
            steps(UV, {"run": "python3 x.py"}), "j step 2: python3 x.py", id="python-after-setup"
        ),
    ],
)
def test_a_step_outside_the_pinned_python_is_found(workflow: dict[str, Any], finding: str) -> None:
    assert step_findings(workflow) == [finding]


def test_a_venv_made_before_setup_uv_runs_no_pinned_python() -> None:
    made = steps({"run": "uv venv v"}, UV, {"run": "v/bin/python -c 1"})
    assert step_findings(made) == ["j step 1: uv before setup-uv", "j step 3: v/bin/python -c 1"]


def test_a_venv_made_by_an_earlier_step_after_setup_uv_runs_the_pinned_python() -> None:
    assert step_findings(steps(UV, {"run": "uv venv v"}, {"run": "v/bin/python -c 1"})) == []


def test_uv_after_setup_uv_is_not_found() -> None:
    assert step_findings(steps(UV, {"run": "uv run --no-project x.py"})) == []


def test_setup_uv_in_another_case_sets_up_uv() -> None:
    assert step_findings(steps({"uses": f"Astral-SH/Setup-UV@{SHA}"}, {"run": "uv sync"})) == []


@pytest.mark.parametrize(
    "node",
    [
        pytest.param({"with": {"python-version": "3.13"}}, id="python-version"),
        pytest.param({"with": {"python-version-file": ".python-version"}}, id="a-version-file"),
        pytest.param({"with": {"Python-Version": "3.13"}}, id="another-case"),
        pytest.param([{"strategy": {"matrix": {"python-version": ["3.13"]}}}], id="in-a-matrix"),
    ],
)
def test_a_python_named_for_an_action_is_found(node: object) -> None:
    assert len(list(python_version_keys(node))) == 1


@pytest.mark.parametrize(
    ("text", "minor"),
    [
        pytest.param("test (py3.12)", "3.12", id="a-job-name"),
        pytest.param("coverage-python-3.12", "3.12", id="an-artifact-name"),
        pytest.param("python3.12 -m x", "3.12", id="an-interpreter"),
    ],
)
def test_a_minor_named_in_a_workflow_string_is_read(text: str, minor: str) -> None:
    assert NAMED_MINOR.findall(text) == [minor]


def test_every_key_and_string_of_a_workflow_is_read_and_nothing_else() -> None:
    workflow = {"jobs": {"a (py3.12)": {"steps": [{"name": "x", "timeout": 5}, "y"]}}, 1: None}
    assert list(strings(workflow)) == [
        "jobs",
        "a (py3.12)",
        "steps",
        "name",
        "x",
        "timeout",
        "y",
        "1",
    ]


def test_an_action_version_is_not_read_as_a_python_minor() -> None:
    assert NAMED_MINOR.findall("actions/checkout@abc # v7.0.1") == []


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("3.13\n", id="a-minor"),
        pytest.param("3.13.15", id="no-newline"),
        pytest.param("3.13.15\n3.12.14\n", id="two-versions"),
        pytest.param("# pin\n3.13.15\n", id="a-comment"),
        pytest.param("cpython-3.13.15\n", id="an-implementation-prefix"),
    ],
)
def test_a_python_version_file_holding_anything_but_one_exact_line_is_refused(text: str) -> None:
    with pytest.raises(AssertionError, match=r"^\.python-version holds "):
        exact_version(text)


def test_one_exact_line_is_read() -> None:
    assert exact_version("3.13.15\n") == (3, 13, 15)


AGREED: dict[str, Any] = {
    "project": {"requires-python": ">=3.13"},
    "tool": {"ruff": {"target-version": "py313"}, "mypy": {"python_version": "3.13"}},
}


def test_a_pyproject_naming_the_pinned_minor_everywhere_is_not_found() -> None:
    assert pyproject_findings("p", AGREED, 3, 13) == []


@pytest.mark.parametrize(
    ("project", "finding"),
    [
        pytest.param(
            {**AGREED, "project": {"requires-python": ">=3.12"}},
            "p: requires-python >=3.12",
            id="requires-python",
        ),
        pytest.param({**AGREED, "project": {}}, "p: requires-python None", id="no-requires-python"),
        pytest.param(
            {**AGREED, "tool": {**AGREED["tool"], "ruff": {"target-version": "py312"}}},
            "p: ruff target-version py312",
            id="ruff",
        ),
        pytest.param(
            {**AGREED, "tool": {**AGREED["tool"], "ruff": {}}},
            "p: ruff target-version None",
            id="ruff-with-no-target",
        ),
        pytest.param(
            {**AGREED, "tool": {**AGREED["tool"], "mypy": {"python_version": "3.12"}}},
            "p: mypy python_version 3.12",
            id="mypy",
        ),
    ],
)
def test_a_pyproject_naming_another_minor_is_found(project: dict[str, Any], finding: str) -> None:
    assert pyproject_findings("p", project, 3, 13) == [finding]
