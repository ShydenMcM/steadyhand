"""The workflows' tracing shell run by a real bash, as GitHub's runner starts it (#384).

On CI this is the runner image's bash 5.2; on the laptop macOS's bash 3.2. Each script below runs
every command it holds once, so every unit tree-sitter-bash finds must show in the trace (a unit
bash's DEBUG trap never fires for would read as unrun forever), and none may show that did not run.
The reader's logic, with no process, is unit-tested in ``tests/scripts/test_workflow_*.py``.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from workflow_coverage import TRACING_SHELL, read_trace, runner_argv, shell_units

BASH = shutil.which("bash")
SHA = "e" * 40

# Every construct the workflows' shell steps use, each run once (an `if` takes its true arm).
SCRIPTS = {
    "simple": "echo one\necho two\n",
    "continued": 'x=$(echo two \\\n  three)\necho "$x"\n',
    "if": 'if [ -n "x" ]; then\n  echo yes\nfi\n',
    "double-bracket": "[[ -n x ]]\n",
    "arithmetic": "n=0\n(( n += 1 ))\necho $n\n",
    "case": 'case "a" in\n  b) ;;\n  a) echo a ;;\nesac\n',
    "heredoc": "cat <<'H'\nbody\nH\n",
    "for": "for i in 1; do\n  echo $i\ndone\n",
    "c-for": "for ((i = 0; i < 1; i++)); do\n  echo $i\ndone\n",
    "while": "printf 'l\\n' | while read -r l; do\n  echo $l\ndone\n",
    "function": "f() {\n  echo in\n}\nf\n",
    "subshell": "( echo sub )\n",
    "pipeline": "echo a | tr a b\n",
    "mapfile": "mapfile -t files < <(printf 'a\\n')\necho \"${files[@]}\"\n",
    "read-process": "read -r digest _ < <(echo d x)\necho $digest\n",
    "export": "export A=1\nunset A\n",
    "assignments": "B=2 C=3\nD=4\n",
}
# An `if` whose test is false: its arm must not show in the trace.
ONE_UNRUN = 'if [ -z "x" ]; then\n  echo never\nfi\necho after\n'


def run_traced(tmp_path: Path, script: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    assert BASH is not None, "bash is not on the path"
    path = tmp_path / "step.sh"
    path.write_text(script, encoding="utf-8")
    argv = runner_argv(TRACING_SHELL, str(path))
    assert argv[0] == "bash"
    env = {
        **os.environ,
        "RUNNER_TEMP": str(tmp_path / "temp"),
        "GITHUB_JOB": "job",
        "GITHUB_ACTION": "__run",
        "GITHUB_SHA": SHA,
    }
    done = subprocess.run(  # noqa: S603 - bash, with the workflows' own shell line
        [BASH, *argv[1:]], env=env, capture_output=True, text=True, check=False
    )
    return done, tmp_path / "temp/workflow-trace/job/__run"


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_every_command_of_a_script_that_runs_them_all_is_traced(tmp_path: Path, name: str) -> None:
    script = SCRIPTS[name]
    done, trace_path = run_traced(tmp_path, script)
    assert done.returncode == 0, done.stderr
    trace = read_trace("job", "__run", trace_path.read_text(encoding="utf-8"))
    assert trace.sha == SHA
    assert trace.lines == len(script.splitlines())
    untraced = [
        unit
        for unit in shell_units(script)
        if not any(unit[0] <= hit <= unit[1] for hit in trace.traced)
    ]
    assert untraced == []


def test_the_arm_not_taken_is_not_traced(tmp_path: Path) -> None:
    done, trace_path = run_traced(tmp_path, ONE_UNRUN)
    assert done.returncode == 0, done.stderr
    assert read_trace("job", "__run", trace_path.read_text(encoding="utf-8")).traced == frozenset(
        {1, 4}
    )


def test_a_failing_command_still_fails_the_step_and_leaves_its_trace(tmp_path: Path) -> None:
    done, trace_path = run_traced(tmp_path, "echo a\nfalse\necho never\n")
    assert done.returncode == 1
    assert done.stdout == "a\n"
    assert read_trace("job", "__run", trace_path.read_text(encoding="utf-8")).traced == frozenset(
        {1, 2}
    )


def test_a_pipeline_failure_still_fails_the_step(tmp_path: Path) -> None:
    done, _ = run_traced(tmp_path, "false | cat\necho never\n")
    assert done.returncode == 1
    assert done.stdout == ""


def test_an_exit_code_is_the_steps(tmp_path: Path) -> None:
    done, _ = run_traced(tmp_path, "exit 3\n")
    assert done.returncode == 3


def test_the_trace_holds_no_command_text(tmp_path: Path) -> None:
    secret = "s3cr3t-value"  # noqa: S105 - a stand-in the trace must not show
    done, trace_path = run_traced(tmp_path, f'TOKEN="{secret}"\necho "$TOKEN" > /dev/null\n')
    assert done.returncode == 0, done.stderr
    assert secret not in trace_path.read_text(encoding="utf-8")
