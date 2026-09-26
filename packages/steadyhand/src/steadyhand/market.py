"""The MarketRules protocol: everything that differs between stock exchanges."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.money import Currency, Money
from steadyhand.types import Costs, Instrument, Side


class UnsupportedDateError(LookupError):
    """A market's rule data does not cover a date.

    Raised instead of guessing: a year with no holiday data, or a day before a rule table's
    first verified row, must stop the run. It is never read as "no holidays" or "today's rules".
    """


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

    @property
    def verified_from(self) -> date:
        """The first day on which every rule is verified. A backtest may not start earlier."""
        ...

    def require_supported(self, day: date) -> None:
        """Raise ``UnsupportedDateError`` for a day the rule data does not cover.

        The message names the rule table that sets the limit. Every other method checks this.
        """
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

    def daily_costs(self, traded: Money, on: date) -> Money:
        """Charges made once per trading day, given the day's buys plus sells.

        Stamp duty on a trade confirmation is the example: brokers issue one confirmation a day,
        so it cannot be charged per trade. Never negative, and nothing when nothing traded.
        """
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
