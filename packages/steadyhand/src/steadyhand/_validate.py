"""Shared argument checks for the engine's value types.

Two Python subclass relationships let wrong values through a plain ``isinstance``: ``bool`` is
an ``int``, and ``datetime`` is a ``date``. Both are refused here, at the point of entry.
"""

from datetime import date, datetime


def require_date(value: object, what: str) -> None:
    """Raise ``TypeError`` unless *value* is a plain ``date``."""
    if isinstance(value, datetime) or not isinstance(value, date):
        msg = f"{what} must be a date, got {type(value).__name__}"
        raise TypeError(msg)


def require_int(value: object, what: str, *, minimum: int) -> None:
    """Raise unless *value* is an ``int`` (never a ``bool``) of at least *minimum*."""
    if type(value) is not int:
        msg = f"{what} must be an int, got {type(value).__name__}"
        raise TypeError(msg)
    if value < minimum:
        msg = f"{what} must be at least {minimum}, got {value}"
        raise ValueError(msg)
