"""``paper status``, ``report``, ``resume`` and ``paper switch`` (M5 spec §7, §9.2).

Each command runs through ``main`` over an account that ``paper run`` built from the recorded
Yahoo answers, in a temporary data directory, at a fixed time in Jakarta. Pages are compared
whole with training off, so a figure that moves or a line that goes missing is seen; the keys
each page names are checked on the page itself.
"""

import io
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from cli_world import (
    GOLDEN_CONFIG,
    Cli,
    at,
    golden_backtest,
    opened,
    paper,
    recorded_source,
    run_on,
    tables,
    trading_days,
)
from record_golden import END, START

from steadyhand import (
    CLAIMS_LABEL,
    CORPORATE_SPLIT_ORDER_CANCELLED,
    DATA_BAR_REFUSED,
    DISCLAIMER,
    FIGURES,
    IDR,
    LIMIT_WEIGHT_CUT,
    LIMIT_WEIGHT_FULL,
    PROJECTION_LABEL,
    RISK_HALT_DRAWDOWN,
    DayReport,
    EngineState,
    Halt,
    Holdings,
    Instrument,
    Money,
    Note,
    Portfolio,
    RiskLimits,
    UnitValue,
)
from steadyhand_idx.cli import World, main
from steadyhand_idx.notes import PAPER_ORDER_SKIPPED, PAPER_RESUMED, PAPER_STRATEGY_SWITCHED
from steadyhand_idx.paper import HaltCausePresentError, check_resume
from steadyhand_idx.paper_pages import day_report_page, income_page, status_page
from steadyhand_idx.state import Account, Outcome

QUIET = '\n[training]\nlevel = "off"\n'
"""Training off: a page is then its lines and the disclaimer, nothing else."""

EXEMPT = "\n[tax]\ndividend_reinvestment_exemption = true\n"

JUMPY = GOLDEN_CONFIG.replace(
    '[risk]\nmax_weight = "0.25"\n', '[risk]\nmax_weight = "0.25"\ndaily_loss_limit = "0.001"\n'
)
"""A daily-loss limit the golden run's second day breaches (as ``paper run``'s halt test)."""

TIGHT = GOLDEN_CONFIG.replace('[risk]\nmax_weight = "0.25"\n', '[risk]\nmax_weight = "0.19"\n')
"""A 19% limit per stock, under buy-and-hold's 20% of each of the five: its first orders are cut to
the limit and its later top-ups skipped. With BBRI's prices restored (#160), the golden settings
spread the money five ways and never block an order."""

DEEP = GOLDEN_CONFIG.replace(
    '[risk]\nmax_weight = "0.25"\n', '[risk]\nmax_weight = "0.25"\nmax_drawdown = "0.05"\n'
)
"""A drawdown limit breached on 2021-03-08 and still breached on 2021-04-30: 9.37% below,
rounded down as every limit is written."""


def quiet(config: str = GOLDEN_CONFIG) -> str:
    assert "[training]" not in config
    return config + QUIET


def page(text: str) -> str:
    """The page as a command prints it with training off."""
    return f"{text}\n\n{DISCLAIMER}\n"


def ran_to(tmp_path: Path, day: date, config: str = GOLDEN_CONFIG) -> Cli:
    """An account opened on the golden window's first day and run up to *day*."""
    cli = paper(tmp_path, config)
    assert run_on(cli, START).code == 0
    if day != START:
        done = run_on(cli, day, "--catch-up")
        assert done.code in (0, 3), done.err
    return replace(cli, now=at(day))


def halted(tmp_path: Path) -> Cli:
    """An account halted by the daily-loss limit on 2021-02-02, the day it is left on."""
    cli = paper(tmp_path, quiet(JUMPY))
    assert run_on(cli, START).code == 0
    assert run_on(cli, trading_days()[1]).code == 3
    return replace(cli, now=at(trading_days()[1]), env={"USER": "tester"})


def retired(cli: Cli) -> None:
    """Save the account as run by a strategy since removed, as a changed configuration leaves
    it (only ``buy-and-hold`` is registered)."""
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        assert account.state.memory
        moved = Account(account.opened_on, "retired", account.state, account.settings)
        assert store.save(moved, after=account.last_day)


# paper status (M5 spec §7.1).


def test_status_before_the_first_run_says_how_to_open_the_account(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    result = cli("paper", "status")
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: there is no paper account yet; run steadyhand-idx paper run first\n"
    )


def test_status_on_the_opening_day_shows_the_cash_and_the_orders_queued(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, START, quiet())
    result = cli("paper", "status")
    assert (result.code, result.err) == (0, "")
    assert result.out == page(
        "Paper account opened on 2021-02-01, running buy-and-hold; last day run 2021-02-01.\n"
        "\n"
        "Cash: IDR 100,000,000 settled, IDR 0 unsettled\n"
        "Holdings value: IDR 0\n"
        "Total value: IDR 100,000,000\n"
        "\n"
        "Holdings: none\n"
        "\n"
        "Queued for the next open:\n"
        "- buy 3300 ASII\n"
        "- buy 500 BBCA\n"
        "- buy 4500 BBRI\n"
        "- buy 6100 TLKM\n"
        "- buy 2800 UNVR\n"
        "\n"
        "Dividend entitlements: none\n"
        "\n"
        "Reinvestment-exemption claims: none\n"
        "\n"
        "Frozen stocks: none"
    )


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


def test_a_halted_account_shows_its_halt_and_the_resume_command_and_exits_0(
    tmp_path: Path,
) -> None:
    cli = halted(tmp_path)
    result = cli("paper", "status")
    assert (result.code, result.err) == (0, "")
    assert result.out.startswith(
        "Paper account opened on 2021-02-01, running buy-and-hold; last day run 2021-02-02.\n"
        "Halted on 2021-02-02: daily loss limit: the unit value fell 2.53%, the limit is 0.10%. "
        "No orders are placed until you resume it with: steadyhand-idx resume buy-and-hold\n"
        "\n"
    )


def test_status_lists_frozen_stocks_with_their_reasons() -> None:
    stock = Instrument("BBRI", "IDX", IDR)
    cash = Money(1_000, IDR)
    holdings = Holdings(
        Portfolio.empty(IDR).deposit(cash, START), frozen={stock: "suspended by the exchange"}
    )
    state = EngineState(holdings, last_day=START)
    report = paper_day(state)
    shown = status_page(Account(START, "buy-and-hold", state), report)
    assert "Frozen stocks:\n- BBRI: suspended by the exchange" in "\n".join(shown.lines)


def paper_day(state: EngineState) -> DayReport:
    """A saved report for *state*'s day with nothing in it but its cash."""
    assert state.last_day is not None
    cash = state.holdings.portfolio.cash_balance()
    nothing = Money(0, IDR)
    return DayReport(
        day=state.last_day,
        fills=(),
        rejected=(),
        cuts=(),
        queued=(),
        entitled=(),
        paid=(),
        tax=nothing,
        daily_cost=nothing,
        deposit=nothing,
        frozen=(),
        halt=None,
        settled=cash,
        unsettled=nothing,
        holdings_value=nothing,
        value=cash,
        unit_price=state.units.price,
        warnings=(),
    )


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


# report (M5 spec §7.2).


@pytest.mark.parametrize("extra", [(), ("--income",), ("--day", "2021-02-01")])
def test_report_before_the_first_run_says_how_to_open_the_account(
    tmp_path: Path, extra: tuple[str, ...]
) -> None:
    result = paper(tmp_path)("report", *extra)
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: there is no paper account yet; run steadyhand-idx paper run first\n"
    )


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


def test_a_days_report_shows_its_fills_its_blocked_orders_and_its_cash(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 2, 3), quiet(TIGHT))
    result = cli("report", "--day", "2021-02-02")
    assert (result.code, result.err) == (0, "")
    assert result.out == page(
        "Day report for 2021-02-02\n"
        "\n"
        "Fills:\n"
        "- buy 3100 ASII at IDR 6,175: IDR 19,142,500\n"
        "- buy 500 BBCA at IDR 34,875: IDR 17,437,500\n"
        "- buy 4300 BBRI at IDR 4,500: IDR 19,350,000\n"
        "- buy 5800 TLKM at IDR 3,310: IDR 19,198,000\n"
        "- buy 2700 UNVR at IDR 7,125: IDR 19,237,500\n"
        "\n"
        "Queued for the next open: none\n"
        "\n"
        "Blocked orders:\n"
        "- skipped: buy 100 ASII: already at the 19.00% limit per stock\n"
        "- skipped: buy 200 BBRI: already at the 19.00% limit per stock\n"
        "- skipped: buy 300 TLKM: already at the 19.00% limit per stock\n"
        "- skipped: buy 100 UNVR: already at the 19.00% limit per stock\n"
        "\n"
        "Cash: IDR 5,428,219 settled, IDR 0 unsettled\n"
        "Holdings value: IDR 92,136,500\n"
        "Total value: IDR 97,564,719\n"
        "Daily charges: IDR 10,000\n"
        "Deposit: IDR 0\n"
        "\n"
        "Holdings are shown for the latest day only, 2021-02-03: steadyhand-idx report\n"
        "\n"
        "Dividends paid: none\n"
        "Dividends earned: none\n"
        "Dividend tax: IDR 0"
    )


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


@pytest.mark.parametrize("day", ["2021-01-29", "2021-02-06", "2021-02-04"])
def test_a_day_with_no_saved_report_names_the_first_and_last_saved(
    tmp_path: Path, day: str
) -> None:
    cli = ran_to(tmp_path, date(2021, 2, 3))
    result = cli("report", "--day", day)
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        f"steadyhand-idx: there is no report for {day}; the saved days run from 2021-02-01 "
        "to 2021-02-03\n"
    )


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


def test_the_day_a_limit_halts_the_account_shows_the_halt(tmp_path: Path) -> None:
    result = halted(tmp_path)("report")
    assert result.code == 0
    assert (
        "\n\nHalted on 2021-02-02: daily loss limit: the unit value fell 2.53%, the limit is "
        "0.10%\n"
    ) in result.out


def test_a_days_frozen_stocks_warnings_and_notes_are_listed_with_their_keys() -> None:
    stock = Instrument("BBRI", "IDX", IDR)
    state = EngineState(Holdings(Portfolio.empty(IDR).deposit(Money(1_000, IDR), START)))
    report = replace(
        paper_day(replace(state, last_day=START)),
        frozen=((stock, "suspended by the exchange"),),
        warnings=(Note(DATA_BAR_REFUSED, "BBRI: the source refused the day"),),
        notes=(Note(CORPORATE_SPLIT_ORDER_CANCELLED, "BBRI: an order was cancelled"),),
    )
    shown = day_report_page(report, None)
    assert "\n".join(shown.lines).endswith(
        "\n\nFrozen stocks:\n- BBRI: suspended by the exchange"
        "\n\nWarnings:\n- BBRI: the source refused the day"
        "\n\nNotes:\n- BBRI: an order was cancelled"
    )
    assert shown.keys[-2:] == [DATA_BAR_REFUSED, CORPORATE_SPLIT_ORDER_CANCELLED]


# resume (M5 spec §7.3, core spec §6.1).


def test_resume_before_the_first_run_says_how_to_open_the_account(tmp_path: Path) -> None:
    result = paper(tmp_path)("resume", "buy-and-hold")
    assert (result.code, result.err) == (
        2,
        "steadyhand-idx: there is no paper account yet; run steadyhand-idx paper run first\n",
    )


def test_resume_must_name_the_accounts_strategy(tmp_path: Path) -> None:
    cli = halted(tmp_path)
    before = tables(cli)
    result = cli("resume", "momentum", stdin="resume\n")
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: the paper account runs buy-and-hold, not momentum; to resume it, run: "
        "steadyhand-idx resume buy-and-hold\n"
    )
    assert tables(cli) == before


def test_resume_when_nothing_is_halted_says_so_and_changes_nothing(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, START, quiet())
    before = tables(cli)
    result = cli("resume", "buy-and-hold", stdin="resume\n")
    assert (result.code, result.err) == (0, "")
    assert result.out == page("The paper account is not halted; there is nothing to resume.")
    assert tables(cli) == before


def test_a_typed_resume_clears_the_halt_and_the_next_day_orders_again(tmp_path: Path) -> None:
    cli = halted(tmp_path)
    result = cli("resume", "buy-and-hold", stdin="resume\n")
    assert (result.code, result.err) == (0, "")
    assert result.out == page(
        "The paper account halted on 2021-02-02: daily loss limit: the unit value fell 2.53%, "
        "the limit is 0.10%.\n"
        "Type resume to resume ordering: "
        "Resumed. From the next day run, the strategy's orders are placed again."
    )
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        assert account.state.halt is None
        line = store.audit()[-1]
    assert (line.day, line.note.key, line.note.text) == (
        trading_days()[1],
        PAPER_RESUMED,
        (
            "resumed ordering after the halt of 2021-02-02 (daily loss limit: the unit value "
            "fell 2.53%, the limit is 0.10%), by tester"
        ),
    )
    later = run_on(cli, trading_days()[2])
    assert later.code == 0, later.err
    with opened(cli) as store:
        assert store.runs()[-1].outcome is Outcome.RAN


def test_resume_names_who_resumed_from_logname_or_else_unknown(tmp_path: Path) -> None:
    cli = replace(halted(tmp_path), env={"LOGNAME": "operator"})
    assert cli("resume", "buy-and-hold", stdin="resume\n").code == 0
    with opened(cli) as store:
        assert store.audit()[-1].note.text.endswith(", by operator")
    again = halted(tmp_path / "again")
    assert replace(again, env={})("resume", "buy-and-hold", stdin="resume\n").code == 0
    with opened(again) as store:
        assert store.audit()[-1].note.text.endswith(", by unknown")
    both = replace(halted(tmp_path / "both"), env={"USER": "tester", "LOGNAME": "operator"})
    assert both("resume", "buy-and-hold", stdin="resume\n").code == 0
    with opened(both) as store:
        assert store.audit()[-1].note.text.endswith(", by tester")


@pytest.mark.parametrize("answer", ["", "\n", "yes\n", "Resume\n", " resume\n"])
def test_any_other_answer_leaves_the_halt_in_place(tmp_path: Path, answer: str) -> None:
    cli = halted(tmp_path)
    before = tables(cli)
    result = cli("resume", "buy-and-hold", stdin=answer)
    assert result.code == 2
    assert result.err == (
        f"steadyhand-idx: you typed {answer.rstrip(chr(10))!r}, not 'resume'; nothing was changed\n"
    )
    assert tables(cli) == before


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


def drawn_down() -> tuple[Account, Halt]:
    """An account halted by the drawdown kill switch whose unit value is 5.00% below its
    high-water mark."""
    halt = Halt(START, Note(RISK_HALT_DRAWDOWN, "drawdown kill switch"))
    cash = Portfolio.empty(IDR).deposit(Money(1_000, IDR), START)
    units = UnitValue(Decimal(1_000), Decimal("0.95"), Decimal(1))
    return Account(START, "buy-and-hold", EngineState(Holdings(cash), units, halt, START)), halt


@pytest.mark.parametrize("limit", ["0.0499", "0.05"])
def test_resume_is_refused_at_or_past_the_drawdown_limit(limit: str) -> None:
    account, _halt = drawn_down()
    with pytest.raises(HaltCausePresentError, match=r"still 5\.00% below"):
        check_resume(account, "buy-and-hold", RiskLimits(max_drawdown=Decimal(limit)))


def test_resume_is_allowed_just_inside_the_drawdown_limit() -> None:
    account, halt = drawn_down()
    assert check_resume(account, "buy-and-hold", RiskLimits(max_drawdown=Decimal("0.0501"))) == halt


class RacingScreen(io.StringIO):
    """A terminal on which, once the question is shown, another ``paper run`` saves a day
    before the answer is typed: the account changes between the question and the answer."""

    def __init__(self, other: Cli) -> None:
        super().__init__()
        self._other = other
        self.raced = False

    def flush(self) -> None:
        if not self.raced:
            self.raced = True
            assert self._other("paper", "run").code == 3
        super().flush()


def test_an_account_changed_while_asking_is_left_as_the_other_run_saved_it(
    tmp_path: Path,
) -> None:
    cli = halted(tmp_path)
    other = replace(cli, now=at(trading_days()[2]))
    screen, err = RacingScreen(other), io.StringIO()
    env = {"STEADYHAND_HOME": str(cli.home)}
    answer = io.StringIO("resume\n")
    world = World(answer, screen, err, env, lambda: cli.now, recorded_source)
    assert main(["resume", "buy-and-hold"], world) == 3
    assert screen.raced
    assert err.getvalue() == (
        "steadyhand-idx: another paper run saved a day while you were answering; nothing was "
        "changed, run the command again\n"
    )
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        assert account.last_day == trading_days()[2]
        assert account.state.halt is not None
        assert PAPER_RESUMED not in [line.note.key for line in store.audit()]


# paper switch (M5 spec §7.3).


def test_switch_before_the_first_run_says_how_to_open_the_account(tmp_path: Path) -> None:
    result = paper(tmp_path)("paper", "switch", "buy-and-hold")
    assert (result.code, result.err) == (
        2,
        "steadyhand-idx: there is no paper account yet; run steadyhand-idx paper run first\n",
    )


def test_switch_must_name_the_configured_strategy(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, START)
    retired(cli)
    before = tables(cli)
    result = cli("paper", "switch", "momentum", stdin="momentum\n")
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: steadyhand.toml names the strategy buy-and-hold, not momentum; edit "
        "[strategy] name first, then run: steadyhand-idx paper switch momentum\n"
    )
    assert tables(cli) == before


def test_switch_to_the_strategy_already_running_is_refused(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, START)
    before = tables(cli)
    result = cli("paper", "switch", "buy-and-hold", stdin="buy-and-hold\n")
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: the paper account already runs buy-and-hold; there is nothing to switch\n"
    )
    assert tables(cli) == before


def test_switch_is_refused_while_the_account_is_halted(tmp_path: Path) -> None:
    cli = halted(tmp_path)
    retired(cli)
    before = tables(cli)
    result = cli("paper", "switch", "buy-and-hold", stdin="buy-and-hold\n")
    assert (result.code, result.out) == (3, "")
    assert result.err == (
        "steadyhand-idx: the paper account halted on 2021-02-02: daily loss limit: the unit "
        "value fell 2.53%, the limit is 0.10%; no orders are placed until you resume it with: "
        "steadyhand-idx resume retired\n"
    )
    assert tables(cli) == before


def test_a_typed_switch_keeps_the_holdings_and_cash_and_clears_the_memory(
    tmp_path: Path,
) -> None:
    cli = replace(ran_to(tmp_path, trading_days()[1], quiet()), env={"USER": "tester"})
    retired(cli)
    with opened(cli) as store:
        before = store.account()
        assert before is not None
    result = cli("paper", "switch", "buy-and-hold", stdin="buy-and-hold\n")
    assert (result.code, result.err) == (0, "")
    assert result.out == page(
        "The paper account runs retired; steadyhand.toml names buy-and-hold.\n"
        "Switching keeps the holdings and the cash and clears what retired remembered; "
        "buy-and-hold trades from the next day run.\n"
        "Type buy-and-hold to switch: "
        "Switched the paper account to buy-and-hold."
    )
    with opened(cli) as store:
        after = store.account()
        assert after is not None
        line = store.audit()[-1]
    assert after.strategy == "buy-and-hold"
    assert after.state.memory == {}
    assert after.state.holdings == before.state.holdings
    assert after.state.units == before.state.units
    assert (after.last_day, after.settings) == (before.last_day, before.settings)
    assert (line.day, line.note.key, line.note.text) == (
        trading_days()[1],
        PAPER_STRATEGY_SWITCHED,
        (
            "switched the strategy from retired to buy-and-hold, keeping the holdings and the "
            "cash, by tester"
        ),
    )
    assert run_on(cli, trading_days()[2]).code == 0


@pytest.mark.parametrize("answer", ["", "yes\n", "retired\n"])
def test_any_other_answer_leaves_the_strategy_as_it_was(tmp_path: Path, answer: str) -> None:
    cli = ran_to(tmp_path, START)
    retired(cli)
    before = tables(cli)
    result = cli("paper", "switch", "buy-and-hold", stdin=answer)
    assert result.code == 2
    assert result.err == (
        f"steadyhand-idx: you typed {answer.rstrip(chr(10))!r}, not 'buy-and-hold'; nothing was "
        "changed\n"
    )
    assert tables(cli) == before
