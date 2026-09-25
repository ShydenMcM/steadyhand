"""The MarketRules protocol: everything that differs between stock exchanges."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.money import Currency, Money
from steadyhand.types import Costs, Instrument, Side


@runtime_checkable
class MarketRules(Protocol):
    """One market's trading rules. Every rule is looked up for a date, because rules change.

    An implementation reads its values from dated data (spec §9.1), never from constants, so a
    backtest over past dates uses the rules that applied on those dates.
    """

    @property
    def currency(self) -> Currency:
        """The currency every price and cost in this market is quoted in."""
        ...

    def lot_size(self, instrument: Instrument, on: date) -> int:
        """Shares per board lot. Orders are whole lots."""
        ...

    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money:
        """The nearest valid price against the trader: up for a BUY, down for a SELL."""
        ...

    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]:
        """The (lowest, highest) price the exchange accepts, given the reference price."""
        ...

    def costs(self, side: Side, gross: Money, on: date) -> Costs:
        """Fee, levy and tax for one trade of *gross* value. Never negative."""
        ...

    def settlement_date(self, trade_date: date) -> date:
        """The trading day on which a trade made on *trade_date* settles."""
        ...

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        """The tax due on a *gross* dividend paid on *on*.

        IDX issuers withhold nothing from resident individuals; see docs/research/t-tax.md.
        """
        ...

    def is_trading_day(self, day: date) -> bool:
        """Whether the market is open on *day*. Raises for a year with no holiday data."""
        ...
