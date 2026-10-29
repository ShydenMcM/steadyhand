"""The paper account's state database as its tests build it: an account, a day's report and an
audit line, for the unit checks of the store (test_state.py) and the logs suite's full-input checks
of its trails (tests/logs, #336)."""

import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from steadyhand import (
    DATA_BAR_MISSING,
    IDR,
    DayReport,
    EngineState,
    Money,
    Note,
)
from steadyhand_idx.state import Account, AuditLine

D1 = date(2026, 1, 5)
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


def raw(path: Path) -> closing[sqlite3.Connection]:
    """A second connection to the file, closed when its ``with`` block ends.

    Python 3.13 warns about a connection left for the garbage collector, and ``-W error``
    fails whichever test is running when it is collected.
    """
    return closing(sqlite3.connect(path, isolation_level=None))
