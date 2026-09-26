"""The Universe protocol: which stocks a strategy may buy on each day (M3 spec §7.2)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.types import Instrument


@runtime_checkable
class Universe(Protocol):
    """The stocks a strategy may choose from, as they stood on each day.

    A backtest refuses a start before ``first_day()``: before it, membership is unknown, and
    guessing it would hide survivorship bias (M3 spec, decision 3).
    """

    def members_on(self, day: date) -> frozenset[Instrument]:
        """Every member on *day*. Raises ``LookupError`` for a day before ``first_day()``."""
        ...

    def excluded_on(self, day: date) -> Mapping[Instrument, str]:
        """Each stock the operator keeps out on *day*, with the reason given for it."""
        ...

    def first_day(self) -> date:
        """The first day whose membership is known."""
        ...
