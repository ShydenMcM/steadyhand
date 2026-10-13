"""The golden backtests over a year of real, recorded Yahoo data, and the look-ahead truncation
check over it (M3 spec §9, core spec §10.3), moved out of unit by #292: each runs the year of five
recorded stocks, BBRI's whole history restored, through the real ``YahooDataSource``,
``CachedDataSource``, ``IdxMarketRules`` and engine, over the unit limit of 0.07 s of its own CPU
in its heaviest measured run (develop, 2026-10-13: 0.30 s to 0.77 s). ``scripts/record_golden.py``
writes the stored files they reproduce; after a change that moves the numbers on purpose,
re-record with ``uv run python scripts/record_golden.py`` and review the diff.

The unit suite keeps a stand-in of each, of the same name, in
``tests/golden/test_golden_backtest.py``: the same checks over nineteen trading days of three
made-up stocks (``tests/cli/short_world.py``), against their own pinned files in
``tests/fixtures/golden/made-up``.
"""

import json
from datetime import date
from functools import cache
from pathlib import Path

import pytest
from record_golden import (
    EXEMPT_GOLDEN,
    GOLDEN,
    GROWTH_GOLDEN,
    record,
    record_exempt,
    record_growth,
    run,
    run_exempt,
    run_growth,
    summary,
)

from steadyhand import (
    IDR,
    STRATEGIES,
    Money,
    Note,
)
from steadyhand_idx import IdxMarketRules
from steadyhand_idx.notes import DATA_PRICES_RESTORED


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def test_buy_and_hold_reproduces_the_stored_results_exactly(tmp_path: Path) -> None:
    stored = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert summary(run(tmp_path)) == stored


def test_the_recorder_writes_the_stored_file_byte_for_byte(tmp_path: Path) -> None:
    written = record(tmp_path / "cache", tmp_path / "golden.json")
    assert written.read_bytes() == GOLDEN.read_bytes()


def test_the_switch_on_run_reproduces_its_stored_results_exactly(tmp_path: Path) -> None:
    stored = json.loads(EXEMPT_GOLDEN.read_text(encoding="utf-8"))
    assert summary(run_exempt(tmp_path)) == stored


def test_the_recorder_writes_the_switch_on_file_byte_for_byte(tmp_path: Path) -> None:
    written = record_exempt(tmp_path / "cache", tmp_path / "exempt.json")
    assert written.read_bytes() == EXEMPT_GOLDEN.read_bytes()


def test_the_dividend_growth_run_reproduces_its_stored_results_exactly(tmp_path: Path) -> None:
    stored = json.loads(GROWTH_GOLDEN.read_text(encoding="utf-8"))
    assert summary(run_growth(tmp_path)) == stored


def test_the_recorder_writes_the_dividend_growth_file_byte_for_byte(tmp_path: Path) -> None:
    written = record_growth(tmp_path / "cache", tmp_path / "growth.json")
    assert written.read_bytes() == GROWTH_GOLDEN.read_bytes()


def test_the_window_holds_the_events_it_was_chosen_for(tmp_path: Path) -> None:
    """The golden file is only worth pinning if the run meets a split, dividends, and prices
    restored from an adjustment Yahoo does not report (#160)."""
    result = run(tmp_path)
    held = {p.instrument.symbol: p.quantity for p in result.run.final.holdings.portfolio.positions}
    # BBCA's 1-for-5 split on 13 October 2021: every share bought became five.
    bought = sum(
        fill.quantity
        for report in result.run.reports
        for fill in report.fills
        if fill.order.instrument.symbol == "BBCA"
    )
    assert bought > 0
    assert held["BBCA"] == 5 * bought
    paid = {e.instrument.symbol for report in result.run.reports for e in report.paid}
    assert paid == {"ASII", "BBCA", "BBRI", "TLKM", "UNVR"}
    # BBRI's prices up to 2021-09-07 are restored (f = 1.100019), so it is ordered on the first
    # day and bought at the next open, and its 2021 dividend is credited at the restored Rp98.9057
    # a share.
    (bbri,) = [
        e for report in result.run.reports for e in report.paid if e.instrument.symbol == "BBRI"
    ]
    assert (bbri.ex_date, bbri.gross) == (date(2021, 4, 6), Money(445_075, IDR))  # 4,500 shares
    assert held["BBRI"] == 4_600
    # The restoration is the run's one warning: BBRI's whole recording from GRID_START.
    assert result.warnings == (
        Note(
            DATA_PRICES_RESTORED,
            "BBRI: Yahoo's prices from 2014-01-06 to 2021-09-07 carry an adjustment Yahoo does "
            "not report, so steadyhand restored them: every price and dividend in that span is "
            "multiplied by 1.100019, proven by 7,380 prices that fit the IDX tick grid at that "
            "factor and at no other.",
        ),
    )


def test_the_income_report_agrees_with_what_the_engine_paid(tmp_path: Path) -> None:
    result = run(tmp_path)
    income = result.run.income
    assert income is not None
    paid = {
        (e.instrument.symbol, e.ex_date): e for report in result.run.reports for e in report.paid
    }
    expected = [dividend for held in income.run_rate.holdings for dividend in held.dividends]
    # Every dividend of the trailing year was paid in the run, on the pay date the calendar uses.
    assert len(expected) == len(paid) == 8
    assert all(  # runtime population: the dividends the run's income report holds
        e.pay_date == paid[(e.instrument.symbol, e.ex_date)].pay_date for e in expected
    )
    # BBCA's 2021-04-08 dividend: Rp432 a share on the 500 shares held before the 1-for-5 split,
    # and Rp86.4 a share, restated, on the 2,500 held after it. Rp216,000 either way.
    bbca = paid[("BBCA", date(2021, 4, 8))]
    assert bbca.gross == Money(216_000, IDR)
    assert bbca in expected


@pytest.mark.parametrize("strategy", sorted(STRATEGIES))
@pytest.mark.parametrize("cut", [date(2021, 4, 7), date(2021, 10, 12), date(2021, 11, 29)])
def test_a_run_to_day_d_decides_as_a_longer_run_did_up_to_d(
    strategy: str, cut: date, tmp_path: Path
) -> None:
    # The cuts fall on the day before BBCA's dividend ex-date, the day before its split, and the
    # day before UNVR's ex-date; each longer run goes on for twenty more trading days.
    # Decisions only: an income report reads no bar after its day, and a run cut this early
    # would need history from before the recordings start.
    short = run(tmp_path / "short", strategy, cut, income=False)
    longer = run(tmp_path / "long", strategy, _trading_days_after(cut, 20), income=False)
    count = len(short.run.reports)
    assert short.run.reports[-1].day == cut
    assert len(longer.run.reports) == count + 20
    assert longer.run.reports[:count] == short.run.reports


def _trading_days_after(day: date, count: int) -> date:
    found = 0
    while found < count:
        day = date.fromordinal(day.toordinal() + 1)
        found += rules().is_trading_day(day)
    return day
