"""One test per case: no population known before the run is looped inside one test (#173).

Shyden's rule (2026-10-02, every repo): a loop inside one test stops at its first failing case
and hides the rest, and its title names no case, so a fixed population is parametrized instead.
``looped_cases`` finds the loops; this file holds the suite to them, with a burn-down list of the
sites found on 2026-10-03 that the conversion tickets (#174-#177) shrink to nothing.
"""

import re
from collections import Counter
from pathlib import Path

import pytest
from looped_cases import ALLOW, LoopedCase, UnreadableTestFileError, read_file, read_tests

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
RAW_TEST = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+test", re.MULTILINE)

# Measured on 2026-10-03 after #175: 1,101 tests read in 86 files. Lower it only by a deliberate
# edit when the suite shrinks.
TESTS_READ_FLOOR = 1_100

# The looped cases found on 2026-10-03 (88 in 66 tests), by file and test: each conversion
# removes its entries, and an entry that no longer loops fails until it is removed, so this list
# can only shrink.
BURN_DOWN: dict[str, dict[str, int]] = {
    "tests/golden/test_golden_backtest.py": {
        "test_the_income_report_agrees_with_what_the_engine_paid": 1,
        "test_the_recordings_reach_five_years_before_the_run_ends": 1,
    },
    "tests/golden/test_golden_snapshot.py": {
        "test_every_day_report_of_both_golden_runs_reads_back_equal": 2,
        "test_the_final_state_of_both_golden_runs_reads_back_equal": 1,
    },
    "tests/idx/test_bands.py": {
        "test_every_period_matches_the_research": 1,
    },
    "tests/idx/test_cache.py": {
        "test_a_refused_look_back_is_not_stored": 1,
        "test_the_restorations_migration_reads_every_range_again": 1,
    },
    "tests/idx/test_datafile.py": {
        "test_dates_must_be_plain_toml_dates": 1,
        "test_decimals_are_written_as_strings_and_never_negative": 1,
        "test_ints_must_be_ints_at_or_above_the_minimum": 1,
        "test_rows_must_be_a_non_empty_array_of_tables": 1,
        "test_strings_must_be_non_empty": 1,
    },
    "tests/idx/test_factor.py": {
        "test_a_day_before_the_first_grid_is_never_provable": 1,
        "test_a_proven_factor_restores_the_true_prices": 1,
        "test_the_window_rejects_half_and_double_the_factor_although_both_fit_the_grid": 1,
    },
    "tests/idx/test_rules.py": {
        "test_band_edges_are_the_widest_valid_prices_inside_the_band": 2,
    },
    "tests/idx/test_ticks.py": {
        "test_rounding_is_tight_and_valid": 2,
    },
    "tests/idx/test_yahoo.py": {
        "test_a_dividend_in_an_unproven_run_is_refused_naming_its_ex_date": 1,
        "test_bbri_s_whole_recording_agrees_with_every_older_recording": 1,
        "test_recovered_prices_obey_the_ticks_and_bands": 3,
    },
    "tests/meta/test_hypothesis_profiles.py": {
        "test_every_profile_has_no_deadline": 1,
    },
    "tests/meta/test_legal_line.py": {
        "test_relative_imports_are_resolved": 1,
    },
    "tests/meta/test_lessons.py": {
        "test_every_lesson_file_is_loaded": 2,
        "test_module_8_has_a_lesson_for_each_strategy_citing_its_guide": 1,
    },
    "tests/meta/test_note_keys.py": {
        "test_every_key_is_a_dotted_lowercase_identifier_named_after_itself": 1,
        "test_every_note_is_built_from_a_note_key_and_every_note_key_is_used": 1,
        "test_no_key_is_defined_twice": 1,
    },
    "tests/meta/test_packaging.py": {
        "test_each_package_ships_the_root_licence": 1,
    },
    "tests/meta/test_public_api.py": {
        "test_training_is_left_out_of_the_engine_and_exports_its_own_names": 1,
    },
    "tests/meta/test_strategy_guides.py": {
        "test_each_registered_name_is_the_strategys_own": 1,
    },
    "tests/perf/test_cli_startup.py": {
        "test_a_command_that_reads_no_market_data_starts_within_budget": 1,
    },
    "tests/perf/test_performance.py": {
        "test_ten_years_of_45_stocks_run_inside_the_budget": 4,
    },
}

PLANTED = {
    "for over a constant": (
        "CASES = (1, 2)\ndef test_x():\n    for case in CASES:\n        assert case\n",
        LoopedCase("test_x", 3, "for"),
    ),
    "for over enumerate": (
        "def test_x():\n    for i, c in enumerate('ab'):\n        assert c\n",
        LoopedCase("test_x", 2, "for"),
    ),
    "for over zip": (
        "def test_x():\n    for a, b in zip((1,), (1,), strict=True):\n        assert a == b\n",
        LoopedCase("test_x", 2, "for"),
    ),
    "for with a nested assert": (
        "def test_x():\n    for c in (1, 2):\n        if c:\n            assert c\n",
        LoopedCase("test_x", 2, "for"),
    ),
    "for expecting a raise": (
        (
            "import pytest\ndef test_x():\n    for bad in ('', 0):\n"
            "        with pytest.raises(ValueError):\n            int(bad)\n"
        ),
        LoopedCase("test_x", 3, "for"),
    ),
    "while": (
        "def test_x():\n    n = 2\n    while n:\n        assert n\n        n -= 1\n",
        LoopedCase("test_x", 3, "while"),
    ),
    "async for": (
        "async def test_x(rows):\n    async for row in rows:\n        assert row\n",
        LoopedCase("test_x", 2, "for"),
    ),
    "all over a generator": (
        "def test_x():\n    assert all(c > 0 for c in (1, 2))\n",
        LoopedCase("test_x", 2, "all"),
    ),
    "any over a generator": (
        "def test_x():\n    assert not any(c < 0 for c in (1, 2))\n",
        LoopedCase("test_x", 2, "any"),
    ),
    "all over a list": (
        "def test_x():\n    assert all([c > 0 for c in (1, 2)])\n",
        LoopedCase("test_x", 2, "all"),
    ),
    "a method of a Test class": (
        "class TestX:\n    def test_y(self):\n        for c in (1, 2):\n            assert c\n",
        LoopedCase("TestX::test_y", 3, "for"),
    ),
    "an async test": (
        "async def test_x():\n    for c in (1, 2):\n        assert c\n",
        LoopedCase("test_x", 2, "for"),
    ),
}


@pytest.mark.parametrize("form", PLANTED)
def test_each_form_of_looped_case_is_found(form: str) -> None:
    source, expected = PLANTED[form]
    assert read_tests(source, "planted.py").looped == (expected,)


ALLOWED = {
    "a loop marked as a runtime population": (
        f"def test_x(days):\n    for day in days:  {ALLOW} the days the run made\n"
        "        assert day\n"
    ),
    "a loop that only builds data": (
        "def test_x():\n    rows = []\n    for c in (1, 2):\n        rows.append(c)\n"
        "    assert rows == [1, 2]\n"
    ),
    "a comprehension that is not judged": (
        "def test_x():\n    rows = [c for c in (1, 2)]\n    assert rows == [1, 2]\n"
    ),
    "all over a value, not a comprehension": ("def test_x(flags):\n    assert all(flags)\n"),
    "a loop in a helper that is not a test": (
        "def check(rows):\n    for r in rows:\n        assert r\ndef test_x():\n    check((1,))\n"
    ),
}


@pytest.mark.parametrize("form", ALLOWED)
def test_what_is_not_a_looped_case(form: str) -> None:
    reading = read_tests(ALLOWED[form], "allowed.py")
    assert reading.tests == ("test_x",)
    assert reading.looped == ()


def test_the_tests_read_are_the_ones_pytest_collects() -> None:
    source = (
        "def test_a(): ...\n"
        "async def test_b(): ...\n"
        "def helper(): ...\n"
        "class TestC:\n"
        "    def test_d(self): ...\n"
        "    def helper(self): ...\n"
        "    class TestE:\n"
        "        def test_f(self): ...\n"
        "class Other:\n"
        "    def test_g(self): ...\n"
    )
    assert read_tests(source, "collect.py").tests == (
        "test_a",
        "test_b",
        "TestC::test_d",
        "TestC::TestE::test_f",
    )


def test_a_file_that_does_not_parse_is_refused_by_name() -> None:
    with pytest.raises(UnreadableTestFileError, match=r"^broken\.py: "):
        read_tests("def test_x(:\n", "broken.py")


def test_a_file_is_read_from_disk(tmp_path: Path) -> None:
    path = tmp_path / "test_disk.py"
    path.write_text("def test_x():\n    for c in (1,):\n        assert c\n", encoding="utf-8")
    assert read_file(path).looped == (LoopedCase("test_x", 2, "for"),)


def suite_files() -> list[Path]:
    """Every test module under ``tests/``, found on disk."""
    return sorted(TESTS.rglob("test_*.py"))


FILES = suite_files()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_every_test_in_the_suite_is_read() -> None:
    names = {rel(path) for path in FILES}
    assert {"tests/meta/test_one_test_per_case.py", "tests/engine/test_backtest.py"} <= names
    total = sum(len(read_file(path).tests) for path in FILES)
    assert total >= TESTS_READ_FLOOR, f"read {total} tests in {len(FILES)} files"


@pytest.mark.parametrize("path", FILES, ids=rel)
def test_the_file_is_read_as_every_test_its_text_defines(path: Path) -> None:
    # Independent of the AST reader: a raw count of ``def test`` lines in the file.
    raw = len(RAW_TEST.findall(path.read_text(encoding="utf-8")))
    assert raw > 0
    assert len(read_file(path).tests) == raw


@pytest.mark.parametrize("path", FILES, ids=rel)
def test_the_file_loops_no_case_beyond_the_burn_down_list(path: Path) -> None:
    found = Counter(case.test for case in read_file(path).looped)
    listed = BURN_DOWN.get(rel(path), {})
    new = {test: n for test, n in found.items() if n > listed.get(test, 0)}
    stale = {test: n for test, n in listed.items() if found.get(test, 0) < n}
    assert new == {}, "a fixed population is parametrized, not looped (#173)"
    assert stale == {}, "these no longer loop: take them off BURN_DOWN"


def test_every_burn_down_entry_names_a_test_file_on_disk() -> None:
    names = {rel(path) for path in FILES}
    assert set(BURN_DOWN) <= names
