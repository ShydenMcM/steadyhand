"""The mutations runner against a real pytest (#288): its output read as the unit tests' stand-ins
assume, a run that did not finish refused, and two same-length mutations of one file run back to
back, each judged on its own bytes. The runner's logic, with pytest stood in, is unit-tested in
``tests/scripts/test_run_mutations.py``."""

import sys
from pathlib import Path

import pytest
from run_mutations import Mutation, MutationError, Outcome, Row, parse_outcome, run_all, run_pytest

SOURCE = "def f():\n    return 1\n"
# The planted test file, a line a string: tests/guards/test_one_test_per_case.py counts every line
# that starts with a test definition, and these are text, not tests of this file.
TESTS = "\n".join(
    [
        "import pytest",
        "from mod import f",
        "",
        "def test_a():",
        "    assert True",
        "",
        "def test_f():",
        "    assert f() == 1",
        "",
        '@pytest.mark.parametrize("n", [1, 2])',
        "def test_g(n):",
        "    assert n >= 1",
        "",
    ]
)


def pytest_run(repo: Path, *tests: str) -> tuple[int, str]:
    """A real pytest of *tests* in *repo*, with the summary lines CI's ``-ra`` prints."""
    args = [sys.executable, "-m", "pytest", "-q", "-ra", "-p", "no:cacheprovider", *tests]
    return run_pytest(args, repo)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "mod.py").write_text(SOURCE)
    (tmp_path / "test_mod.py").write_text(TESTS)
    return tmp_path


def test_a_clean_run_reads_as_green_with_its_totals(repo: Path) -> None:
    assert parse_outcome(*pytest_run(repo, "test_mod.py")) == Outcome(0, frozenset(), "4 passed")


def test_a_red_run_names_each_failed_test_with_its_parameters(repo: Path) -> None:
    (repo / "mod.py").write_text("def f():\n    return 2\n")
    assert parse_outcome(*pytest_run(repo, "test_mod.py")) == Outcome(
        1, frozenset({"test_mod.py::test_f"}), "1 failed, 3 passed"
    )
    (repo / "test_mod.py").write_text(TESTS.replace("n >= 1", "n < 1"))
    assert parse_outcome(*pytest_run(repo, "test_mod.py")).failed == {
        "test_mod.py::test_f",
        "test_mod.py::test_g[1]",
        "test_mod.py::test_g[2]",
    }


def test_a_file_that_cannot_be_collected_is_refused_as_interrupted(repo: Path) -> None:
    (repo / "mod.py").write_text("def f(:\n")
    with pytest.raises(MutationError, match=r"exit 2 \(interrupted\)"):
        parse_outcome(*pytest_run(repo, "test_mod.py"))


def test_no_test_collected_is_refused(repo: Path) -> None:
    (repo / "test_none.py").write_text("x = 1\n")
    with pytest.raises(MutationError, match=r"exit 5 \(no tests ran\)"):
        parse_outcome(*pytest_run(repo, "test_none.py"))


def test_same_length_mutations_back_to_back_are_each_judged_on_their_own_bytes(
    repo: Path,
) -> None:
    def mutation(name: str, new: str, expect: str, *red: str) -> Mutation:
        tests = ("test_mod.py",)
        return Mutation(
            name, "f changes", "mod.py", "    return 1", new, "integration", tests, expect, red
        )

    # Every rewrite keeps the file's length, within about a second of the last. Bytecode cached by
    # size and whole-second time would run the baseline's code for M1 (green, not red) and M1's
    # for M2 (red, not green); the runner's fresh bytecode prefix per run rules both out.
    found = run_all(
        repo,
        [
            mutation("M1", "    return 2", "red", "test_mod.py::test_f"),
            mutation("M2", "    return+1", "green"),
        ],
        lambda _suite, tests: pytest_run(repo, *tests),
    )
    assert found == [
        Row("baseline", "integration", "green", "green", "4 passed", ok=True),
        Row("M1", "integration", "red", "red", "1 failed, 3 passed", ok=True),
        Row("M2", "integration", "green", "green", "4 passed", ok=True),
    ]
    assert (repo / "mod.py").read_text() == SOURCE
