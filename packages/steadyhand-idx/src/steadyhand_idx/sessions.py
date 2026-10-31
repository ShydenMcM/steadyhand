"""The IDX regular-market times the extension needs, from ``data/sessions.toml`` (#225).

Python reads the file only to check it: the browser extension's core decides from it when a
trading day's close is final and when the next day's pre-opening starts (extension spec §4.2).
Times are Jakarta time (WIB).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from steadyhand_idx._datafile import (
    DataFileError,
    Dated,
    Row,
    Where,
    get_date,
    get_str,
    get_time,
    only_keys,
    require_schema,
    rows,
)

SESSIONS_FILE = "sessions.toml"


@dataclass(frozen=True, slots=True)
class SessionRow:
    """When pre-opening starts and the last second of closing-price matching, in WIB."""

    source: str
    pre_opening_from: time
    closing_match_until: time


def _parse_row(row: Row, where: Where) -> SessionRow:
    only_keys(row, {"from", "source", "pre_opening_from", "closing_match_until"}, where)
    opening = get_time(row, "pre_opening_from", where)
    closing = get_time(row, "closing_match_until", where)
    if opening >= closing:
        msg = (
            f"{where}: pre-opening must start before the closing match ends, got "
            f"{opening.isoformat()} and {closing.isoformat()}"
        )
        raise DataFileError(msg)
    return SessionRow(get_str(row, "source", where), opening, closing)


def parse_sessions(document: Row, file: str = SESSIONS_FILE) -> Dated[SessionRow]:
    require_schema(document, file, 1)
    only_keys(document, {"schema", "sessions"}, Where(file, "top level"))
    where = Where(file, "sessions")
    found = rows(document, "sessions", where)
    return Dated(
        where,
        tuple(get_date(row, "from", where.at(i)) for i, row in enumerate(found, start=1)),
        tuple(_parse_row(row, where.at(i)) for i, row in enumerate(found, start=1)),
    )
