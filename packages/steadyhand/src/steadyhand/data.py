"""The DataSource protocol: where prices and corporate actions come from."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.types import Bar, CorporateAction, Instrument


class DataUnavailableError(RuntimeError):
    """A data source could not supply what was asked for. The daily run stops without trading."""


class UnavailableDaysError(DataUnavailableError):
    """A data source refuses particular days for one stock, and ``days`` names every one.

    A backtest leaves the stock untraded on those days and fetches the clean days around them
    (M3 spec §7.3). Any other ``DataUnavailableError`` stops the run.
    """

    def __init__(self, message: str, days: Sequence[date]) -> None:
        found = tuple(days)
        if not found:
            msg = "an unavailable-days error must name at least one day"
            raise ValueError(msg)
        if list(found) != sorted(set(found)):
            msg = "the unavailable days must be different and in date order"
            raise ValueError(msg)
        self.days = found
        super().__init__(message)


@runtime_checkable
class DataSource(Protocol):
    """A supplier of **unadjusted** daily bars and corporate actions.

    Both methods cover *start* to *end* inclusive, return items in date order, and raise
    ``DataUnavailableError`` rather than return partial data (fail closed).
    """

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        """Unadjusted OHLCV bars, one per trading day with data."""
        ...

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        """Splits, cash dividends and other actions with an ex-date in the range."""
        ...
