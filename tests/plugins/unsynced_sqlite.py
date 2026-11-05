"""A unit run's SQLite connections skip the disk sync (#506).

A COMMIT waits for the disk under SQLite's default ``synchronous = FULL``; on a CI runner one
took more than the 1 s unit limit (PR #505, ``test_resume_must_name_the_accounts_strategy``, with
no other connection on the file). Unit tests check what a store holds, never that it survives a
power cut, so a unit run opens every connection with ``synchronous = OFF``. Shipped code sets
nothing: the integration suite checks each store keeps the durable default
(``tests/integration/cli/test_stores_are_durable.py``).

``tests/conftest.py`` installs this for a unit run only, before any test module is imported.
"""

import functools
import sqlite3
from collections.abc import Callable

REAL_CONNECT: Callable[..., sqlite3.Connection] = sqlite3.connect


@functools.wraps(REAL_CONNECT)
def _unsynced_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
    connection = REAL_CONNECT(*args, **kwargs)
    connection.execute("PRAGMA synchronous = OFF")
    return connection


def install() -> None:
    """Open every later SQLite connection without the disk sync (once, however often called)."""
    sqlite3.connect = _unsynced_connect  # type: ignore[assignment]
