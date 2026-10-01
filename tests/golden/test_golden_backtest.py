"""The golden backtest, and the look-ahead truncation check (M3 spec §9, core spec §10.3).

``scripts/record_golden.py`` runs ``buy-and-hold`` over a year of real, recorded Yahoo data
through the real ``YahooDataSource``, ``CachedDataSource``, ``IdxMarketRules`` and engine. Its
result, its income report included, must equal the stored file exactly, in integer rupiah.
After a change that moves the numbers on purpose, re-record with
``uv run python scripts/record_golden.py`` and review the diff.

``dividend-growth`` has a golden run of its own, over the same window with a two-year test, a
look-back holding UNVR's 2020 split, TLKM's look-back refused, and a review in January 2022.

The truncation check: every registered strategy, run to day D and to D plus 20 trading days,
makes the same decisions up to D, so no decision can have read a later price.
"""

import json
from datetime import date
from functools import cache
from pathlib import Path

import pytest
from record_golden import (
    END,
    EXEMPT_GOLDEN,
    GOLDEN,
    GROWTH_GOLDEN,
    HISTORY_START,
    STOCKS,
    main,
    record,
    record_exempt,
    record_growth,
    recorded,
    run,
    run_exempt,
    run_growth,
    summary,
)

from steadyhand import (
    CLAIMS_LABEL,
    DATA_BAR_REFUSED,
    DATA_DIVIDENDS_HISTORY_REFUSED,
    EXEMPTION_CLAIM_BROKEN,
    EXEMPTION_DEADLINE_MISSED,
    HISTORY_YEARS,
    IDR,
    STRATEGIES,
    STRATEGY_TOO_FEW_QUALIFIED,
    Money,
    years_before,
)
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


def test_the_switch_on_run_reproduces_its_stored_results_exactly(tmp_path: Path) -> None:
    stored = json.loads(EXEMPT_GOLDEN.read_text(encoding="utf-8"))
    assert summary(run_exempt(tmp_path)) == stored


def test_the_recorder_writes_the_switch_on_file_byte_for_byte(tmp_path: Path) -> None:
    written = record_exempt(tmp_path / "cache", tmp_path / "exempt.json")
    assert written.read_bytes() == EXEMPT_GOLDEN.read_bytes()


def test_the_switch_on_run_holds_a_claim_of_each_kind_as_worked_by_hand() -> None:
    stored = json.loads(EXEMPT_GOLDEN.read_text(encoding="utf-8"))
    # Each [quantity, price, fee, levy, sale tax]: the cost basis is 200 x 34,875 + 11,509 + 2,999
    # = 6,989,508 and 300 x 30,400 + 15,049 + 3,921 = 9,138,970, together 16,128,478.
    assert [f[3:8] for f in stored["fills"] if f[1] == "BBCA" and f[2] == "buy"] == [
        [200, 34_875, 11_509, 2_999, 0],
        [300, 30_400, 15_049, 3_921, 0],
    ]
    until = "2023-12-31"  # a 2021 purchase is protected through its third tax year
    assert stored["claims"] == [
        # Reinvested by the deadline: ASII's buy on 2 July 2021 (1,900 x 5,050 = 9,595,000)
        # covers the four claims paid before it, oldest first: 86,400 (200 BBCA shares x Rp432,
        # before the split), 139,200 (1,600 ASII x 87) and 140,000 (1,400 UNVR x 100) stay whole.
        ["BBCA", "2021-04-08", "2021-04-28", 86_400, "2022-03-31", 0, [[86_400, until]]],
        ["ASII", "2021-05-03", "2021-05-27", 139_200, "2022-03-31", 0, [[139_200, until]]],
        ["UNVR", "2021-06-08", "2021-06-28", 140_000, "2022-03-31", 0, [[140_000, until]]],
        # Broken after reinvestment: selling 2,400 of the 2,500 BBCA shares on 2 November
        # releases 16,128,478 x 2,400 / 2,500 = 15,483,338.88, rounded up to 15,483,339, so
        # 645,139 stays invested against 869,630 protected. The 224,491 short at the close of
        # 4 November, the sale's settlement date, breaks from the newest claim, TLKM's
        # (3,000 x 168.01 = 504,030): 504,030 - 224,491 = 279,539 stays protected.
        ["TLKM", "2021-06-09", "2021-06-29", 504_030, "2022-03-31", 0, [[279_539, until]]],
        # Still open at the end: 100 BBCA x 120, with a year to be reinvested.
        ["BBCA", "2022-03-28", "2022-04-18", 12_000, "2023-03-31", 12_000, []],
    ]
    # 10% of 224,491 is 22,449.1, rounded up. Taxed at the deadline: ASII's 3,500 x 45 = 157,500
    # and BBCA's 100 x 25 = 2,500 were never reinvested, so 15,750 + 250 on 1 April 2022.
    assert stored["taxes"] == [["2021-11-04", 22_450], ["2022-04-01", 16_000]]
    assert [note[:2] for note in stored["notes"]] == [
        ["2021-11-04", EXEMPTION_CLAIM_BROKEN],
        ["2022-04-01", EXEMPTION_DEADLINE_MISSED],
        ["2022-04-01", EXEMPTION_DEADLINE_MISSED],
    ]
    assert stored["income"]["claims"] == [CLAIMS_LABEL, stored["claims"]]
    # Tax shows in the month it was booked, not the month its dividend was paid (M4 spec §6.5).
    taxed = {month[0]: month[2] for month in stored["income"]["received"]["by_month"] if month[2]}
    assert taxed == {"2021-11-01": 22_450, "2022-04-01": 16_000}


def test_the_dividend_growth_run_reproduces_its_stored_results_exactly(tmp_path: Path) -> None:
    stored = json.loads(GROWTH_GOLDEN.read_text(encoding="utf-8"))
    assert summary(run_growth(tmp_path)) == stored


def test_the_recorder_writes_the_dividend_growth_file_byte_for_byte(tmp_path: Path) -> None:
    written = record_growth(tmp_path / "cache", tmp_path / "growth.json")
    assert written.read_bytes() == GROWTH_GOLDEN.read_bytes()


def test_the_dividend_growth_run_reviews_as_worked_by_hand() -> None:
    stored = json.loads(GROWTH_GOLDEN.read_text(encoding="utf-8"))
    # 1 February 2021 tests the dividends of 2018 to 2020, a share in today's shares. BBCA's
    # 260, 355, 553 grew. UNVR's 183, 241, 194 are its dividends of before its 1-for-5 split of
    # January 2020 restated, so 194 >= 183 passes (unrestated, 915 would not). BBRI passes but
    # its prices are refused that day, so it cannot be bought; ASII's 184 < 190 fails, and
    # TLKM's look-back was refused. Two picks at half each, the risk limit's 25% bought on the
    # 2nd: 700 x 34,875 and 3,500 x 7,125, just under Rp25,000,000 each.
    assert [fill[:5] for fill in stored["fills"] if fill[0] == "2021-02-02"] == [
        ["2021-02-02", "BBCA", "buy", 700, 34_875],
        ["2021-02-02", "UNVR", "buy", 3_500, 7_125],
    ]
    # 3 January 2022 tests 2019 to 2021. BBCA's 71, 110.6, 111.4 (restated by its October 2021
    # split) pass; UNVR's 166 < 241 fails, and so do BBRI's 89.9 < 120.2 and ASII; TLKM's
    # history is still incomplete. One pick under min_stocks 2: the note, and UNVR is sold.
    assert stored["notes"] == [
        [
            "2022-01-03",
            STRATEGY_TOO_FEW_QUALIFIED,
            "Only 1 stock passed the dividend test; the rest is held as cash until more do.",
        ]
    ]
    assert [fill[:3] for fill in stored["fills"] if fill[2] == "sell"] == [
        ["2022-01-04", "UNVR", "sell"]
    ]
    assert stored["positions"] == {"BBCA": 3_500}
    assert [warning[0] for warning in stored["warnings"]] == [
        DATA_BAR_REFUSED,
        DATA_DIVIDENDS_HISTORY_REFUSED,
    ]
    assert stored["warnings"][1][1].startswith(
        "TLKM: the data source refused its corporate actions from 2018-01-01 to 2021-01-31, "
        "before the run"
    )


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
