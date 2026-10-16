"""The mutations runner (#288): a story's planted mutations, each applied to a clean checkout and
judged against the suite that should catch it, in CI.

A unit test starts no process (#286): here pytest is stood in by a runner that answers each call.
The real pytest's output is read in ``tests/integration/scripts/test_run_mutations_pytest.py``."""

import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from run_mutations import (
    SUITES,
    Mutation,
    MutationError,
    Outcome,
    Row,
    apply,
    command,
    judge,
    load,
    main,
    parse_outcome,
    render,
    run_all,
    run_pytest,
)

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
    assert SUITES == ("guards", "integration", "properties")


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
        f"named tests stayed green: {TESTS}::test_f"
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
    assert run_pytest(["x"], tmp_path) == (1, "out\nerr\n")
    assert run_pytest(["x"], tmp_path) == (1, "out\nerr\n")
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
