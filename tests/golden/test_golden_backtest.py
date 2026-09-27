"""The golden backtest, and the look-ahead truncation check (M3 spec §9, core spec §10.3).

``scripts/record_golden.py`` runs ``buy-and-hold`` over a year of real, recorded Yahoo data
through the real ``YahooDataSource``, ``CachedDataSource``, ``IdxMarketRules`` and engine. Its
result, its income report included, must equal the stored file exactly, in integer rupiah.
After a change that moves the numbers on purpose, re-record with
``uv run python scripts/record_golden.py`` and review the diff.

The truncation check: every registered strategy, run to day D and to D plus 20 trading days,
makes the same decisions up to D, so no decision can have read a later price.
"""

import json
from datetime import date
from functools import cache
from pathlib import Path

import pytest
from record_golden import END, GOLDEN, HISTORY_START, STOCKS, main, record, recorded, run, summary

from steadyhand import DATA_BAR_REFUSED, HISTORY_YEARS, IDR, STRATEGIES, Money, years_before
from steadyhand_idx import IdxMarketRules


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def test_buy_and_hold_reproduces_the_stored_results_exactly(tmp_path: Path) -> None:
    stored = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert summary(run(tmp_path)) == stored


def test_the_recorder_writes_the_stored_file_byte_for_byte(tmp_path: Path) -> None:
    written = record(tmp_path / "cache", tmp_path / "golden.json")
    assert written.read_bytes() == GOLDEN.read_bytes()


def test_the_recorder_takes_no_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["extra"]) == 2
    assert "uv run python scripts/record_golden.py" in capsys.readouterr().out


def test_the_window_holds_the_events_it_was_chosen_for(tmp_path: Path) -> None:
    """The golden file is only worth pinning if the run meets a split, dividends and refusals."""
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
    assert paid == {"ASII", "BBCA", "TLKM", "UNVR"}
    assert "BBRI" not in held
    assert result.warnings[0].key == DATA_BAR_REFUSED
    assert result.warnings[0].text.startswith(
        "BBRI: the data source refused 146 day(s) (2021-02-01 to 2021-09-07),"
    )


def test_a_fetch_outside_the_recording_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"^ASII\.JK: the fixture covers 2017-01-31 to 2022-01-31"):
        run(tmp_path, end=date(2022, 2, 7))
    with pytest.raises(
        ValueError, match=r"^ASII\.JK: the fixture covers 2017-01-31 to 2022-01-31, not 2017-01-30"
    ):
        recorded("ASII.JK", date(2017, 1, 30), END)


def test_the_recordings_reach_five_years_before_the_run_ends() -> None:
    # Growth reads a year window four years back, so five years of history must be there.
    assert years_before(END, HISTORY_YEARS) == HISTORY_START
    for stock in STOCKS:
        rows = recorded(f"{stock}.JK", HISTORY_START, END).rows
        assert (rows[0].day, rows[-1].day) == (HISTORY_START, END), stock


def test_the_income_report_agrees_with_what_the_engine_paid(tmp_path: Path) -> None:
    result = run(tmp_path)
    income = result.run.income
    assert income is not None
    paid = {
        (e.instrument.symbol, e.ex_date): e for report in result.run.reports for e in report.paid
    }
    expected = [dividend for held in income.run_rate.holdings for dividend in held.dividends]
    # Every dividend of the trailing year was paid in the run, on the pay date the calendar uses.
    assert len(expected) == len(paid) == 7
    assert all(e.pay_date == paid[(e.instrument.symbol, e.ex_date)].pay_date for e in expected)
    # BBCA's 2021-04-08 dividend: Rp432 a share on the 700 shares held before the 1-for-5 split,
    # and Rp86.4 a share, restated, on the 3,500 held after it. Rp302,400 either way.
    bbca = paid[("BBCA", date(2021, 4, 8))]
    assert bbca.gross == Money(302_400, IDR)
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
