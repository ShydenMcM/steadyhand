"""``paper run``: which days it runs, what it saves, and how it stops (M5 spec §6, §9.2).

Every run goes through ``main`` with the recorded Yahoo answers, the real bar cache and the real
state database in a temporary data directory, at a fixed time in Jakarta.
"""

import multiprocessing
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from cli_world import (
    GOLDEN_CONFIG,
    GROWTH_CONFIG,
    at,
    golden_backtest,
    opened,
    paper,
    paper_process,
    recorded_source,
    rules,
    run_on,
    tables,
    trading_days,
)
from record_golden import END, START

from steadyhand import (
    IDR,
    RISK_HALT_DAILY_LOSS,
    Bar,
    CorporateAction,
    DataSource,
    Instrument,
    Market,
    Money,
    Note,
    day_inputs,
)
from steadyhand_idx.cli import SourceFactory
from steadyhand_idx.config import load
from steadyhand_idx.notes import (
    PAPER_ACCOUNT_OPENED,
    PAPER_ORDER_QUEUED,
    PAPER_RUN_STOPPED,
    PAPER_SETTING_CHANGED,
    PAPER_SETTING_STARTING_CASH_IGNORED,
)
from steadyhand_idx.paper import CATCH_UP_CAP, CLOSE, days_to_run, settings_of, target_day
from steadyhand_idx.state import STATE_FILE, Account, Outcome
from steadyhand_idx.universe import Exclusions, Lq45Membership, Lq45Universe

# Which day is the target (M5 spec §6.1).


@pytest.mark.parametrize(
    ("now", "target"),
    [
        (at(date(2021, 2, 1), 16, 29, 59), date(2021, 1, 29)),
        (at(date(2021, 2, 1), 16, 30, 0), date(2021, 2, 1)),
        (datetime(2021, 2, 1, 9, 30, tzinfo=UTC), date(2021, 2, 1)),
        (at(date(2021, 2, 6), 16, 29, 59), date(2021, 2, 5)),
        (at(date(2021, 2, 6), 16, 30, 0), date(2021, 2, 5)),
        (at(date(2021, 2, 12), 16, 29, 59), date(2021, 2, 11)),
        (at(date(2021, 2, 12), 16, 30, 0), date(2021, 2, 11)),
        (at(date(2021, 2, 15), 9, 0), date(2021, 2, 11)),
    ],
    ids=[
        "Monday before 16:30",
        "Monday at 16:30",
        "Monday at 16:30 given in UTC",
        "Saturday before 16:30",
        "Saturday at 16:30",
        "Chinese New Year before 16:30",
        "Chinese New Year at 16:30",
        "Monday morning after the holiday",
    ],
)
def test_the_target_is_the_latest_completed_trading_day(now: datetime, target: date) -> None:
    assert CLOSE.isoformat() == "16:30:00"
    assert not rules().is_trading_day(date(2021, 2, 6))
    assert not rules().is_trading_day(date(2021, 2, 12))
    assert target_day(now, rules()) == target


def test_the_days_to_run_are_the_trading_days_after_the_last_one_run() -> None:
    assert days_to_run(None, date(2021, 2, 1), rules()) == (date(2021, 2, 1),)
    assert days_to_run(date(2021, 2, 11), date(2021, 2, 16), rules()) == (
        date(2021, 2, 15),
        date(2021, 2, 16),
    )
    assert days_to_run(date(2021, 2, 16), date(2021, 2, 16), rules()) == ()


# The first run, and running twice (M5 spec §6.1, §9.2 "Idempotency").


def test_the_first_run_opens_the_account_on_the_target_day_and_runs_it(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    result = run_on(cli, START)
    assert result.code == 0, result.err
    assert result.out.startswith(
        "2021-02-01: 0 fill(s), 5 order(s) queued, value IDR 100,000,000\n\n"
        "Ran 1 day(s): 2021-02-01. Read a day's report with: steadyhand-idx report\n"
    )
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        assert (account.opened_on, account.strategy, account.last_day) == (
            START,
            "buy-and-hold",
            START,
        )
        assert account.settings == settings_of(load(cli.config))
        lines = [(line.day, line.note.key, line.note.text) for line in store.audit()]
        assert lines[0] == (
            START,
            PAPER_ACCOUNT_OPENED,
            (
                "opened the paper account on 2021-02-01 with IDR 100,000,000 and the "
                "buy-and-hold strategy"
            ),
        )
        assert lines[1:] == [
            (START, PAPER_ORDER_QUEUED, f"queued: buy {order} at the next open")
            for order in ("3300 ASII", "500 BBCA", "4500 BBRI", "6100 TLKM", "2800 UNVR")
        ]
        assert [(run.outcome, run.target, run.days) for run in store.runs()] == [
            (Outcome.RAN, START, (START,))
        ]


def test_running_twice_changes_nothing_but_the_run_log(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    assert run_on(cli, START).code == 0
    before = tables(cli)
    again = run_on(cli, START)
    assert (again.code, again.err) == (0, "")
    assert again.out.startswith("already up to date for 2021-02-01\n")
    assert tables(cli) == before
    with opened(cli) as store:
        assert [(run.outcome, run.days, run.detail) for run in store.runs()] == [
            (Outcome.RAN, (START,), "ran 1 day(s)"),
            (Outcome.UP_TO_DATE, (), "already up to date for 2021-02-01"),
        ]


def test_missed_days_are_caught_up_in_order_each_saved(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    result = run_on(cli, trading_days()[2])
    assert result.code == 0, result.err
    assert result.out.startswith(
        "2021-02-02: 5 fill(s), 0 order(s) queued, value IDR 97,464,230\n"
        "2021-02-03: 0 fill(s), 0 order(s) queued, value IDR 98,501,230\n"
    )
    with opened(cli) as store:
        assert store.days() == trading_days()[:3]
        caught_up = store.report(trading_days()[1])
    assert caught_up is not None
    assert [fill.order.instrument.symbol for fill in caught_up.fills] == [
        "ASII",
        "BBCA",
        "BBRI",
        "TLKM",
        "UNVR",
    ]


# The catch-up cap (M5 spec §6.1, §9.2).


def test_thirty_days_to_run_proceed(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    result = run_on(cli, trading_days()[CATCH_UP_CAP])
    assert result.code == 0, result.err
    with opened(cli) as store:
        assert store.days() == trading_days()[: CATCH_UP_CAP + 1]


def test_thirty_one_days_to_run_are_refused_and_nothing_is_written(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    before = tables(cli)
    result = run_on(cli, trading_days()[CATCH_UP_CAP + 1])
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: 31 trading days to run since 2021-02-01, more than 30; run "
        "steadyhand-idx paper run --catch-up to run them all\n"
    )
    assert tables(cli) == before
    with opened(cli) as store:
        assert len(store.runs()) == 1


def test_thirty_one_days_to_run_proceed_with_catch_up(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    result = run_on(cli, trading_days()[CATCH_UP_CAP + 1], "--catch-up")
    assert result.code == 0, result.err
    with opened(cli) as store:
        assert store.days() == trading_days()[: CATCH_UP_CAP + 2]


# The golden invariant (M5 spec §6.2, §9.2).


def test_a_paper_account_run_day_by_day_ends_where_the_backtest_does(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    days = trading_days()[:12]
    for day in days:
        assert run_on(cli, day).code == 0
    expected = golden_backtest(cli, days[-1]).run
    with opened(cli) as store:
        assert store.reports() == expected.reports
        account = store.account()
        assert account is not None
        assert account.state == expected.final


def test_a_year_caught_up_in_one_run_ends_where_the_backtest_does(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    result = run_on(cli, END, "--catch-up")
    assert result.code == 0, result.err
    expected = golden_backtest(cli, END).run
    assert len(expected.reports) == len(trading_days()) == 248
    with opened(cli) as store:
        assert store.reports() == expected.reports
        account = store.account()
        assert account is not None
        assert account.state == expected.final


def test_the_public_fetch_gives_each_trading_day_its_inputs_oldest_first(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    config = load(cli.config)
    universe = Lq45Universe(
        Lq45Membership.load(config.lq45_members), Exclusions.load(config.exclusions)
    )
    with recorded_source(cli.home) as source:
        market = Market(universe, source, rules())
        inputs = day_inputs(market, START, trading_days()[4])
        with pytest.raises(
            ValueError, match=r"^the range ends on 2021-01-31, before it starts on 2021-02-01$"
        ):
            day_inputs(market, START, date(2021, 1, 31))
    assert [found.day for found in inputs] == list(trading_days()[:5])
    assert all(found.members == universe.members_on(found.day) for found in inputs)


# Refusals (M5 spec §6.5, §8.1).


def test_a_changed_strategy_is_refused_naming_both_and_the_switch_command(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        retired = Account(account.opened_on, "retired", account.state, account.settings)
        assert store.save(retired, after=START)
    before = tables(cli)
    result = run_on(cli, trading_days()[1])
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: steadyhand.toml names the strategy buy-and-hold, but the paper account "
        "runs retired; to change it, run: steadyhand-idx paper switch buy-and-hold\n"
    )
    assert tables(cli) == before


def test_a_file_without_a_strategy_name_now_means_dividend_growth_so_paper_refuses(
    tmp_path: Path,
) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    # Without [strategy] name a file meant buy-and-hold before M6; it now means the new default.
    unnamed = GOLDEN_CONFIG.replace('name = "buy-and-hold"\n', "")
    assert unnamed != GOLDEN_CONFIG
    cli.config.write_text(unnamed, encoding="utf-8")
    before = tables(cli)
    result = run_on(cli, trading_days()[1])
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: steadyhand.toml names the strategy dividend-growth, but the paper account "
        "runs buy-and-hold; to change it, run: steadyhand-idx paper switch dividend-growth\n"
    )
    assert tables(cli) == before


def test_paper_needs_a_command(tmp_path: Path) -> None:
    result = paper(tmp_path)("paper")
    assert result.code == 2
    assert result.err.startswith("steadyhand-idx: the following arguments are required: command")


# Stops (M5 spec §6.5, §11).


@dataclass(frozen=True, slots=True)
class Edited:
    """The recorded data with each bar passed through ``edit``, which may drop it."""

    inner: DataSource
    edit: Callable[[Bar], Bar | None]

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        edited = (self.edit(bar) for bar in self.inner.bars(instrument, start, end))
        return [bar for bar in edited if bar is not None]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return self.inner.corporate_actions(instrument, start, end)

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> Sequence[Note]:
        return ()


def edited(edit: Callable[[Bar], Bar | None]) -> SourceFactory:
    @contextmanager
    def source(folder: Path) -> Iterator[DataSource]:
        with recorded_source(folder) as recorded:
            yield Edited(recorded, edit)

    return source


def doubling(symbol: str, day: date) -> SourceFactory:
    """One stock's close doubled on one day: an impossible price."""
    return edited(
        lambda bar: (
            replace(bar, high=bar.close * 2, close=bar.close * 2)
            if (bar.instrument.symbol, bar.day) == (symbol, day)
            else bar
        )
    )


def unpublished(day: date) -> SourceFactory:
    """No bar at all on *day*, as when Yahoo has not yet published the close (M5 spec §11)."""
    return edited(lambda bar: None if bar.day == day else bar)


def test_an_impossible_price_stops_the_run_keeping_the_days_before_it(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    bad = trading_days()[3]
    result = run_on(replace(cli, source=doubling("BBCA", bad)), trading_days()[4])
    assert result.code == 3
    assert result.err.startswith(f"steadyhand-idx: BBCA on {bad}: the close ")
    with opened(cli) as store:
        assert store.days() == trading_days()[:3]
        runs = store.runs()
        assert (runs[-1].outcome, runs[-1].days) == (Outcome.STOPPED, trading_days()[1:3])
        stop = store.audit()[-1]
        assert (stop.day, stop.note.key) == (bad, PAPER_RUN_STOPPED)
        assert stop.note.text.startswith(f"stopped on {bad}: BBCA on {bad}: the close ")
    assert run_on(cli, trading_days()[4]).code == 0
    with opened(cli) as store:
        assert store.days() == trading_days()[:5]


def test_a_day_the_source_has_not_published_stops_the_run(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    first = run_on(replace(cli, source=unpublished(START)), START)
    assert (first.code, first.out) == (3, "")
    assert first.err == (
        "steadyhand-idx: the data source has no bars for 2021-02-01 yet, so nothing was run for "
        "it; run paper run again later\n"
    )
    with opened(cli) as store:
        assert store.account() is None
        assert [(run.outcome, run.days) for run in store.runs()] == [(Outcome.STOPPED, ())]
        assert [(line.day, line.note.key) for line in store.audit()] == [(START, PAPER_RUN_STOPPED)]
    assert run_on(cli, START).code == 0
    late = trading_days()[2]
    assert run_on(replace(cli, source=unpublished(late)), late).code == 3
    with opened(cli) as store:
        assert store.days() == trading_days()[:2]
        assert store.runs()[-1].days == trading_days()[1:2]
    assert run_on(cli, late).code == 0


# Halts (M5 spec §6.5).

JUMPY_CONFIG = GOLDEN_CONFIG.replace(
    '[risk]\nmax_weight = "0.25"\n', '[risk]\nmax_weight = "0.25"\ndaily_loss_limit = "0.001"\n'
)


def test_a_halt_is_saved_with_its_day_and_every_later_run_exits_3(tmp_path: Path) -> None:
    assert JUMPY_CONFIG != GOLDEN_CONFIG
    cli = paper(tmp_path, JUMPY_CONFIG)
    assert run_on(cli, START).code == 0
    halted = run_on(cli, trading_days()[1])
    assert halted.code == 3
    assert halted.out.startswith("2021-02-02: 5 fill(s), 0 order(s) queued")
    assert halted.err == (
        "steadyhand-idx: the paper account halted on 2021-02-02: daily loss limit: the unit "
        "value fell 2.53%, the limit is 0.10%; no orders are placed until you resume it with: "
        "steadyhand-idx resume buy-and-hold\n"
    )
    with opened(cli) as store:
        halt = store.audit()[-1]
        assert (halt.day, halt.note.key) == (trading_days()[1], RISK_HALT_DAILY_LOSS)
    later = run_on(cli, trading_days()[2])
    assert later.code == 3
    assert later.out.startswith("2021-02-03: 0 fill(s), 0 order(s) queued")
    assert run_on(cli, trading_days()[2]).code == 3
    with opened(cli) as store:
        assert store.days() == trading_days()[:3]
        assert [run.outcome for run in store.runs()] == [
            Outcome.RAN,
            Outcome.HALTED,
            Outcome.HALTED,
            Outcome.HALTED,
        ]


# Configuration changes (M5 spec §6.5).


def test_a_changed_setting_is_written_in_the_audit_log_and_applies_from_the_next_day(
    tmp_path: Path,
) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    cli.config.write_text(
        GOLDEN_CONFIG.replace('max_weight = "0.25"', 'max_weight = "0.20"'), encoding="utf-8"
    )
    run_on(cli, trading_days()[1])
    with opened(cli) as store:
        changed = [line for line in store.audit() if line.note.key == PAPER_SETTING_CHANGED]
        assert [(line.day, line.note.text) for line in changed] == [
            (
                trading_days()[1],
                "risk.max_weight changed from 0.25 to 0.20; it applies from 2021-02-02",
            )
        ]
        account = store.account()
        assert account is not None
        assert account.settings["risk.max_weight"] == "0.20"


def test_a_changed_starting_cash_is_noted_once_and_changes_nothing(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    cli.config.write_text(
        GOLDEN_CONFIG.replace("starting_cash_idr = 100_000_000", "starting_cash_idr = 200_000_000"),
        encoding="utf-8",
    )
    run_on(cli, trading_days()[1])
    run_on(cli, trading_days()[2])
    expected = golden_backtest(paper(tmp_path / "unchanged"), trading_days()[2]).run
    with opened(cli) as store:
        ignored = [
            line for line in store.audit() if line.note.key == PAPER_SETTING_STARTING_CASH_IGNORED
        ]
        assert [(line.day, line.note.text) for line in ignored] == [
            (
                trading_days()[1],
                (
                    "account.starting_cash_idr changed from 100000000 to 200000000; it is used "
                    "only when the account opens, so the account's cash is unchanged"
                ),
            )
        ]
        assert store.reports() == expected.reports


def test_the_settings_a_day_ran_with_are_recorded_by_configuration_key(tmp_path: Path) -> None:
    config = load(paper(tmp_path).config)
    assert settings_of(config) == {
        "account.starting_cash_idr": "100000000",
        "account.monthly_contribution_idr": "0",
        "account.broker_fees": "custom",
        "goal.monthly_income_target_idr": "1000000",
        "risk.max_weight": "0.25",
        "risk.daily_loss_limit": "0.05",
        "risk.max_drawdown": "0.25",
        "risk.max_volume_participation": "0.10",
        "dividends.pay_lag_trading_days": "14",
        "tax.dividend_reinvestment_exemption": "false",
    }


# Atomicity and concurrency (M5 spec §6.4, §9.2).


def test_a_day_that_fails_to_save_leaves_the_account_at_the_day_before(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    before = tables(cli)
    with closing(sqlite3.connect(cli.home / STATE_FILE, isolation_level=None)) as database:
        database.execute(
            "CREATE TRIGGER refuse BEFORE INSERT ON day_reports "
            "BEGIN SELECT RAISE(ABORT, 'refused by the test'); END"
        )
        failed = run_on(cli, trading_days()[1])
        assert failed.code == 1
        assert failed.err.startswith("steadyhand-idx: refused by the test\n")
        assert tables(cli) == before
        database.execute("DROP TRIGGER refuse")
    assert run_on(cli, trading_days()[1]).code == 0
    with opened(cli) as store:
        assert store.days() == trading_days()[:2]


@dataclass(frozen=True, slots=True)
class Interrupted:
    """The recorded data, which runs *interrupt* once, on the first read: as if another
    ``paper run`` worked while this one was fetching."""

    inner: DataSource
    interrupt: Callable[[], object]
    done: list[bool]

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        if not self.done:
            self.done.append(True)
            self.interrupt()
        return self.inner.bars(instrument, start, end)

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return self.inner.corporate_actions(instrument, start, end)

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> Sequence[Note]:
        return ()


def test_days_another_run_saves_meanwhile_are_left_to_it(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    target = trading_days()[3]

    @contextmanager
    def interrupted(folder: Path) -> Iterator[DataSource]:
        with recorded_source(folder) as recorded:
            yield Interrupted(recorded, lambda: run_on(cli, target), [])

    result = run_on(replace(cli, source=interrupted), target)
    assert result.code == 0, result.err
    assert result.out.startswith("already up to date for 2021-02-04\n")
    with opened(cli) as store:
        assert store.days() == trading_days()[:4]
        assert [(run.outcome, run.days) for run in store.runs()] == [
            (Outcome.RAN, (START,)),
            (Outcome.RAN, trading_days()[1:4]),
            (Outcome.UP_TO_DATE, ()),
        ]


def test_two_runs_started_together_run_each_day_exactly_once(tmp_path: Path) -> None:
    together = paper(tmp_path / "together")
    alone = paper(tmp_path / "alone")
    for cli in (together, alone):
        run_on(cli, START)
    target = at(trading_days()[8])
    assert run_on(alone, trading_days()[8]).code == 0
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    processes = [
        context.Process(target=paper_process, args=(str(together.home), target.isoformat(), start))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(timeout=120)
    assert [process.exitcode for process in processes] == [0, 0]
    assert tables(together) == tables(alone)
    with opened(together) as store:
        assert store.days() == trading_days()[:9]
        assert len(store.runs()) == 3


MONTHLY_CONFIG = GOLDEN_CONFIG.replace(
    'name = "buy-and-hold"', 'name = "monthly-savings"\ninstalments = 4'
)
"""The golden settings with ``monthly-savings`` spreading the starting cash over four months."""


def test_dividend_growth_reviews_again_on_the_first_trading_day_of_2022(tmp_path: Path) -> None:
    cli = paper(tmp_path, GROWTH_CONFIG)
    run_on(cli, START)
    result = run_on(cli, END, "--catch-up")
    assert result.code == 0, result.err
    expected = golden_backtest(cli, END).run
    with opened(cli) as store:
        reports = store.reports()
        account = store.account()
    assert reports == expected.reports
    assert account is not None
    assert account.state == expected.final
    # 3 January 2022 tests 2019 to 2021: TLKM now passes and UNVR no longer does. The orders
    # it places that day fill on the 4th.
    filled = {
        (fill.order.instrument.symbol, fill.order.side.value)
        for report in reports
        if report.day == date(2022, 1, 4)
        for fill in report.fills
    }
    assert {("TLKM", "buy"), ("UNVR", "sell")} <= filled
    assert account.state.memory == {"set": "IDX:BBCA IDX:TLKM", "year": "2022"}


def test_the_settings_of_the_strategy_that_runs_are_recorded_with_the_engines(
    tmp_path: Path,
) -> None:
    monthly = settings_of(load(paper(tmp_path, MONTHLY_CONFIG).config))
    assert monthly["strategy.instalments"] == "4"
    plain = settings_of(load(paper(tmp_path / "plain").config))
    assert [key for key in plain if key.startswith("strategy.")] == []


def test_a_changed_strategy_setting_is_recorded_and_its_guide_says_when_it_applies(
    tmp_path: Path,
) -> None:
    cli = paper(tmp_path, MONTHLY_CONFIG)
    run_on(cli, START)
    cli.config.write_text(
        MONTHLY_CONFIG.replace("instalments = 4", "instalments = 6"), encoding="utf-8"
    )
    run_on(cli, trading_days()[1])
    with opened(cli) as store:
        changed = [
            (line.day, line.note.text)
            for line in store.audit()
            if line.note.key == PAPER_SETTING_CHANGED
        ]
        account = store.account()
    assert changed == [
        (
            trading_days()[1],
            (
                "strategy.instalments changed from 4 to 6; the strategy's guide says when a "
                "change takes effect"
            ),
        )
    ]
    assert account is not None
    # monthly-savings fixed its instalment on its first day: a quarter of the starting cash.
    assert account.state.memory["instalment"] == "25000000"


def test_a_strategy_switched_to_records_its_settings_the_first_day_it_runs(
    tmp_path: Path,
) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    cli.config.write_text(MONTHLY_CONFIG, encoding="utf-8")
    assert cli("paper", "switch", "monthly-savings", stdin="monthly-savings\n").code == 0
    run_on(cli, trading_days()[1])
    with opened(cli) as store:
        recorded = [
            (line.day, line.note.text)
            for line in store.audit()
            if line.note.key == PAPER_SETTING_CHANGED
        ]
        account = store.account()
    assert recorded == [
        (trading_days()[1], "strategy.instalments is 4, recorded for the first time")
    ]
    assert account is not None
    # buy-and-hold had spent all but Rp 1,579,730 of the starting cash: monthly-savings sizes its
    # instalment from that cash, not from the portfolio's value (M6 spec §5).
    cash = account.state.holdings.portfolio.spendable_cash(trading_days()[1])
    assert cash == Money(1_579_730, IDR)
    assert account.state.memory == {"instalment": "394932", "due": "3", "month": "2021-02"}
