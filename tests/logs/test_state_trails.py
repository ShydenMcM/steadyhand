"""The paper account's three trails at full input (#336 AC 4): a year of saved days, its runs and
its audit lines, written, kept, refused and replayed as the store promises (M5 spec §6.3, §9.7).

tests/cli/test_state.py holds the unit stand-ins of each check, on two or three days.
"""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest
from state_world import D1, account, line, raw, report

from steadyhand_idx.state import STATE_FILE, Outcome, Run, StateStore

# A trading year: every weekday for 52 weeks from D1, a Monday (holidays play no part here).
DAYS = tuple(D1 + timedelta(weeks=week, days=weekday) for week in range(52) for weekday in range(5))


@pytest.fixture
def store(tmp_path: Path) -> Iterator[StateStore]:
    with StateStore(tmp_path / STATE_FILE) as opened:
        yield opened


def run_on(day: date, *, days: tuple[date, ...]) -> Run:
    return Run(datetime.combine(day, time(10), tzinfo=UTC), day, days, Outcome.RAN)


def saved_year(store: StateStore) -> None:
    """Each day of DAYS saved after the one before, with an audit line, then its run recorded with
    a line of its own: the order a paper run writes them in."""
    after: date | None = None
    for day in DAYS:
        assert store.save(account(day), after=after, report=report(day), audit=(line(day, "day"),))
        store.finish(run_on(day, days=(day,)), (line(day, "run"),))
        after = day


def test_a_year_of_saved_days_is_replayed_in_day_order_each_day_once(store: StateStore) -> None:
    saved_year(store)
    assert len(DAYS) == 260
    assert store.days() == DAYS
    assert store.reports() == tuple(report(day) for day in DAYS)
    assert store.account() == account(DAYS[-1])


def test_a_years_audit_lines_read_back_in_the_order_they_were_written(store: StateStore) -> None:
    saved_year(store)
    assert store.audit() == tuple(
        written for day in DAYS for written in (line(day, "day"), line(day, "run"))
    )


def test_a_years_runs_read_back_in_the_order_they_were_recorded(store: StateStore) -> None:
    saved_year(store)
    assert store.runs() == tuple(run_on(day, days=(day,)) for day in DAYS)


@pytest.mark.parametrize("index", [0, 129, 258], ids=["first", "middle", "before-last"])
def test_a_day_saved_again_is_refused_and_still_replayed_once(
    store: StateStore, index: int
) -> None:
    saved_year(store)
    day = DAYS[index]
    before = None if index == 0 else DAYS[index - 1]
    again = store.save(account(day), after=before, report=report(day), audit=(line(day, "again"),))
    assert again is False
    assert store.days() == DAYS
    assert store.reports() == tuple(report(day) for day in DAYS)
    assert line(day, "again") not in store.audit()


def test_a_day_that_cannot_be_written_midway_leaves_every_trail_as_it_was(
    store: StateStore, tmp_path: Path
) -> None:
    half = DAYS[:130]
    after: date | None = None
    for day in half:
        assert store.save(account(day), after=after, report=report(day), audit=(line(day, "day"),))
        after = day
    audit, runs = store.audit(), store.runs()
    nxt = DAYS[130]
    with raw(tmp_path / STATE_FILE) as database:
        database.execute(
            "CREATE TRIGGER refuse BEFORE INSERT ON day_reports "
            "BEGIN SELECT RAISE(ABORT, 'refused by the test'); END"
        )
        with pytest.raises(sqlite3.IntegrityError, match="refused by the test"):
            store.save(account(nxt), after=half[-1], report=report(nxt), audit=(line(nxt, "day"),))
        assert (store.days(), store.audit(), store.runs()) == (half, audit, runs)
        assert store.account() == account(half[-1])
        database.execute("DROP TRIGGER refuse")
    assert store.save(account(nxt), after=half[-1], report=report(nxt), audit=(line(nxt, "day"),))
    assert store.days() == (*half, nxt)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE day_reports SET report = '{}' WHERE day = '2026-07-01'",
        "DELETE FROM day_reports WHERE day = '2026-07-01'",
        "UPDATE audit SET line = 'changed' WHERE day = '2026-07-01'",
        "DELETE FROM audit WHERE day = '2026-07-01'",
        "UPDATE runs SET detail = 'changed' WHERE target = '2026-07-01'",
        "DELETE FROM runs WHERE target = '2026-07-01'",
    ],
    ids=[
        "update-day-report",
        "delete-day-report",
        "update-audit",
        "delete-audit",
        "update-run",
        "delete-run",
    ],
)
def test_one_row_of_a_full_year_cannot_be_changed_or_removed(
    store: StateStore, tmp_path: Path, statement: str
) -> None:
    saved_year(store)
    assert date(2026, 7, 1) in DAYS
    table = statement.split()[1 if statement.startswith("UPDATE") else 2]
    with (
        raw(tmp_path / STATE_FILE) as database,
        pytest.raises(sqlite3.IntegrityError, match=f"^{table} is append-only$"),
    ):
        database.execute(statement)
    assert (store.days(), len(store.audit()), len(store.runs())) == (DAYS, 520, 260)
