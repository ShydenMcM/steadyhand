"""The mutations runner (#288): a story's planted mutations, each applied to a clean checkout and
judged against the suite that should catch it, in CI.

A unit test starts no process (#286): here pytest is stood in by a runner that answers each call.
The real pytest's output is read in ``tests/integration/scripts/test_run_mutations_pytest.py``;
vitest's JSON report is read here from reports shaped as vitest 4 writes them."""

import json
import runpy
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from run_mutations import (
    NON_UNIT_TEST,
    SUITES,
    Mutation,
    MutationError,
    Outcome,
    Plan,
    Row,
    apply,
    command,
    judge,
    load,
    main,
    parse_outcome,
    parse_vitest,
    plan_for,
    plan_main,
    render,
    run_all,
    run_process,
    run_vitest,
    runner_for,
    vitest_command,
)
from stood_in_git import FakeGit

from ci_scope import Change

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/run_mutations.py"
TARGET = "pkg/mod.py"
TESTS = "tests/integration/test_mod.py"
SOURCE = "def f():\n    return 1\n"
VALID = f"""
[[mutation]]
id = "M1"
why = "f returns 2"
path = "{TARGET}"
old = "    return 1"
new = "    return 2"
suite = "integration"
tests = ["{TESTS}"]
expect = "red"
red = ["{TESTS}::test_f"]
"""


def mutation(**changes: object) -> Mutation:
    fields: dict[str, object] = {
        "id": "M1",
        "why": "f returns 2",
        "path": TARGET,
        "old": "    return 1",
        "new": "    return 2",
        "suite": "integration",
        "tests": (TESTS,),
        "expect": "red",
        "red": (f"{TESTS}::test_f",),
    }
    return Mutation(**(fields | changes))  # type: ignore[arg-type]


def outcome(returncode: int = 0, *failed: str) -> Outcome:
    return Outcome(returncode, frozenset(failed), "1 passed")


def with_entry(**fields: str) -> str:
    """VALID with each named key replaced by its raw TOML value, or removed when it is empty."""
    lines = []
    for line in VALID.splitlines():
        key = line.split(" = ")[0]
        if key in fields:
            if fields[key]:
                lines.append(f"{key} = {fields[key]}")
            continue
        lines.append(line)
    return "\n".join(lines)


# --- reading a mutation file ---------------------------------------------------------------------


def test_a_valid_file_reads_as_its_mutations() -> None:
    assert load(VALID, "m.toml") == [mutation()]


def test_an_anchor_spanning_lines_reads_byte_for_byte_from_a_literal_string() -> None:
    text = with_entry(old="'''\ndef f():\n    return 1'''", new="'''\ndef f():\n    return 2'''")
    [read] = load(text, "m.toml")
    assert (read.old, read.new) == ("def f():\n    return 1", "def f():\n    return 2")


def test_the_suites_are_the_non_unit_ones() -> None:
    assert SUITES == (
        "guards",
        "integration",
        "properties",
        "logs",
        "extension-guards",
        "extension-integration",
    )


@pytest.mark.parametrize("key", ["id", "why", "path", "old", "new", "suite", "tests", "expect"])
def test_a_missing_key_is_refused_by_name(key: str) -> None:
    text = "\n".join(line for line in VALID.splitlines() if not line.startswith(f"{key} = "))
    with pytest.raises(MutationError, match=f"missing key '{key}'"):
        load(text, "m.toml")


def test_an_unknown_key_is_refused_by_name() -> None:
    with pytest.raises(MutationError, match="unknown key 'expected'"):
        load(VALID + 'expected = "red"\n', "m.toml")


@pytest.mark.parametrize("suite", ['"unit"', '"perf"', '"Integration"'])
def test_a_suite_outside_the_non_unit_ones_is_refused(suite: str) -> None:
    with pytest.raises(MutationError, match="suite"):
        load(with_entry(suite=suite), "m.toml")


@pytest.mark.parametrize("expect", ['"RED"', '"caught"', '""'])
def test_an_expectation_other_than_red_or_green_is_refused(expect: str) -> None:
    with pytest.raises(MutationError, match="expect"):
        load(with_entry(expect=expect), "m.toml")


def test_a_red_expectation_names_at_least_one_test() -> None:
    with pytest.raises(MutationError, match="names no test"):
        load(with_entry(red="[]"), "m.toml")


def test_a_red_expectation_without_its_red_list_is_refused() -> None:
    with pytest.raises(MutationError, match="names no test"):
        load(with_entry(red=""), "m.toml")


def test_a_green_expectation_names_no_red_test() -> None:
    with pytest.raises(MutationError, match="green"):
        load(with_entry(expect='"green"'), "m.toml")


def test_a_green_expectation_reads_with_an_empty_red_list() -> None:
    [read] = load(with_entry(expect='"green"', red=""), "m.toml")
    assert (read.expect, read.red) == ("green", ())


def test_a_red_test_outside_the_target_files_is_refused() -> None:
    with pytest.raises(MutationError, match="not in its target files"):
        load(with_entry(red='["tests/integration/test_other.py::test_f"]'), "m.toml")


def test_a_red_name_without_a_test_part_is_refused() -> None:
    with pytest.raises(MutationError, match="not in its target files"):
        load(with_entry(red=f'["{TESTS}"]'), "m.toml")


def test_a_mutation_that_changes_nothing_is_refused() -> None:
    with pytest.raises(MutationError, match="changes nothing"):
        load(with_entry(new='"    return 1"'), "m.toml")


@pytest.mark.parametrize(
    ("key", "value"),
    [("tests", f'"{TESTS}"'), ("tests", "[1]"), ("red", '"x"'), ("id", "1"), ("old", "[]")],
)
def test_a_value_of_the_wrong_type_is_refused(key: str, value: str) -> None:
    with pytest.raises(MutationError, match=key):
        load(with_entry(**{key: value}), "m.toml")


def test_no_target_files_is_refused() -> None:
    with pytest.raises(MutationError, match="tests"):
        load(with_entry(tests="[]"), "m.toml")


def test_two_mutations_with_one_id_are_refused() -> None:
    with pytest.raises(MutationError, match="M1 twice"):
        load(VALID + VALID, "m.toml")


def test_a_file_with_no_mutation_is_refused() -> None:
    with pytest.raises(MutationError, match="no mutation"):
        load("", "m.toml")


def test_a_file_that_is_not_toml_is_refused_with_its_name() -> None:
    with pytest.raises(MutationError, match=r"m\.toml"):
        load("[[mutation]\n", "m.toml")


@pytest.mark.parametrize("value", ['["x"]', "1"], ids=["list-of-strings", "number"])
def test_mutation_entries_that_are_not_tables_are_refused(value: str) -> None:
    with pytest.raises(MutationError, match="table"):
        load(f"mutation = {value}\n", "m.toml")


def test_a_top_level_key_other_than_mutation_is_refused() -> None:
    with pytest.raises(MutationError, match="unknown key 'mutations'"):
        load("mutations = 1\n" + VALID, "m.toml")


# --- applying one --------------------------------------------------------------------------------


def test_an_anchor_found_once_is_replaced_and_the_original_returned(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / TARGET).write_text(SOURCE)
    original = apply(tmp_path, mutation())
    assert original == SOURCE.encode()
    assert (tmp_path / TARGET).read_text() == "def f():\n    return 2\n"


@pytest.mark.parametrize(
    ("source", "count"), [("x = 0\n", 0), (SOURCE + SOURCE, 2)], ids=["absent", "twice"]
)
def test_an_anchor_found_other_than_once_is_refused_and_the_file_left(
    tmp_path: Path, source: str, count: int
) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / TARGET).write_text(source)
    with pytest.raises(MutationError, match=f"M1: the anchor matches {count} times"):
        apply(tmp_path, mutation())
    assert (tmp_path / TARGET).read_text() == source


def test_a_target_file_that_is_missing_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MutationError, match=r"M1: cannot read pkg/mod\.py"):
        apply(tmp_path, mutation())


# --- reading pytest's verdict --------------------------------------------------------------------


def test_a_clean_run_reads_as_green_with_its_totals() -> None:
    assert parse_outcome(0, "...\n3 passed in 0.12s\n") == Outcome(0, frozenset(), "3 passed")


def test_a_red_run_reads_its_failed_and_errored_tests() -> None:
    output = (
        "FAILED tests/a.py::test_x - AssertionError: no\n"
        "ERROR tests/a.py::test_y[BBRI] - RuntimeError\n"
        "========= 1 failed, 2 passed, 1 error in 1.50s =========\n"
    )
    assert parse_outcome(1, output) == Outcome(
        1,
        frozenset({"tests/a.py::test_x", "tests/a.py::test_y[BBRI]"}),
        "1 failed, 2 passed, 1 error",
    )


def test_the_last_totals_line_is_the_one_read() -> None:
    output = "4 passed in 0.1s\nFAILED t.py::test_a - x\n1 failed, 3 passed in 0.2s\n"
    assert parse_outcome(1, output).totals == "1 failed, 3 passed"


def test_a_red_run_naming_no_test_is_refused() -> None:
    with pytest.raises(MutationError, match="names no failed test"):
        parse_outcome(1, "1 failed in 0.1s\n")


@pytest.mark.parametrize(
    ("returncode", "meaning"),
    [
        (2, "interrupted"),
        (3, "internal error"),
        (4, "usage error"),
        (5, "no tests ran"),
        (-9, "exit -9"),
    ],
)
def test_a_run_that_did_not_finish_is_refused_by_meaning(returncode: int, meaning: str) -> None:
    with pytest.raises(MutationError, match=meaning):
        parse_outcome(returncode, "1 failed in 0.1s\n")


def test_a_run_with_no_totals_line_is_refused_with_its_tail() -> None:
    with pytest.raises(MutationError, match=r"no totals line.*the tail"):
        parse_outcome(0, "the tail")


def test_a_green_run_that_names_a_failed_test_is_refused() -> None:
    with pytest.raises(MutationError, match="exit 0"):
        parse_outcome(0, "FAILED t.py::test_a - x\n1 passed in 0.1s\n")


# --- judging one ---------------------------------------------------------------------------------


def test_a_predicted_red_that_fails_its_named_test_is_as_predicted() -> None:
    assert judge(mutation(), outcome(1, f"{TESTS}::test_f")) is None


def test_a_named_test_failing_under_a_parameter_counts() -> None:
    assert judge(mutation(), outcome(1, f"{TESTS}::test_f[BBRI]")) is None


def test_a_longer_name_sharing_the_prefix_does_not_count() -> None:
    assert judge(mutation(), outcome(1, f"{TESTS}::test_f_other")) == (
        f"named tests stayed green: {TESTS}::test_f; red instead: {TESTS}::test_f_other"
    )


def test_a_predicted_red_that_stays_green_is_not_as_predicted() -> None:
    assert judge(mutation(), outcome(0)) == "not caught: every test passed"


def test_a_predicted_green_that_passes_is_as_predicted() -> None:
    assert judge(mutation(expect="green", red=()), outcome(0)) is None


def test_a_predicted_green_that_fails_is_not_as_predicted() -> None:
    assert judge(mutation(expect="green", red=()), outcome(1, "t.py::test_b", "t.py::test_a")) == (
        "red: t.py::test_a, t.py::test_b"
    )


# --- running a file ------------------------------------------------------------------------------


class StoodIn:
    """pytest stood in: answers each run from *answers* by the target file's text, and keeps the
    suite, target files and mutated text of every call."""

    def __init__(self, root: Path, answers: dict[str, tuple[int, str]]) -> None:
        self.root = root
        self.answers = answers
        self.calls: list[tuple[str, tuple[str, ...], str]] = []

    def __call__(self, suite: str, tests: tuple[str, ...]) -> tuple[int, str]:
        text = (self.root / TARGET).read_text()
        self.calls.append((suite, tests, text))
        return self.answers[text]


CLEAN = (0, "1 passed in 0.1s\n")
CAUGHT = (1, f"FAILED {TESTS}::test_f - assert 2 == 1\n1 failed in 0.1s\n")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / TARGET).write_text(SOURCE)
    return tmp_path


def test_each_target_runs_clean_first_then_once_per_mutation(repo: Path) -> None:
    runner = StoodIn(repo, {SOURCE: CLEAN, "def f():\n    return 2\n": CAUGHT})
    rows = run_all(repo, [mutation()], runner)
    assert runner.calls == [
        ("integration", (TESTS,), SOURCE),
        ("integration", (TESTS,), "def f():\n    return 2\n"),
    ]
    assert rows == [
        Row("baseline", "integration", "green", "green", "1 passed", ok=True),
        Row("M1", "integration", "red", "red", "1 failed", ok=True),
    ]
    assert (repo / TARGET).read_text() == SOURCE


def test_mutations_sharing_a_target_share_its_clean_run(repo: Path) -> None:
    second = mutation(id="M2", new="    return 3")
    caught_3 = (1, f"FAILED {TESTS}::test_f - assert 3 == 1\n1 failed in 0.1s\n")
    runner = StoodIn(
        repo,
        {SOURCE: CLEAN, "def f():\n    return 2\n": CAUGHT, "def f():\n    return 3\n": caught_3},
    )
    rows = run_all(repo, [mutation(), second], runner)
    assert [row.id for row in rows] == ["baseline", "M1", "M2"]
    assert len(runner.calls) == 3


def test_a_target_red_before_any_mutation_fails_and_runs_none_of_its_mutations(repo: Path) -> None:
    runner = StoodIn(repo, {SOURCE: CAUGHT})
    rows = run_all(repo, [mutation()], runner)
    assert len(runner.calls) == 1
    assert rows == [
        Row(
            "baseline",
            "integration",
            "green",
            "red",
            f"red before any mutation: {TESTS}::test_f",
            ok=False,
        ),
        Row(
            "M1", "integration", "red", "not run", "its target is red before any mutation", ok=False
        ),
    ]


def test_a_clean_run_that_cannot_be_read_fails_and_runs_none_of_its_mutations(repo: Path) -> None:
    runner = StoodIn(repo, {SOURCE: (5, "no tests ran in 0.1s\n")})
    rows = run_all(repo, [mutation()], runner)
    assert len(runner.calls) == 1
    assert rows == [
        Row(
            "baseline",
            "integration",
            "green",
            "not read",
            "exit 5 (no tests ran): no tests ran in 0.1s\n",
            ok=False,
        ),
        Row(
            "M1", "integration", "red", "not run", "its target is red before any mutation", ok=False
        ),
    ]


def test_a_mutation_not_as_predicted_fails_its_row(repo: Path) -> None:
    runner = StoodIn(repo, {SOURCE: CLEAN, "def f():\n    return 2\n": CLEAN})
    rows = run_all(repo, [mutation()], runner)
    assert rows[1] == Row(
        "M1", "integration", "red", "green", "not caught: every test passed", ok=False
    )


def test_a_broken_anchor_fails_its_row_and_the_rest_still_run(repo: Path) -> None:
    broken = mutation(id="M0", old="    return 9")
    runner = StoodIn(repo, {SOURCE: CLEAN, "def f():\n    return 2\n": CAUGHT})
    rows = run_all(repo, [broken, mutation()], runner)
    assert rows[1] == Row(
        "M0", "integration", "red", "not run", "M0: the anchor matches 0 times", ok=False
    )
    assert rows[2].ok


def test_an_unreadable_run_fails_its_row(repo: Path) -> None:
    runner = StoodIn(repo, {SOURCE: CLEAN, "def f():\n    return 2\n": (2, "1 error in 0.1s\n")})
    rows = run_all(repo, [mutation()], runner)
    assert rows[1] == Row(
        "M1", "integration", "red", "not read", "exit 2 (interrupted): 1 error in 0.1s\n", ok=False
    )


def test_the_file_is_put_back_when_the_run_raises(repo: Path) -> None:
    def runner(_suite: str, _tests: tuple[str, ...]) -> tuple[int, str]:
        if (repo / TARGET).read_text() != SOURCE:
            raise KeyboardInterrupt
        return CLEAN

    with pytest.raises(KeyboardInterrupt):
        run_all(repo, [mutation()], runner)
    assert (repo / TARGET).read_text() == SOURCE


# --- the report ----------------------------------------------------------------------------------


def test_the_report_is_a_table_and_a_count() -> None:
    rows = [
        Row("baseline", "integration", "green", "green", "1 passed", ok=True),
        Row("M1", "integration", "red", "green", "not caught | x", ok=False),
    ]
    assert render(rows) == (
        "| Mutation | Suite | Expected | Result | As predicted | Detail |\n"
        "|---|---|---|---|---|---|\n"
        "| baseline | integration | green | green | yes | 1 passed |\n"
        "| M1 | integration | red | green | **NO** | not caught \\| x |\n"
        "\n**1 of 2 as predicted.**\n"
    )


def test_a_detail_spanning_lines_stays_on_its_row() -> None:
    row = Row("M1", "integration", "red", "not read", "a\nb\n", ok=False)
    assert "| a b |" in render([row])


# --- the extension's suites ---------------------------------------------------------------------

EXT_FILE = "extension/tests/guards/a.test.ts"
EXT_RED = f"{EXT_FILE}::a group the test"


def ext_mutation(**changes: object) -> Mutation:
    fields: dict[str, object] = {
        "suite": "extension-guards",
        "tests": (EXT_FILE,),
        "red": (EXT_RED,),
    }
    return mutation(**(fields | changes))


def test_an_extension_suite_reads_with_its_workspace_files() -> None:
    text = with_entry(
        suite='"extension-integration"',
        tests=f'["{EXT_FILE}"]',
        red=f'["{EXT_RED}"]',
    )
    [read] = load(text, "m.toml")
    assert (read.suite, read.tests, read.red) == ("extension-integration", (EXT_FILE,), (EXT_RED,))


def test_an_extension_suite_with_a_file_outside_the_workspace_is_refused() -> None:
    with pytest.raises(MutationError, match="extension-guards runs files under extension/ only"):
        load(with_entry(suite='"extension-guards"'), "m.toml")


def test_a_python_suite_with_a_workspace_file_is_refused() -> None:
    with pytest.raises(MutationError, match="integration runs no file under extension/"):
        load(with_entry(tests=f'["{EXT_FILE}"]', red=f'["{EXT_RED}"]'), "m.toml")


@pytest.mark.parametrize(
    ("suite", "project"),
    [("extension-guards", "guards"), ("extension-integration", "integration")],
)
def test_the_vitest_command_runs_the_project_s_files_with_a_json_report(
    suite: str, project: str
) -> None:
    assert vitest_command(
        suite, (EXT_FILE, "extension/tests/guards/b.test.ts"), Path("/r.json")
    ) == [
        "npm",
        "exec",
        "--no",
        "--",
        "vitest",
        "run",
        "--project",
        project,
        "--reporter=json",
        "--outputFile=/r.json",
        "tests/guards/a.test.ts",
        "tests/guards/b.test.ts",
    ]


def report(*files: dict[str, object], passed: int = 1, failed: int = 0, **counts: int) -> str:
    """A vitest JSON report holding *files*, shaped as vitest 4 writes it."""
    totals = {
        "numPassedTests": passed,
        "numFailedTests": failed,
        "numPendingTests": 0,
        "numTodoTests": 0,
    } | counts
    totals["numTotalTests"] = counts.get("numTotalTests", sum(totals.values()))
    return json.dumps(totals | {"success": failed == 0, "testResults": list(files)})


def file_result(
    root: Path, status: str = "passed", message: str = "", **tests: str
) -> dict[str, object]:
    return {
        "name": str(root / EXT_FILE),
        "status": status,
        "message": message,
        "assertionResults": [
            {"fullName": name, "status": state, "title": name.split()[-1]}
            for name, state in tests.items()
        ],
    }


def test_a_clean_vitest_run_reads_as_green_with_its_totals(tmp_path: Path) -> None:
    text = report(file_result(tmp_path, **{"a group the test": "passed"}), passed=1)
    assert parse_vitest(0, text, tmp_path) == Outcome(0, frozenset(), "1 passed")


def test_a_red_vitest_run_names_each_failed_test_by_file_and_full_name(tmp_path: Path) -> None:
    result = file_result(
        tmp_path, "failed", **{"a group the test": "failed", "other": "passed", "x": "skipped"}
    )
    text = report(result, passed=1, failed=1, numPendingTests=1, numTodoTests=2)
    assert parse_vitest(1, text, tmp_path) == Outcome(
        1, frozenset({EXT_RED}), "1 failed, 1 passed, 1 skipped, 2 todo"
    )


def test_a_file_that_failed_to_load_is_refused_by_name(tmp_path: Path) -> None:
    text = report(file_result(tmp_path, "failed", "SyntaxError: x"), passed=0, numTotalTests=1)
    with pytest.raises(MutationError, match=rf"{EXT_FILE} failed to load: SyntaxError: x"):
        parse_vitest(1, text, tmp_path)


def test_a_vitest_run_of_no_test_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MutationError, match="no tests ran"):
        parse_vitest(0, report(passed=0), tmp_path)


def test_output_that_is_not_a_report_is_refused_with_its_tail(tmp_path: Path) -> None:
    with pytest.raises(MutationError, match="no vitest report; the tail: npm error"):
        parse_vitest(1, "npm error could not determine executable", tmp_path)


@pytest.mark.parametrize(
    "text",
    ["[]", '{"numTotalTests": 1}', '{"numTotalTests": 1, "testResults": [{"name": 1}]}'],
    ids=["not-an-object", "no-results", "a-name-not-a-path"],
)
def test_a_report_missing_its_fields_is_refused(tmp_path: Path, text: str) -> None:
    with pytest.raises(MutationError, match="unreadable vitest report"):
        parse_vitest(1, text, tmp_path)


def test_a_report_naming_a_file_outside_the_checkout_is_refused(tmp_path: Path) -> None:
    text = report(file_result(tmp_path / "elsewhere", t="passed"))
    with pytest.raises(MutationError, match="unreadable vitest report"):
        parse_vitest(0, text, tmp_path / "root")


@pytest.mark.parametrize(
    ("returncode", "failed", "meaning"),
    [
        (2, 0, r"exit 2 \(killed or unknown\)"),
        (1, 0, "exit 1 but names no failed test"),
        (0, 1, "exit 0 but names failed tests"),
    ],
    ids=["unknown-exit", "red-naming-none", "green-naming-some"],
)
def test_a_vitest_exit_that_disagrees_with_its_report_is_refused(
    tmp_path: Path, returncode: int, failed: int, meaning: str
) -> None:
    state = "failed" if failed else "passed"
    text = report(
        file_result(tmp_path, **{"a group the test": state}), passed=1 - failed, failed=failed
    )
    with pytest.raises(MutationError, match=meaning):
        parse_vitest(returncode, text, tmp_path)


def test_an_extension_mutation_is_judged_from_its_report(repo: Path) -> None:
    clean = report(file_result(repo, **{"a group the test": "passed"}))
    caught = report(
        file_result(repo, "failed", **{"a group the test": "failed"}), passed=0, failed=1
    )
    runner = StoodIn(repo, {SOURCE: (0, clean), "def f():\n    return 2\n": (1, caught)})
    rows = run_all(repo, [ext_mutation()], runner)
    assert rows == [
        Row("baseline", "extension-guards", "green", "green", "1 passed", ok=True),
        Row("M1", "extension-guards", "red", "red", "1 failed", ok=True),
    ]


def stand_in_processes(monkeypatch: pytest.MonkeyPatch, write: str | None) -> list[dict[str, Any]]:
    """``subprocess.run`` stood in: keeps each call, and writes *write* to the report the call
    names in its ``--outputFile`` flag when it is given."""
    seen: list[dict[str, Any]] = []

    def stood_in(args: list[str], **kwargs: object) -> object:
        seen.append({"args": args, **kwargs})
        if write is not None:
            [flag] = [arg for arg in args if arg.startswith("--outputFile=")]
            Path(flag.removeprefix("--outputFile=")).write_text(write)
        return type("Done", (), {"returncode": 1, "stdout": "out\n", "stderr": "err\n"})()

    monkeypatch.setattr(subprocess, "run", stood_in)
    return seen


def test_a_vitest_run_answers_with_the_report_it_wrote(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen = stand_in_processes(monkeypatch, '{"a": 1}')
    assert run_vitest("extension-integration", (EXT_FILE,), tmp_path) == (1, '{"a": 1}')
    [call] = seen
    assert call["cwd"] == tmp_path / "extension"
    assert call["args"][:8] == vitest_command("extension-integration", (), Path())[:8]


def test_a_vitest_run_that_wrote_no_report_answers_with_its_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stand_in_processes(monkeypatch, None)
    assert run_vitest("extension-guards", (EXT_FILE,), tmp_path) == (1, "out\nerr\n")


@pytest.mark.parametrize(
    ("suite", "where", "first"),
    [("integration", "", "uv"), ("extension-guards", "extension", "npm")],
    ids=["python", "extension"],
)
def test_the_runner_starts_each_suite_s_tool_in_its_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, suite: str, where: str, first: str
) -> None:
    seen = stand_in_processes(monkeypatch, None)
    runner_for(tmp_path)(suite, ("x",))
    [call] = seen
    assert (call["args"][0], call["cwd"]) == (first, tmp_path / where)


# --- the plan: which mutation files a pull request must run --------------------------------------


@pytest.mark.parametrize(
    ("path", "non_unit"),
    [
        ("tests/guards/test_a.py", True),
        ("tests/integration/cli/test_b_golden.py", True),
        ("tests/properties/test_c.py", True),
        ("tests/logs/test_state_trails.py", True),
        ("tests/logs/cli/test_paper_run_trails.py", True),
        ("tests/logs/trail_world.py", False),
        ("tests/logsx/test_e.py", False),
        ("extension/tests/guards/core-rules.test.ts", True),
        ("extension/tests/integration/build.test.ts", True),
        ("tests/engine/test_d.py", False),
        ("tests/guards/population.py", False),
        ("tests/integration/conftest.py", False),
        ("extension/tests/population.test.ts", False),
        ("extension/tests/lib/source.ts", False),
        ("packages/steadyhand/src/steadyhand/risk.py", False),
    ],
    ids=str,
)
def test_a_non_unit_test_file_is_known_by_its_path(path: str, *, non_unit: bool) -> None:
    assert bool(NON_UNIT_TEST.fullmatch(path)) is non_unit


GUARD = "tests/guards/test_a.py"
COVERING = f"""
[[mutation]]
id = "G1"
why = "w"
path = "pkg/mod.py"
old = "a"
new = "b"
suite = "guards"
tests = ["{GUARD}"]
expect = "green"
"""


def reader(files: dict[str, str]) -> Callable[[str], str]:
    return files.__getitem__


def test_a_changed_test_its_mutation_file_targets_is_covered_and_the_file_run() -> None:
    changed = [Change(GUARD, removed=False), Change("mutations/9.toml", removed=False)]
    assert plan_for(changed, reader({"mutations/9.toml": COVERING})) == Plan(
        files=("mutations/9.toml",), changed_tests=(GUARD,), uncovered=(), judged=2
    )


def test_a_changed_test_no_mutation_file_targets_is_uncovered() -> None:
    changed = [
        Change(GUARD, removed=False),
        Change("tests/guards/test_b.py", removed=False),
        Change("mutations/9.toml", removed=False),
    ]
    found = plan_for(changed, reader({"mutations/9.toml": COVERING}))
    assert found.uncovered == ("tests/guards/test_b.py",)


def test_a_removed_test_and_a_removed_mutation_file_ask_for_nothing() -> None:
    changed = [Change(GUARD, removed=True), Change("mutations/9.toml", removed=True)]
    assert plan_for(changed, reader({})) == Plan(files=(), changed_tests=(), uncovered=(), judged=2)


def test_a_mutation_file_that_does_not_load_is_refused() -> None:
    with pytest.raises(MutationError, match=r"mutations/9\.toml: no mutation"):
        plan_for([Change("mutations/9.toml", removed=False)], reader({"mutations/9.toml": ""}))


def plan_env(tmp_path: Path, **extra: str) -> dict[str, str]:
    return {"GITHUB_OUTPUT": str(tmp_path / "out")} | extra


def test_a_pull_request_writes_its_mutation_files_and_says_what_it_judged(
    tmp_path: Path, fake_git: FakeGit, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "mutations").mkdir()
    (tmp_path / "mutations/9.toml").write_text(COVERING)
    fake_git.stdout = f"M\0{GUARD}\0A\0mutations/9.toml\0M\0README.md\0".encode()
    assert plan_main(["pull_request"], plan_env(tmp_path), tmp_path) == 0
    assert fake_git.called_in(tmp_path, "diff", "--name-status", "-z", "-M", "HEAD^1", "HEAD")
    assert (tmp_path / "mutation-files.txt").read_text() == "mutations/9.toml\n"
    assert (tmp_path / "out").read_text() == "run=true\n"
    assert capsys.readouterr().out == (
        "mutations plan: 3 paths judged, 1 non-unit test file changed, 1 mutation file to run\n"
    )


def test_a_pull_request_with_nothing_to_run_passes_saying_so(
    tmp_path: Path, fake_git: FakeGit, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_git.stdout = b"M\0README.md\0"
    assert plan_main(["pull_request"], plan_env(tmp_path), tmp_path) == 0
    assert (tmp_path / "mutation-files.txt").read_text() == ""
    assert (tmp_path / "out").read_text() == "run=false\n"
    assert capsys.readouterr().out == (
        "mutations plan: 1 path judged, 0 non-unit test files changed, 0 mutation files to run\n"
    )


def test_a_pull_request_changing_an_uncovered_test_fails_naming_it(
    tmp_path: Path, fake_git: FakeGit, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_git.stdout = f"M\0{GUARD}\0".encode()
    assert plan_main(["pull_request"], plan_env(tmp_path), tmp_path) == 1
    assert capsys.readouterr().out.endswith(
        f"no mutation file in this pull request targets {GUARD}: add one under mutations/\n"
    )
    assert not (tmp_path / "out").exists()


def test_a_diff_that_cannot_be_computed_fails(
    tmp_path: Path, fake_git: FakeGit, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_git.returncode = 128
    fake_git.stderr = b"fatal: bad revision"
    assert plan_main(["pull_request"], plan_env(tmp_path), tmp_path) == 1
    assert "fatal: bad revision" in capsys.readouterr().out


def test_a_changed_mutation_file_that_cannot_be_read_fails(
    tmp_path: Path, fake_git: FakeGit, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_git.stdout = b"A\0mutations/9.toml\0"
    assert plan_main(["pull_request"], plan_env(tmp_path), tmp_path) == 1
    assert "cannot read mutations/9.toml" in capsys.readouterr().out


def test_a_dispatch_runs_the_one_file_it_names(tmp_path: Path) -> None:
    env = plan_env(tmp_path, FILE="mutations/9.toml")
    assert plan_main(["workflow_dispatch"], env, tmp_path) == 0
    assert (tmp_path / "mutation-files.txt").read_text() == "mutations/9.toml\n"
    assert (tmp_path / "out").read_text() == "run=true\n"


@pytest.mark.parametrize("name", ["", "pyproject.toml"], ids=["none", "outside"])
def test_a_dispatch_naming_no_mutation_file_is_a_usage_error(
    tmp_path: Path, name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert plan_main(["workflow_dispatch"], plan_env(tmp_path, FILE=name), tmp_path) == 2
    assert "is not a mutations/<name>.toml file" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "env"),
    [(["push"], {"GITHUB_OUTPUT": "o"}), ([], {"GITHUB_OUTPUT": "o"}), (["pull_request"], {})],
    ids=["another-event", "no-event", "no-output-file"],
)
def test_a_plan_without_its_event_or_output_is_a_usage_error(
    tmp_path: Path, argv: list[str], env: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert plan_main(argv, env, tmp_path) == 2
    assert "usage:" in capsys.readouterr().err


def test_the_script_plans_from_the_working_directory_when_asked(
    tmp_path: Path, fake_git: FakeGit, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_git.stdout = b"M\0README.md\0"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--plan", "pull_request"])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exited.value.code == 0
    assert (tmp_path / "out").read_text() == "run=false\n"


# --- the command line ----------------------------------------------------------------------------


def test_the_command_runs_the_suite_s_target_files_as_ci_runs_that_suite() -> None:
    assert command("guards", ("tests/guards/test_a.py",)) == [
        "uv",
        "run",
        "--locked",
        "pytest",
        "-W",
        "error",
        "--suite",
        "guards",
        "-p",
        "no:cacheprovider",
        "-q",
        "tests/guards/test_a.py",
    ]


def test_each_run_gets_a_fresh_bytecode_prefix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[dict[str, object]] = []

    def stood_in(args: list[str], **kwargs: object) -> object:
        seen.append({"args": args, **kwargs})
        return type("Done", (), {"returncode": 1, "stdout": "out\n", "stderr": "err\n"})()

    monkeypatch.setattr("run_mutations.subprocess.run", stood_in)
    assert run_process(["x"], tmp_path) == (1, "out\nerr\n")
    assert run_process(["x"], tmp_path) == (1, "out\nerr\n")
    first, second = (call.pop("env") for call in seen)
    assert (
        seen
        == [{"args": ["x"], "cwd": tmp_path, "capture_output": True, "text": True, "check": False}]
        * 2
    )
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    assert first["PYTHONPYCACHEPREFIX"] != second["PYTHONPYCACHEPREFIX"]


def write_file(repo: Path, text: str = VALID) -> str:
    (repo / "mutations").mkdir(exist_ok=True)
    (repo / "mutations/288.toml").write_text(text)
    return "mutations/288.toml"


def test_main_reports_and_passes_when_all_are_as_predicted(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    summary = repo / "summary.md"
    runner = StoodIn(repo, {SOURCE: CLEAN, "def f():\n    return 2\n": CAUGHT})
    code = main([write_file(repo)], runner, repo, {"GITHUB_STEP_SUMMARY": str(summary)})
    assert code == 0
    report = (repo / "mutations-report.md").read_text()
    assert report.startswith("## mutations/288.toml\n\n| Mutation |")
    assert "**2 of 2 as predicted.**" in report
    assert summary.read_text() == report
    assert "**2 of 2 as predicted.**" in capsys.readouterr().out


def test_main_appends_to_a_summary_already_written(repo: Path) -> None:
    summary = repo / "summary.md"
    summary.write_text("before\n")
    runner = StoodIn(repo, {SOURCE: CLEAN, "def f():\n    return 2\n": CAUGHT})
    main([write_file(repo)], runner, repo, {"GITHUB_STEP_SUMMARY": str(summary)})
    assert summary.read_text().startswith("before\n## mutations/288.toml")


def test_main_fails_when_any_row_is_not_as_predicted(repo: Path) -> None:
    runner = StoodIn(repo, {SOURCE: CLEAN, "def f():\n    return 2\n": CLEAN})
    assert main([write_file(repo)], runner, repo, {}) == 1
    assert "**1 of 2 as predicted.**" in (repo / "mutations-report.md").read_text()


def test_main_fails_on_a_file_it_cannot_read_and_says_why(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([write_file(repo, "")], StoodIn(repo, {}), repo, {}) == 1
    assert "mutations/288.toml: no mutation" in capsys.readouterr().out


def test_main_fails_on_a_file_that_is_not_there(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["mutations/none.toml"], StoodIn(repo, {}), repo, {}) == 1
    assert "cannot read mutations/none.toml" in capsys.readouterr().out


@pytest.mark.parametrize(
    "name",
    [
        "288.toml",
        "mutations/288.yml",
        "mutations/../pyproject.toml",
        "mutations/a/288.toml",
        "/mutations/288.toml",
    ],
    ids=["outside", "not-toml", "climbs-out", "nested", "absolute"],
)
def test_main_refuses_a_file_outside_the_mutations_folder(
    repo: Path, name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([name], StoodIn(repo, {}), repo, {}) == 2
    assert f"{name} is not a mutations/<name>.toml file" in capsys.readouterr().err


def test_main_with_no_file_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([], StoodIn(Path(), {}), Path(), {}) == 2
    assert "usage:" in capsys.readouterr().err


def test_the_script_runs_the_files_it_is_given_from_the_working_directory(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], object]] = []

    def stood_in(args: list[str], **kwargs: object) -> object:
        calls.append((args, kwargs["cwd"]))
        answer = CLEAN if (repo / TARGET).read_text() == SOURCE else CAUGHT
        return type("Done", (), {"returncode": answer[0], "stdout": answer[1], "stderr": ""})()

    monkeypatch.setattr(subprocess, "run", stood_in)
    monkeypatch.chdir(repo)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), write_file(repo)])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exited.value.code == 0
    assert calls == [(command("integration", (TESTS,)), repo)] * 2
    assert "**2 of 2 as predicted.**" in (repo / "mutations-report.md").read_text()
