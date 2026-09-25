"""The DataSource protocol: where prices and corporate actions come from."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.types import Bar, CorporateAction, Instrument


class DataUnavailableError(RuntimeError):
    """A data source could not supply what was asked for. The daily run stops without trading."""


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
