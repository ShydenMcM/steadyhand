"""``IdxMarketRules``: the Indonesia Stock Exchange's ``MarketRules``, read from ``data/*.toml``.

Every value is looked up for the date it applies to (spec §9.1). The rules refuse any day before
``verified_from``, the latest first date of any table in ``tick_sizes.toml``, ``auto_reject.toml``,
``fees.toml`` and ``holidays.toml``, and the refusal names the table that sets it. The date is
derived from the files and never written into code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from steadyhand import (
    IDR,
    Costs,
    Currency,
    Instrument,
    Money,
    Side,
    UnsupportedDateError,
)
from steadyhand_idx._datafile import Dated, load_shipped
from steadyhand_idx.bands import BANDS_FILE, BandRow, parse_bands
from steadyhand_idx.calendar import HOLIDAYS_FILE, IdxCalendar
from steadyhand_idx.fees import FeeSchedule
from steadyhand_idx.ticks import TICKS_FILE, TickRow, parse_settlement, parse_ticks

MARKET = "IDX"


@dataclass(frozen=True, slots=True)
class RuleTables:
    """Every dated table the IDX rules read. ``shipped()`` loads the package's own files."""

    calendar: IdxCalendar
    ticks: Dated[TickRow]
    settlement: Dated[int]
    bands: Dated[BandRow]
    fees: FeeSchedule

    @classmethod
    def shipped(cls) -> RuleTables:
        tick_document = load_shipped(TICKS_FILE)
        return cls(
            calendar=IdxCalendar.shipped(),
            ticks=parse_ticks(tick_document),
            settlement=parse_settlement(tick_document),
            bands=parse_bands(load_shipped(BANDS_FILE)),
            fees=FeeSchedule.shipped(),
        )

    def first_dates(self) -> list[tuple[date, str]]:
        """Each table's first day, with the table's name, calendar first."""
        dated: list[Dated[object]] = [self.ticks, self.settlement, self.bands, *self.fees.tables]
        return [
            (self.calendar.first_day, f"{HOLIDAYS_FILE} [year]"),
            *((table.first, str(table.where)) for table in dated),
        ]


class IdxMarketRules:
    """IDX rules for one broker fee preset (``custom`` by default; spec §9.5 ``broker_fees``)."""

    def __init__(self, tables: RuleTables | None = None, *, broker_fees: str = "custom") -> None:
        self._tables = RuleTables.shipped() if tables is None else tables
        self._preset = self._tables.fees.preset(broker_fees)
        self._verified_from, self._set_by = max(self._tables.first_dates(), key=lambda p: p[0])

    @property
    def currency(self) -> Currency:
        return IDR

    @property
    def verified_from(self) -> date:
        return self._verified_from

    def require_supported(self, day: date) -> None:
        if day < self._verified_from:
            msg = (
                f"steadyhand's IDX rules are primary-verified from "
                f"{self._verified_from.isoformat()}, the first date of {self._set_by}; "
                f"{day.isoformat()} is earlier"
            )
            raise UnsupportedDateError(msg)
        self._tables.calendar.require_covered(day)

    def lot_size(self, instrument: Instrument, on: date) -> int:
        self._check(instrument, on)
        return self._tables.ticks.on(on).lot_size

    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money:
        self._check(instrument, on)
        self._check_money(price, "price")
        row = self._tables.ticks.on(on)
        rounded = row.round_up(price.amount) if side is Side.BUY else row.round_down(price.amount)
        return Money(rounded, IDR)

    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]:
        """The lowest and highest prices the exchange accepts around *reference*.

        II-A gives the band as a percentage (or, for the lowest prices, rupiah) and states no
        rounding. A price must also sit on the tick grid, so the highest accepted price is the
        highest valid price at or below the band's top, and the lowest is the lowest valid price
        at or above its bottom and the minimum price (docs/research/t-rules.md §3).
        """
        self._check(instrument, on)
        self._check_money(reference, "reference")
        band = self._tables.bands.on(on)
        if reference.amount < band.min_price:
            msg = f"reference {reference} is below the minimum price, Rp{band.min_price}"
            raise ValueError(msg)
        ticks = self._tables.ticks.on(on)
        bottom, top = band.limits(reference.amount)
        low = ticks.round_up(max(math.ceil(bottom), band.min_price))
        high = ticks.round_down(math.floor(top))
        return Money(low, IDR), Money(high, IDR)

    def costs(self, side: Side, gross: Money, on: date) -> Costs:
        self.require_supported(on)
        return self._tables.fees.trade_costs(self._preset, side, gross, on)

    def daily_costs(self, traded: Money, on: date) -> Money:
        self.require_supported(on)
        return self._tables.fees.daily_costs(traded, on)

    def settlement_date(self, trade_date: date) -> date:
        """The trading day, ``settlement`` trading days after *trade_date*, when a trade settles."""
        self.require_supported(trade_date)
        if not self._tables.calendar.is_trading_day(trade_date):
            msg = f"{trade_date.isoformat()} is not an IDX trading day, so nothing trades on it"
            raise ValueError(msg)
        lag = self._tables.settlement.on(trade_date)
        return self._tables.calendar.add_trading_days(trade_date, lag)

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        self.require_supported(on)
        self._check_money(gross, "gross")
        return self._tables.fees.dividend_tax(
            gross, reinvested_by_deadline=reinvested_by_deadline, on=on
        )

    def is_trading_day(self, day: date) -> bool:
        self.require_supported(day)
        return self._tables.calendar.is_trading_day(day)

    def _check(self, instrument: Instrument, on: date) -> None:
        self.require_supported(on)
        if instrument.market != MARKET or instrument.currency != IDR:
            msg = (
                f"{instrument.symbol} is a {instrument.market} {instrument.currency.code} "
                f"instrument; these rules are for IDX IDR"
            )
            raise ValueError(msg)

    @staticmethod
    def _check_money(amount: Money, what: str) -> None:
        if amount.currency != IDR:
            msg = f"{what} must be in IDR, got {amount}"
            raise ValueError(msg)
