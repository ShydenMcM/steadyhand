"""The engine's plug-in points are structural Protocols: anything with the right methods fits.

Each ``_Minimal*`` class is the smallest conforming implementation. Assigning it to a variable
typed as the protocol makes ``mypy --strict`` check every signature; ``isinstance`` checks the
runtime view that plug-in loading will use.
"""

from collections.abc import Mapping, Sequence
from datetime import date, timedelta

import pytest

from steadyhand.broker import Broker
from steadyhand.data import DataSource, DataUnavailableError
from steadyhand.market import MarketRules
from steadyhand.money import IDR, Currency, Money
from steadyhand.notes import Note
from steadyhand.types import Bar, CorporateAction, Costs, Fill, Instrument, Order, OrderAck, Side
from steadyhand.universe import Universe


class _MinimalRules:
    @property
    def currency(self) -> Currency:
        return IDR

    @property
    def verified_from(self) -> date:
        return date(2021, 1, 1)

    def require_supported(self, day: date) -> None:
        return None

    def lot_size(self, instrument: Instrument, on: date) -> int:
        return 100

    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money:
        return price

    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]:
        return (reference, reference)

    def costs(self, side: Side, gross: Money, on: date) -> Costs:
        return Costs.zero(gross.currency)

    def daily_costs(self, traded: Money, on: date) -> Money:
        return Money.zero(traded.currency)

    def settlement_date(self, trade_date: date) -> date:
        return trade_date + timedelta(days=2)

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        return Money.zero(gross.currency)

    def reinvestment_deadline(self, ex_date: date) -> date | None:
        return None

    def protection_end(self, purchase_day: date) -> date:
        return purchase_day

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5


class _MinimalSource:
    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        return ()

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return ()

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> Sequence[Note]:
        return ()


class _MinimalBroker:
    def submit(self, orders: Sequence[Order], on: date) -> Sequence[OrderAck]:
        return [OrderAck(order, accepted=True) for order in orders]

    def fills(self, on: date) -> Sequence[Fill]:
        return ()


class _RulesWithoutTax:
    currency = IDR

    def lot_size(self, instrument: Instrument, on: date) -> int:
        return 100


def test_a_minimal_class_satisfies_market_rules() -> None:
    rules: MarketRules = _MinimalRules()
    assert isinstance(rules, MarketRules)


def test_a_class_missing_methods_is_not_market_rules() -> None:
    assert not isinstance(_RulesWithoutTax(), MarketRules)


@pytest.mark.parametrize("member", ["verified_from", "require_supported", "daily_costs"])
def test_each_member_added_in_m2_is_required(member: str) -> None:
    members = {name: value for name, value in vars(_MinimalRules).items() if name != member}
    assert not isinstance(type("Partial", (), members)(), MarketRules)


@pytest.mark.parametrize("member", ["reinvestment_deadline", "protection_end"])
def test_each_member_added_in_m4_is_required(member: str) -> None:
    members = {name: value for name, value in vars(_MinimalRules).items() if name != member}
    assert not isinstance(type("Partial", (), members)(), MarketRules)


def test_a_minimal_class_satisfies_data_source() -> None:
    source: DataSource = _MinimalSource()
    assert isinstance(source, DataSource)
    assert not isinstance(_MinimalBroker(), DataSource)


def test_data_notes_is_required_of_a_data_source() -> None:
    members = {name: value for name, value in vars(_MinimalSource).items() if name != "data_notes"}
    assert not isinstance(type("Partial", (), members)(), DataSource)


def test_a_minimal_class_satisfies_broker() -> None:
    broker: Broker = _MinimalBroker()
    assert isinstance(broker, Broker)
    assert not isinstance(_MinimalSource(), Broker)


def test_data_unavailable_keeps_the_callers_message() -> None:
    message = "BBRI.JK bars: the request to Yahoo failed: timeout"
    with pytest.raises(
        DataUnavailableError, match=r"^BBRI\.JK bars: the request to Yahoo failed: timeout$"
    ):
        raise DataUnavailableError(message)


class _MinimalUniverse:
    def members_on(self, day: date) -> frozenset[Instrument]:
        return frozenset({Instrument("BBRI", "IDX", IDR)})

    def excluded_on(self, day: date) -> Mapping[Instrument, str]:
        return {}

    def first_day(self) -> date:
        return date(2021, 1, 4)

    def survivorship_warnings(self, start: date, end: date) -> Sequence[Note]:
        return ()


def test_a_minimal_class_satisfies_universe() -> None:
    universe: Universe = _MinimalUniverse()
    assert isinstance(universe, Universe)
    assert not isinstance(_MinimalSource(), Universe)
