"""``paper status``, ``report`` and ``resume`` over accounts run across the recorded golden window
(M5 spec §7, §9.2), moved out of unit by #292: each first runs the paper account over months of
five recorded stocks through the real source, cache and state database, over the unit limit of
0.07 s of its own CPU in its heaviest measured run (develop, 2026-10-13: 0.17 s to 1.3 s).

The unit suite keeps a stand-in of each, of the same name, in ``tests/cli/test_paper_commands.py``:
the same pages over nineteen trading days of three made-up stocks (``tests/cli/short_world.py``),
which meet a dividend paid and reinvested, a weight limit that cuts and skips orders, and a halt.
"""

from datetime import date
from pathlib import Path

import pytest
from cli_world import (
    EXEMPT,
    GOLDEN_CONFIG,
    TIGHT,
    golden_backtest,
    halted,
    names_held,
    opened,
    page,
    planted,
    quiet,
    ran_to,
    tables,
)
from record_golden import END, START

from steadyhand import (
    CLAIMS_LABEL,
    FIGURES,
    LIMIT_WEIGHT_CUT,
    LIMIT_WEIGHT_FULL,
    PROJECTION_LABEL,
)
from steadyhand_idx.notes import PAPER_ORDER_SKIPPED, PAPER_RESUMED
from steadyhand_idx.paper_pages import day_report_page, income_page, status_page

DEEP = GOLDEN_CONFIG.replace(
    '[risk]\nmax_weight = "0.25"\n', '[risk]\nmax_weight = "0.25"\nmax_drawdown = "0.05"\n'
)
"""A drawdown limit breached on 2021-03-08 and still breached on 2021-04-30: 9.37% below,
rounded down as every limit is written."""


def test_status_shows_each_holding_with_its_last_close_value_and_weight(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 30), quiet())
    result = cli("paper", "status")
    assert result.code == 0
    assert (
        "Cash: IDR 1,587,638 settled, IDR 0 unsettled\n"
        "Holdings value: IDR 84,138,500\n"
        "Total value: IDR 85,726,138\n"
        "\n"
        "Holdings:\n"
        "Stock  Quantity  Last close           Value  Weight\n"
        "ASII       3300   IDR 4,940  IDR 16,302,000  19.02%\n"
        "BBCA        500  IDR 30,125  IDR 15,062,500  17.57%\n"
        "BBRI       4600   IDR 3,940  IDR 18,124,000  21.14%\n"
        "TLKM       6600   IDR 3,150  IDR 20,790,000  24.25%\n"
        "UNVR       2800   IDR 4,950  IDR 13,860,000  16.17%\n"
        "\n"
        "Queued for the next open:\n"
        "- buy 100 TLKM\n"
    ) in result.out


def test_status_shows_a_dividend_entitlement_until_it_is_paid(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 4, 8), quiet())
    result = cli("paper", "status")
    assert (
        "Dividend entitlements:\n"
        "- BBRI: IDR 445,075 before tax, ex-date 2021-04-06, paid on 2021-04-26\n"
        "- BBCA: IDR 216,000 before tax, ex-date 2021-04-08, paid on 2021-04-28\n"
    ) in result.out


def test_status_shows_open_claims_under_their_label(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 4, 28), quiet(GOLDEN_CONFIG + EXEMPT))
    result = cli("paper", "status")
    assert "Dividend entitlements: none\n" in result.out
    assert (
        f"Reinvestment-exemption claims ({CLAIMS_LABEL}):\n"
        "- BBRI: IDR 445,075 paid on 2021-04-26, IDR 120,075 still to reinvest by 2022-03-31, "
        "IDR 325,000 protected until 2023-12-31\n"
        "- BBCA: IDR 216,000 paid on 2021-04-28, IDR 216,000 still to reinvest by 2022-03-31\n"
    ) in result.out


def test_a_claims_reinvested_parts_are_shown_with_how_long_each_is_protected(
    tmp_path: Path,
) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 30), quiet(GOLDEN_CONFIG + EXEMPT))
    result = cli("paper", "status")
    assert (
        "- BBRI: IDR 445,075 paid on 2021-04-26, IDR 0 still to reinvest by 2022-03-31, "
        "IDR 325,000 protected until 2023-12-31, IDR 120,075 protected until 2023-12-31\n"
        "- BBCA: IDR 216,000 paid on 2021-04-28, IDR 0 still to reinvest by 2022-03-31, "
        "IDR 195,925 protected until 2023-12-31, IDR 20,075 protected until 2023-12-31\n"
    ) in result.out
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        report = store.report(account.last_day)
        assert report is not None
    assert FIGURES["Protection.amount"] in status_page(account, report).keys


def test_the_status_page_names_every_figure_it_shows(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 4, 28), GOLDEN_CONFIG + EXEMPT)
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        report = store.report(account.last_day)
        assert report is not None
    shown = status_page(account, report)
    assert shown.keys == [
        FIGURES["DayReport.settled"],
        FIGURES["DayReport.unsettled"],
        FIGURES["DayReport.holdings_value"],
        FIGURES["DayReport.value"],
        FIGURES["Holdings.last_closes"],
        FIGURES["DividendClaim.gross"],
        FIGURES["DividendClaim.uncovered"],
        FIGURES["Protection.amount"],
    ]


def test_report_shows_the_latest_day_by_default_with_its_holdings(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 30), quiet())
    result = cli("report")
    assert (result.code, result.err) == (0, "")
    assert result.out.startswith("Day report for 2021-06-30\n\n")
    assert (
        "Holdings:\n"
        "Stock  Quantity  Last close           Value  Weight\n"
        "ASII       3300   IDR 4,940  IDR 16,302,000  19.02%\n"
    ) in result.out


def test_a_blocked_order_is_shown_with_its_reason_and_the_dividends_of_the_day(
    tmp_path: Path,
) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 30), quiet(TIGHT))
    result = cli("report", "--day", "2021-06-29")
    assert result.code == 0
    assert (
        "Queued for the next open:\n"
        "- buy 100 UNVR\n"
        "\n"
        "Blocked orders:\n"
        "- skipped: buy 100 ASII: already at the 19.00% limit per stock\n"
        "- skipped: buy 100 BBRI: already at the 19.00% limit per stock\n"
        "- skipped: buy 100 TLKM: already at the 19.00% limit per stock\n"
    ) in result.out
    assert "Dividends paid:\n- TLKM: IDR 991,259 before tax\n" in result.out


def test_the_skipped_order_is_in_the_audit_log_under_its_key(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 29), TIGHT)
    with opened(cli) as store:
        first = next(line for line in store.audit() if line.note.key == PAPER_ORDER_SKIPPED)
    assert (first.day, first.note.text) == (
        date(2021, 2, 2),
        "skipped: buy 100 ASII: already at the 19.00% limit per stock",
    )


def test_a_report_names_the_key_of_each_blocked_orders_reason(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 30), TIGHT)
    with opened(cli) as store:
        cut, skipped = store.report(START), store.report(date(2021, 6, 29))
    assert cut is not None
    assert skipped is not None
    assert LIMIT_WEIGHT_CUT in day_report_page(cut, None).keys
    assert LIMIT_WEIGHT_FULL in day_report_page(skipped, None).keys


def test_the_income_report_is_the_backtests_over_the_same_days(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, END, quiet())
    result = cli("report", "--income")
    assert (result.code, result.err) == (0, "")
    reference = golden_backtest(cli, END, goal=True).run.income
    assert reference is not None
    assert result.out == page("\n".join(income_page(reference).lines))
    # The golden record's income figures (tests/fixtures/golden), as the page writes them.
    assert (
        "Goal: IDR 1,000,000 a month\n"
        "Received: IDR 202,442 a month, 20.24% of the goal\n"
        "Run-rate: IDR 206,964 a month, 20.70% of the goal\n"
        "\n"
        f"{PROJECTION_LABEL}:\n"
        "Reaching IDR 1,000,000 a month, adding IDR 0 a month\n"
        "- pessimistic: from IDR 2,207,626 a year, growing 0.00% a year: not within 50 years\n"
        "- base: from IDR 2,759,533 a year, growing 5.00% a year: the goal in 18.0 years\n"
        "- optimistic: from IDR 2,759,533 a year, growing 6.09% a year: the goal in 16.0 years\n"
    ) in result.out


def test_resume_writes_no_login_name_anywhere_in_the_state_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = planted(halted(tmp_path), monkeypatch)
    assert cli("resume", "buy-and-hold", stdin="resume\n").code == 0
    assert names_held(cli, "resumed ordering after the halt of 2021-02-02 ") == []


def test_resume_is_refused_while_the_drawdown_is_still_past_its_limit(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 4, 30), quiet(DEEP))
    before = tables(cli)
    result = cli("resume", "buy-and-hold", stdin="resume\n")
    assert (result.code, result.out) == (3, "")
    assert result.err == (
        "steadyhand-idx: the unit value is still 9.12% below its high-water mark, at or past "
        "the 5.00% drawdown limit; the halt stays until it recovers or you raise "
        "risk.max_drawdown\n"
    )
    assert tables(cli) == before
    raised = DEEP.replace('max_drawdown = "0.05"', 'max_drawdown = "0.10"')
    cli.config.write_text(quiet(raised), encoding="utf-8")
    assert cli("resume", "buy-and-hold", stdin="resume\n").code == 0
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        assert account.state.halt is None
        assert store.audit()[-1].note.key == PAPER_RESUMED
