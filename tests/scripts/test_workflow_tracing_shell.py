"""The tracing shell every workflow sets, and how GitHub's runner reads it (#384).

The runner takes a custom shell's first word as the program, fills ``{0}`` with string.Format and
splits the rest by .NET's argument rules. The real bash run is in
``tests/integration/scripts/test_workflow_trace_bash.py``.
"""

from pathlib import Path

import pytest

from workflow_coverage import TRACING_SHELL, WorkflowError, require_traced, runner_argv

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))


def traced(shell: str) -> str:
    indented = shell.replace("'", "''")
    return f"defaults:\n  run:\n    shell: '{indented}'\njobs:\n  a:\n    steps: []\n"


@pytest.mark.parametrize("path", WORKFLOWS, ids=[path.name for path in WORKFLOWS])
def test_every_workflow_sets_the_tracing_shell(path: Path) -> None:
    require_traced(path.read_text(encoding="utf-8"))


def test_the_workflows_are_the_four_measured_on_2026_10_22() -> None:
    assert [path.name for path in WORKFLOWS] == [
        "ci.yml",
        "mutations.yml",
        "record-floors.yml",
        "yahoo-shape.yml",
    ]


def test_the_tracing_shell_is_accepted_written_any_way_yaml_allows() -> None:
    require_traced(traced(TRACING_SHELL))


@pytest.mark.parametrize(
    "text",
    [
        "jobs:\n  a:\n    steps: []\n",
        "defaults: []\njobs:\n  a:\n    steps: []\n",
        "defaults:\n  run: []\njobs:\n  a:\n    steps: []\n",
        "defaults:\n  run:\n    shell: [bash]\njobs:\n  a:\n    steps: []\n",
        traced(TRACING_SHELL.replace("set -T; ", "")),
        traced("bash --noprofile --norc -eo pipefail {0}"),
    ],
    ids=[
        "no-defaults",
        "defaults-a-list",
        "run-a-list",
        "shell-a-list",
        "no-functrace",
        "plain-bash",
    ],
)
def test_a_workflow_without_the_tracing_shell_is_refused(text: str) -> None:
    with pytest.raises(WorkflowError, match="does not set the tracing shell"):
        require_traced(text)


def test_the_runner_starts_bash_with_the_prelude_and_the_script() -> None:
    argv = runner_argv(TRACING_SHELL, "/tmp/s.sh")  # noqa: S108 - a path the test only names
    assert argv[:6] == ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c"]
    assert argv[7:] == ["/tmp/s.sh"]  # noqa: S108
    prelude = argv[6]
    assert prelude.startswith('__wt_t="$RUNNER_TEMP/workflow-trace/$GITHUB_JOB/$GITHUB_ACTION"; ')
    assert prelude.endswith('; . "$0"')
    assert 'trap \'if [ "$BASH_SOURCE" = "$__wt_s" ]; then echo "$LINENO"' in prelude


@pytest.mark.parametrize(
    ("arguments", "words"),
    [
        ('a "b c" d', ["a", "b c", "d"]),
        ('a\\"b', ['a"b']),
        ('"a\\\\" b', ["a\\", "b"]),
        ('a\\\\\\"b', ['a\\"b']),
        ("a\\b", ["a\\b"]),
        ('a  ""  b', ["a", "", "b"]),
        ("a\tb", ["a", "b"]),
        ("", []),
    ],
    ids=[
        "quotes",
        "escaped-quote",
        "even-backslashes",
        "odd-backslashes",
        "lone-backslash",
        "empty",
        "tab",
        "none",
    ],
)
def test_the_runner_splits_arguments_by_dotnet_rules(arguments: str, words: list[str]) -> None:
    assert runner_argv(f"prog {arguments}", "x") == ["prog", *words]


def test_the_script_path_fills_every_placeholder() -> None:
    assert runner_argv("prog {0} -x {0}", "/s") == ["prog", "/s", "-x", "/s"]


@pytest.mark.parametrize(
    "shell", ["prog ${HOME} {0}", "prog a} {0}", "prog {1}"], ids=["open", "close", "other"]
)
def test_a_brace_string_format_would_break_is_refused(shell: str) -> None:
    with pytest.raises(WorkflowError, match="no brace but"):
        runner_argv(shell, "/s")
