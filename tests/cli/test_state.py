"""The paper account's state database (M5 spec §6.3, §6.4, §9.2 "Migrations")."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from cli_world import mode, umask

from steadyhand import (
    DATA_BAR_MISSING,
    IDR,
    DayReport,
    EngineState,
    Money,
    Note,
)
from steadyhand_idx.state import (
    BUSY_TIMEOUT_SECONDS,
    MIGRATIONS,
    STATE_FILE,
    Account,
    AuditLine,
    Outcome,
    Run,
    StateSchemaError,
    StateStore,
)

D1 = date(2026, 1, 5)
D2 = date(2026, 1, 6)
D3 = date(2026, 1, 7)
SETTINGS = {"account.monthly_contribution_idr": "0", "risk.max_weight": "0.10"}


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def account(day: date, cash: int = 10_000_000, strategy: str = "buy-and-hold") -> Account:
    state = replace(EngineState.opening(rp(cash), D1), last_day=day)
    return Account(D1, strategy, state, SETTINGS)


def report(day: date) -> DayReport:
    zero = rp(0)
    return DayReport(
        day=day,
        fills=(),
        rejected=(),
        cuts=(),
        queued=(),
        entitled=(),
        paid=(),
        tax=zero,
        daily_cost=zero,
        deposit=zero,
        frozen=(),
        halt=None,
        settled=rp(10_000_000),
        unsettled=zero,
        holdings_value=zero,
        value=rp(10_000_000),
        unit_price=Decimal(1),
        warnings=(),
    )


def line(day: date, text: str) -> AuditLine:
    return AuditLine(day, Note(DATA_BAR_MISSING, text))


@pytest.fixture
def store(tmp_path: Path) -> Iterator[StateStore]:
    with StateStore(tmp_path / STATE_FILE) as opened:
        yield opened


def saved_through_d2(store: StateStore) -> None:
    assert store.save(account(D1), after=None, report=report(D1), audit=(line(D1, "one"),))
    assert store.save(account(D2), after=D1, report=report(D2), audit=(line(D2, "two"),))


def raw(path: Path) -> closing[sqlite3.Connection]:
    """A second connection to the file, closed when its ``with`` block ends.

    Python 3.13 warns about a connection left for the garbage collector, and ``-W error``
    fails whichever test is running when it is collected.
    """
    return closing(sqlite3.connect(path, isolation_level=None))


# The schema.


def test_a_new_database_reaches_the_current_schema_with_its_tables_and_triggers(
    tmp_path: Path,
) -> None:
    with StateStore(tmp_path / STATE_FILE) as store:
        assert store.schema_version == len(MIGRATIONS) == 1
    with raw(tmp_path / STATE_FILE) as database:
        rows = database.execute("SELECT type, name FROM sqlite_master").fetchall()
    assert {name for kind, name in rows if kind == "table"} == {
        "account",
        "day_reports",
        "audit",
        "runs",
    }
    assert {name for kind, name in rows if kind == "trigger"} == {
        "day_reports_are_kept",
        "day_reports_are_never_removed",
        "audit_is_kept",
        "audit_is_never_removed",
        "runs_are_kept",
        "runs_are_never_removed",
    }


def test_opening_again_keeps_what_was_saved(tmp_path: Path) -> None:
    with StateStore(tmp_path / STATE_FILE) as store:
        saved_through_d2(store)
    with StateStore(tmp_path / STATE_FILE) as store:
        assert (store.schema_version, store.days()) == (1, (D1, D2))


def test_a_database_from_a_newer_steadyhand_idx_is_refused_and_left_as_it_was(
    tmp_path: Path,
) -> None:
    path = tmp_path / STATE_FILE
    with raw(path) as database:
        database.execute("PRAGMA user_version = 2")
    with pytest.raises(
        StateSchemaError,
        match=(
            rf"^{path} is at state schema 2, newer than this steadyhand-idx knows \(1\); "
            r"upgrade steadyhand-idx$"
        ),
    ):
        StateStore(path)
    with raw(path) as database:
        assert database.execute("PRAGMA user_version").fetchone() == (2,)
        assert database.execute("SELECT name FROM sqlite_master").fetchall() == []


@pytest.mark.parametrize("value", [0o000, 0o022, 0o277])
def test_the_database_file_is_0600_whatever_the_umask(tmp_path: Path, value: int) -> None:
    with umask(value), StateStore(tmp_path / STATE_FILE):
        pass
    assert mode(tmp_path / STATE_FILE) == 0o600


def test_a_second_run_waits_up_to_the_busy_timeout(store: StateStore) -> None:
    assert BUSY_TIMEOUT_SECONDS == 30.0
    assert store._db.execute("PRAGMA busy_timeout").fetchone() == (30_000,)


def test_the_account_table_holds_one_row(store: StateStore, tmp_path: Path) -> None:
    saved_through_d2(store)
    with (
        raw(tmp_path / STATE_FILE) as database,
        pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
    ):
        database.execute(
            "INSERT INTO account VALUES (2, '2026-01-05', 'x', '{}', '2026-01-05', '{}')"
        )


# Saving days.


def test_there_is_nothing_before_the_first_day(store: StateStore) -> None:
    assert store.account() is None
    assert (store.reports(), store.days(), store.audit(), store.runs()) == ((), (), (), ())
    assert store.report(D1) is None


def test_the_first_day_is_saved_with_its_report_and_its_audit_lines(store: StateStore) -> None:
    first = account(D1)
    assert store.save(first, after=None, report=report(D1), audit=(line(D1, "one"),))
    assert store.account() == first
    assert (store.reports(), store.days()) == ((report(D1),), (D1,))
    assert (store.report(D1), store.report(D2)) == (report(D1), None)
    assert store.audit() == (line(D1, "one"),)


def test_each_later_day_is_saved_after_the_one_before_in_order(store: StateStore) -> None:
    saved_through_d2(store)
    assert store.account() == account(D2)
    assert store.reports() == (report(D1), report(D2))
    assert store.audit() == (line(D1, "one"), line(D2, "two"))


def test_a_save_from_a_day_that_is_no_longer_the_last_writes_nothing(store: StateStore) -> None:
    saved_through_d2(store)
    assert not store.save(account(D3), after=D1, report=report(D3), audit=(line(D3, "late"),))
    assert not store.save(account(D3), after=None, report=report(D3))
    assert store.account() == account(D2)
    assert store.days() == (D1, D2)
    assert store.audit() == (line(D1, "one"), line(D2, "two"))


def test_a_save_without_a_report_changes_only_the_account_and_the_audit_log(
    store: StateStore,
) -> None:
    saved_through_d2(store)
    changed = Account(D1, "other", account(D2).state, {"risk.max_weight": "0.08"})
    assert store.save(changed, after=D2, audit=(line(D2, "switched"),))
    assert store.account() == changed
    assert store.days() == (D1, D2)
    assert store.audit()[-1] == line(D2, "switched")


def test_a_day_whose_report_cannot_be_written_leaves_everything_as_it_was(
    store: StateStore, tmp_path: Path
) -> None:
    saved_through_d2(store)
    with raw(tmp_path / STATE_FILE) as database:
        database.execute(
            "CREATE TRIGGER refuse BEFORE INSERT ON day_reports "
            "BEGIN SELECT RAISE(ABORT, 'refused by the test'); END"
        )
        with pytest.raises(sqlite3.IntegrityError, match="refused by the test"):
            store.save(account(D3), after=D2, report=report(D3), audit=(line(D3, "three"),))
        assert store.account() == account(D2)
        assert store.days() == (D1, D2)
        assert store.audit() == (line(D1, "one"), line(D2, "two"))
        database.execute("DROP TRIGGER refuse")
        assert store.save(account(D3), after=D2, report=report(D3), audit=(line(D3, "three"),))
        assert store.days() == (D1, D2, D3)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE day_reports SET report = '{}'",
        "DELETE FROM day_reports",
        "UPDATE audit SET line = 'changed'",
        "DELETE FROM audit",
        "UPDATE runs SET detail = 'changed'",
        "DELETE FROM runs",
    ],
)
def test_the_logs_are_append_only(store: StateStore, tmp_path: Path, statement: str) -> None:
    saved_through_d2(store)
    store.finish(Run(datetime(2026, 1, 6, 10, tzinfo=UTC), D2, (D1, D2), Outcome.RAN))
    table = statement.split()[1 if statement.startswith("UPDATE") else 2]
    with (
        raw(tmp_path / STATE_FILE) as database,
        pytest.raises(sqlite3.IntegrityError, match=f"^{table} is append-only$"),
    ):
        database.execute(statement)
    assert (len(store.days()), len(store.audit()), len(store.runs())) == (2, 2, 1)


# Runs.


def test_each_run_is_recorded_in_order_with_its_audit_lines(store: StateStore) -> None:
    runs = [
        Run(datetime(2026, 1, 5, 10, tzinfo=UTC), D1, (D1,), Outcome.RAN),
        Run(datetime(2026, 1, 5, 11, tzinfo=UTC), D1, (), Outcome.UP_TO_DATE, "already"),
        Run(datetime(2026, 1, 6, 10, tzinfo=UTC), D2, (), Outcome.STOPPED, "stale"),
        Run(datetime(2026, 1, 7, 10, tzinfo=UTC), D3, (D2, D3), Outcome.HALTED, "halted"),
    ]
    store.finish(runs[0])
    store.finish(runs[1])
    store.finish(runs[2], (line(D2, "stopped"),))
    store.finish(runs[3])
    assert store.runs() == tuple(runs)
    assert store.audit() == (line(D2, "stopped"),)


def test_the_outcomes_are_the_four_the_database_accepts() -> None:
    assert [outcome.value for outcome in Outcome] == ["ran", "up to date", "stopped", "halted"]


WIB = timezone(timedelta(hours=7))


@pytest.mark.parametrize(
    "at", [datetime.fromisoformat("2026-01-05T10:00"), datetime(2026, 1, 5, 17, tzinfo=WIB)]
)
def test_a_runs_time_is_in_utc(at: datetime) -> None:
    with pytest.raises(ValueError, match=r"^a run's time is in UTC, got 2026-01-05T"):
        Run(at, D1, (), Outcome.RAN)


# Accounts.


def test_an_account_is_saved_only_with_a_day_run() -> None:
    with pytest.raises(ValueError, match=r"^an account is saved only with a day run$"):
        Account(D1, "buy-and-hold", EngineState.opening(rp(1_000), D1))


def test_an_accounts_settings_cannot_be_changed_in_place() -> None:
    settings = dict(SETTINGS)
    saved = Account(D1, "buy-and-hold", account(D1).state, settings)
    settings["risk.max_weight"] = "0.50"
    assert saved.settings == SETTINGS
    with pytest.raises(TypeError):
        saved.settings["risk.max_weight"] = "0.50"  # type: ignore[index]


@pytest.mark.parametrize(
    ("statement", "read", "message"),
    [
        (
            "UPDATE account SET settings = '{\"risk.max_weight\":1}'",
            "account",
            r"^the saved settings are not a table of text values: \{\"risk.max_weight\":1\}$",
        ),
        (
            "UPDATE account SET settings = '[]'",
            "account",
            r"^the saved settings are not a table of text values: \[\]$",
        ),
        (
            (
                "INSERT INTO runs (at, target, days, outcome, detail) VALUES "
                "('2026-01-05T10:00:00+00:00', '2026-01-05', '{\"days\":[5]}', 'ran', '')"
            ),
            "runs",
            r"^a run's days are not a list of dates: \{\"days\":\[5\]\}$",
        ),
        (
            (
                "INSERT INTO runs (at, target, days, outcome, detail) VALUES "
                "('2026-01-05T10:00:00+00:00', '2026-01-05', '[]', 'ran', '')"
            ),
            "runs",
            r"^a run's days are not a list of dates: \[\]$",
        ),
    ],
)
def test_saved_rows_that_cannot_be_read_are_refused(
    store: StateStore, tmp_path: Path, statement: str, read: str, message: str
) -> None:
    saved_through_d2(store)
    with raw(tmp_path / STATE_FILE) as database:
        database.execute(statement)
    with pytest.raises(ValueError, match=message):
        getattr(store, read)()
