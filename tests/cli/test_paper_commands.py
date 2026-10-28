"""``paper status``, ``report``, ``resume`` and ``paper switch`` (M5 spec §7, §9.2).

Each command runs through ``main`` over an account that ``paper run`` built from the recorded
Yahoo answers, in a temporary data directory, at a fixed time in Jakarta. Pages are compared
whole with training off, so a figure that moves or a line that goes missing is seen; the keys
each page names are checked on the page itself.
"""

import io
import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from cli_world import (
    EXEMPT,
    TIGHT,
    Cli,
    at,
    halted,
    names_held,
    opened,
    page,
    paper,
    planted,
    quiet,
    ran_to,
    recorded_source,
    run_from,
    run_on,
    tables,
    trading_days,
)
from record_golden import START
from short_world import SHORT_CONFIG, cached, library_run, short_cli
from short_world import START as SHORT_START
from short_world import WEEK_END as SHORT_WEEK_END
from short_world import trading_days as short_trading_days

from steadyhand import (
    CLAIMS_LABEL,
    CORPORATE_SPLIT_ORDER_CANCELLED,
    DATA_BAR_REFUSED,
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
from steadyhand_idx import CachedDataSource
from steadyhand_idx.cli import World, main
from steadyhand_idx.notes import PAPER_ORDER_SKIPPED, PAPER_RESUMED, PAPER_STRATEGY_SWITCHED
from steadyhand_idx.paper import HaltCausePresentError, check_resume
from steadyhand_idx.paper_pages import day_report_page, income_page, status_page
from steadyhand_idx.state import STATE_FILE, Account, Outcome


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
            "fell 2.53%, the limit is 0.10%)"
        ),
    )
    later = run_on(cli, trading_days()[2])
    assert later.code == 0, later.err
    with opened(cli) as store:
        assert store.runs()[-1].outcome is Outcome.RAN


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
    before the answer is typed: the account changes between the question and the answer.
    ``resume`` asks one question, and the CLI flushes only to show a question (``ask``), so a
    second flush is a second question this race was never written for. ``main`` turns an error
    raised here into its exit code 1, so the test reads ``questions`` before the exit code."""

    def __init__(self, other: Cli) -> None:
        super().__init__()
        self._other = other
        self.questions = 0

    def flush(self) -> None:
        self.questions += 1
        assert self.questions == 1, "resume showed a second question"
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
    code = main(["resume", "buy-and-hold"], world)
    assert screen.questions == 1, "the race ran once, on resume's one question"
    assert code == 3
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
    cli = ran_to(tmp_path, trading_days()[1], quiet())
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
        ("switched the strategy from retired to buy-and-hold, keeping the holdings and the cash"),
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


# The stand-ins of the golden-window tests moved to tests/integration/cli/
# test_paper_commands_golden.py (#292): each of the same name, over the made-up window.

SHORT_RISK = '[risk]\nmax_weight = "0.35"\n'
SHORT_TIGHT = SHORT_CONFIG.replace(SHORT_RISK, '[risk]\nmax_weight = "0.30"\n')
"""A 30% limit per stock, under buy-and-hold's third of each of the three: its first orders are
cut to the limit and its later top-ups skipped."""
SHORT_DEEP = SHORT_CONFIG.replace(SHORT_RISK, SHORT_RISK + 'max_drawdown = "0.003"\n')
"""A drawdown limit breached on 2021-12-20: 0.45% below, rounded down as every limit is written."""
SHORT_JUMPY = SHORT_CONFIG.replace(SHORT_RISK, SHORT_RISK + 'daily_loss_limit = "0.001"\n')
"""A daily-loss limit the made-up window's second day breaches."""


def short_ran_to(tmp_path: Path, day: date, config: str = SHORT_CONFIG) -> Cli:
    """An account opened on the made-up window's first day and run up to *day*."""
    return run_from(short_cli(tmp_path / "home", config), SHORT_START, day)


def saved_account(
    tmp_path: Path,
    day: date,
    config: str = SHORT_CONFIG,
    *,
    exemption: bool = False,
    max_weight: str = "0.35",
    daily_loss: str = "0.05",
) -> Cli:
    """An account saved as ``paper run`` leaves it on *day*, with every day's report, built by the
    library's backtest of the same days with the exemption and limits that *config* sets (passed
    again here): ``test_paper_run.py`` proves the two end alike, and a page test then pays for
    its one command, not for a paper run of every day up to *day*."""
    cli = short_cli(tmp_path / "home", config)
    result = library_run(end=day, exemption=exemption, max_weight=max_weight, daily_loss=daily_loss)
    account = Account(SHORT_START, result.run.strategy, result.run.final)
    with opened(cli) as store:
        after = None
        for report in result.run.reports:  # runtime population: the days the run saved
            assert store.save(account, after=after, report=report)
            after = account.last_day
    return replace(cli, now=at(day))


def test_status_shows_each_holding_with_its_last_close_value_and_weight(tmp_path: Path) -> None:
    cli = saved_account(tmp_path, date(2022, 1, 10), quiet(SHORT_CONFIG))
    result = cli("paper", "status")
    assert result.code == 0
    assert (
        "Cash: IDR 494,515 settled, IDR 0 unsettled\n"
        "Holdings value: IDR 103,246,500\n"
        "Total value: IDR 103,741,015\n"
        "\n"
        "Holdings:\n"
        "Stock  Quantity  Last close           Value  Weight\n"
        "XAAA      33700   IDR 1,045  IDR 35,216,500  33.95%\n"
        "XBBB      16500   IDR 2,065  IDR 34,072,500  32.84%\n"
        "XCCC       4700   IDR 7,225  IDR 33,957,500  32.73%\n"
        "\n"
        "Queued for the next open:\n"
        "- buy 100 XAAA\n"
    ) in result.out


def test_status_shows_a_dividend_entitlement_until_it_is_paid(tmp_path: Path) -> None:
    cli = short_ran_to(tmp_path, date(2021, 12, 17), quiet(SHORT_CONFIG))
    result = cli("paper", "status")
    assert (
        "Dividend entitlements:\n"
        "- XAAA: IDR 825,000 before tax, ex-date 2021-12-17, paid on 2022-01-07\n"
    ) in result.out


def test_status_shows_open_claims_under_their_label(tmp_path: Path) -> None:
    cli = saved_account(tmp_path, date(2022, 1, 7), quiet(SHORT_CONFIG + EXEMPT), exemption=True)
    result = cli("paper", "status")
    assert "Dividend entitlements: none\n" in result.out
    assert (
        f"Reinvestment-exemption claims ({CLAIMS_LABEL}):\n"
        "- XAAA: IDR 825,000 paid on 2022-01-07, IDR 825,000 still to reinvest by 2022-03-31\n"
    ) in result.out


def test_a_claims_reinvested_parts_are_shown_with_how_long_each_is_protected(
    tmp_path: Path,
) -> None:
    cli = saved_account(tmp_path, date(2022, 1, 10), quiet(SHORT_CONFIG + EXEMPT), exemption=True)
    result = cli("paper", "status")
    assert (
        "- XAAA: IDR 825,000 paid on 2022-01-07, IDR 305,500 still to reinvest by 2022-03-31, "
        "IDR 313,500 protected until 2024-12-31, IDR 206,000 protected until 2024-12-31\n"
    ) in result.out
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        report = store.report(account.last_day)
        assert report is not None
    assert FIGURES["Protection.amount"] in status_page(account, report).keys


def test_the_status_page_names_every_figure_it_shows(tmp_path: Path) -> None:
    cli = saved_account(tmp_path, date(2022, 1, 10), SHORT_CONFIG + EXEMPT, exemption=True)
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
    cli = saved_account(tmp_path, SHORT_WEEK_END, quiet(SHORT_CONFIG))
    result = cli("report")
    assert (result.code, result.err) == (0, "")
    assert result.out.startswith("Day report for 2021-12-21\n\n")
    assert (
        "Holdings:\n"
        "Stock  Quantity  Last close           Value  Weight\n"
        "XAAA      33400   IDR 1,020  IDR 34,068,000  33.67%\n"
    ) in result.out


def test_a_blocked_order_is_shown_with_its_reason_and_the_dividends_of_the_day(
    tmp_path: Path,
) -> None:
    cli = saved_account(tmp_path, date(2022, 1, 7), quiet(SHORT_TIGHT), max_weight="0.30")
    result = cli("report", "--day", "2022-01-07")
    assert result.code == 0
    assert (
        "Queued for the next open:\n"
        "- buy 100 XBBB\n"
        "\n"
        "Blocked orders:\n"
        "- cut: buy XBBB from 1700 to 100 shares: cut to the 30.00% limit per stock\n"
        "- skipped: buy 3500 XAAA: already at the 30.00% limit per stock\n"
        "- skipped: buy 500 XCCC: already at the 30.00% limit per stock\n"
    ) in result.out
    assert "Dividends paid:\n- XAAA: IDR 742,500 before tax\n" in result.out


def test_the_skipped_order_is_in_the_audit_log_under_its_key(tmp_path: Path) -> None:
    cli = short_ran_to(tmp_path, date(2021, 12, 17), SHORT_TIGHT)
    with opened(cli) as store:
        first = next(line for line in store.audit() if line.note.key == PAPER_ORDER_SKIPPED)
    assert (first.day, first.note.text) == (
        date(2021, 12, 16),
        "skipped: buy 800 XBBB: already at the 30.00% limit per stock",
    )


def test_a_report_names_the_key_of_each_blocked_orders_reason(tmp_path: Path) -> None:
    cli = short_ran_to(tmp_path, date(2021, 12, 17), SHORT_TIGHT)
    with opened(cli) as store:
        cut, skipped = store.report(SHORT_START), store.report(date(2021, 12, 17))
    assert cut is not None
    assert skipped is not None
    assert LIMIT_WEIGHT_CUT in day_report_page(cut, None).keys
    assert LIMIT_WEIGHT_FULL in day_report_page(skipped, None).keys


def test_the_income_report_is_the_backtests_over_the_same_days(tmp_path: Path) -> None:
    cli = saved_account(tmp_path, SHORT_WEEK_END, quiet(SHORT_CONFIG))
    result = cli("report", "--income")
    assert (result.code, result.err) == (0, "")
    reference = library_run(end=SHORT_WEEK_END).run.income
    assert reference is not None
    assert result.out == page("\n".join(income_page(reference).lines))
    # XAAA's dividend is entitled, not yet paid: nothing received, a run-rate from what is held.
    assert "Goal: IDR 2,000 a month\nReceived: IDR 0 a month, 0.00% of the goal\n" in result.out
    assert f"\n\n{PROJECTION_LABEL}:\n" in result.out


def test_resume_writes_no_login_name_anywhere_in_the_state_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    second = short_trading_days()[1]
    saved = saved_account(tmp_path, second, quiet(SHORT_JUMPY), daily_loss="0.001")
    cli = planted(saved, monkeypatch)
    assert cli("resume", "buy-and-hold", stdin="resume\n").code == 0
    assert names_held(cli, "resumed ordering after the halt of ") == []


def test_switch_writes_no_login_name_anywhere_in_the_state_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = planted(ran_to(tmp_path, trading_days()[1], quiet()), monkeypatch)
    retired(cli)
    assert cli("paper", "switch", "buy-and-hold", stdin="buy-and-hold\n").code == 0
    assert names_held(cli, "switched the strategy from retired to buy-and-hold") == []


def test_a_resume_line_naming_its_user_from_an_older_release_still_reads(tmp_path: Path) -> None:
    # Releases before #341 ended the line with ", by <login name>". The audit is append-only, so
    # no migration rewrites it: the line stays as written and the account still opens.
    second = short_trading_days()[1]
    cli = saved_account(tmp_path, second, quiet(SHORT_JUMPY), daily_loss="0.001")
    old = "resumed ordering after the halt of 2021-02-02 (a halt), by tester"
    with closing(sqlite3.connect(cli.home / STATE_FILE)) as database, database:
        database.execute(
            "INSERT INTO audit (day, key, line) VALUES (?, ?, ?)",
            (second.isoformat(), PAPER_RESUMED, old),
        )
    status = cli("paper", "status")
    assert (status.code, status.err) == (0, "")
    with opened(cli) as store:
        line = store.audit()[-1]
    assert (line.day, line.note.key, line.note.text) == (second, PAPER_RESUMED, old)


def test_resume_is_refused_while_the_drawdown_is_still_past_its_limit(tmp_path: Path) -> None:
    cli = short_ran_to(tmp_path, date(2021, 12, 20), quiet(SHORT_DEEP))
    before = tables(cli)
    result = cli("resume", "buy-and-hold", stdin="resume\n")
    assert (result.code, result.out) == (3, "")
    assert result.err == (
        "steadyhand-idx: the unit value is still 0.45% below its high-water mark, at or past "
        "the 0.30% drawdown limit; the halt stays until it recovers or you raise "
        "risk.max_drawdown\n"
    )
    assert tables(cli) == before
    raised = SHORT_DEEP.replace('max_drawdown = "0.003"', 'max_drawdown = "0.005"')
    cli.config.write_text(quiet(raised), encoding="utf-8")
    assert cli("resume", "buy-and-hold", stdin="resume\n").code == 0
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        assert account.state.halt is None
        assert store.audit()[-1].note.key == PAPER_RESUMED


def test_the_short_worlds_cached_source_opens_its_cache_in_the_folder(tmp_path: Path) -> None:
    """The made-up answers through the real cache, built (and its cache file made) without a
    read: every member of the short world runs in some test (#374)."""
    with cached(tmp_path) as source:
        assert isinstance(source, CachedDataSource)
    assert (tmp_path / "cache.sqlite").is_file()
