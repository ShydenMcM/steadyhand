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

# Measured on 2026-10-03: 1,083 tests read in 85 files. Lower it only by a deliberate edit
# when the suite shrinks.
TESTS_READ_FLOOR = 1_082

# The looped cases found on 2026-10-03 (88 in 66 tests), by file and test: each conversion
# removes its entries, and an entry that no longer loops fails until it is removed, so this list
# can only shrink.
BURN_DOWN: dict[str, dict[str, int]] = {
    "tests/cli/test_backtest_command.py": {
        "test_monthly_savings_spreads_the_starting_cash_over_its_instalments": 1,
        "test_the_reports_are_private_and_a_second_run_replaces_them": 1,
    },
    "tests/cli/test_cli.py": {
        "test_help_goes_to_stdout_and_exits_0": 1,
    },
    "tests/cli/test_config.py": {
        "test_the_starter_file_writes_every_key_under_its_comment": 2,
    },
    "tests/cli/test_output.py": {
        "test_a_page_that_shows_a_key_with_no_lesson_is_a_bug_at_every_level": 1,
        "test_with_no_keys_there_is_no_block_at_any_level": 1,
    },
    "tests/cli/test_paper_run.py": {
        "test_a_paper_account_run_day_by_day_ends_where_the_backtest_does": 1,
        "test_the_public_fetch_gives_each_trading_day_its_inputs_oldest_first": 1,
    },
    "tests/cli/test_reports.py": {
        "test_a_run_with_no_goal_shows_no_income_figures": 1,
        "test_each_figure_reads_the_report_field_it_names": 1,
    },
    "tests/engine/test_backtest.py": {
        "test_a_dividend_on_a_refused_day_reaches_the_history_when_read_without_prices": 1,
        "test_a_halt_lasts_to_the_end_of_the_run_and_is_recorded": 2,
        "test_both_runs_share_the_settings": 1,
        "test_compare_gives_every_run_its_income_report_when_there_is_a_goal": 1,
        "test_day_inputs_give_every_day_the_look_back": 1,
        "test_each_run_carries_its_metrics": 1,
        "test_every_stock_the_universe_holds_on_any_day_is_fetched_for_the_whole_window": 1,
        "test_exclusions_and_corporate_actions_reach_their_days": 1,
        "test_refused_days_are_fetched_around_and_the_stock_sits_them_out": 3,
    },
    "tests/engine/test_buy_and_hold.py": {
        "test_it_never_sells_and_buys_only_its_set": 1,
    },
    "tests/engine/test_dividend_growth.py": {
        "test_it_reviews_on_no_day_but_the_first_and_each_new_years_first": 1,
    },
    "tests/engine/test_engine.py": {
        "test_every_day_keeps_cash_whole_and_the_value_adding_up": 2,
    },
    "tests/engine/test_income_projection.py": {
        "test_a_larger_contribution_never_takes_longer": 1,
        "test_nothing_to_project_from_cannot_be_projected": 1,
    },
    "tests/engine/test_ledger_booking.py": {
        "test_every_snapshot_in_a_tree_of_bookings_keeps_its_own_ledger": 2,
    },
    "tests/engine/test_monthly_savings.py": {
        "test_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month": 3,
    },
    "tests/engine/test_portfolio_properties.py": {
        "test_cash_and_share_invariants": 2,
        "test_the_kept_totals_agree_with_the_whole_ledger_on_every_day": 2,
    },
    "tests/engine/test_registry.py": {
        "test_every_registered_strategy_has_a_summary_and_a_turnover": 1,
    },
    "tests/engine/test_simulated_broker.py": {
        "test_fills_keep_cash_whole_lots_ticks_and_bands": 2,
    },
    "tests/engine/test_sizing.py": {
        "test_orders_are_whole_lots_that_never_overshoot_the_target": 1,
    },
    "tests/engine/test_snapshot.py": {
        "test_a_restored_portfolio_behaves_as_the_one_it_was_saved_from": 1,
    },
    "tests/engine/test_view.py": {
        "test_nothing_after_today_is_returned_and_each_dividend_is_restated_by_its_own_splits": 3,
    },
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
    "tests/scripts/test_record_yahoo_fixture.py": {
        "test_a_recording_reads_back_as_the_history_it_was_given": 1,
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
