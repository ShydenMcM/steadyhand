"""Value types validate themselves on construction, so bad data fails where it enters."""

import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.types import (
    Bar,
    CashDividend,
    Costs,
    Fill,
    Instrument,
    InvalidBarError,
    Order,
    OrderAck,
    OtherAction,
    Position,
    Side,
    Split,
)

DAY = date(2026, 1, 5)


def usd() -> Currency:
    return Currency("USD", 2)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def bbri() -> Instrument:
    return Instrument("BBRI", "IDX", IDR)


def bar(**overrides: object) -> Bar:
    fields: dict[str, object] = {
        "instrument": bbri(),
        "day": DAY,
        "open": rp(4_100),
        "high": rp(4_200),
        "low": rp(4_000),
        "close": rp(4_150),
        "volume": 1_000_000,
    }
    fields.update(overrides)
    return Bar(**fields)  # type: ignore[arg-type]


def order(side: Side = Side.BUY, quantity: int = 300) -> Order:
    return Order(bbri(), side, quantity, DAY)


def costs(fee: int = 0, levy: int = 0, tax: int = 0) -> Costs:
    return Costs(rp(fee), rp(levy), rp(tax))


def test_side_values() -> None:
    assert [side.value for side in Side] == ["buy", "sell"]


class TestInstrument:
    @pytest.mark.parametrize("symbol", ["BBRI", "BRK.B", "0700", "A", "X" * 20, "BF-B"])
    def test_accepts_exchange_symbols(self, symbol: str) -> None:
        assert Instrument(symbol, "IDX", IDR).symbol == symbol

    @pytest.mark.parametrize("symbol", ["", "bbri", "BB RI", ".BBRI", "X" * 21])
    def test_refuses_malformed_symbols(self, symbol: str) -> None:
        with pytest.raises(ValueError, match="symbol must be 1-20 capital letters"):
            Instrument(symbol, "IDX", IDR)

    def test_refuses_a_non_string_symbol(self) -> None:
        with pytest.raises(TypeError, match="symbol must be a str, got NoneType"):
            Instrument(None, "IDX", IDR)  # type: ignore[arg-type]

    def test_refuses_a_non_currency_currency(self) -> None:
        with pytest.raises(TypeError, match="currency must be a Currency, got str"):
            Instrument("BBRI", "IDX", "IDR")  # type: ignore[arg-type]

    def test_refuses_a_non_string_market(self) -> None:
        with pytest.raises(TypeError, match="market must be a str, got int"):
            Instrument("BBRI", 1, IDR)  # type: ignore[arg-type]

    @pytest.mark.parametrize("market", ["I", "idx", "IDX1", "M" * 11])
    def test_refuses_malformed_markets(self, market: str) -> None:
        with pytest.raises(ValueError, match="market must be 2-10 capital letters"):
            Instrument("BBRI", market, IDR)

    @pytest.mark.parametrize("market", ["US", "M" * 10])
    def test_market_length_boundaries_are_accepted(self, market: str) -> None:
        assert Instrument("BBRI", market, IDR).market == market

    def test_is_compared_and_hashed_by_value(self) -> None:
        assert {bbri(): 1}[Instrument("BBRI", "IDX", IDR)] == 1


class TestBar:
    def test_a_consistent_bar_is_accepted(self) -> None:
        assert bar().close == rp(4_150)

    def test_zero_volume_is_a_valid_bar(self) -> None:
        # A suspended stock's day: the bar is real data; the fill model rejects orders on it.
        assert bar(volume=0).volume == 0

    @pytest.mark.parametrize("field", ["open", "high", "low", "close"])
    def test_prices_must_be_positive(self, field: str) -> None:
        with pytest.raises(
            InvalidBarError, match=f"BBRI 2026-01-05: {field} must be positive, got IDR 0"
        ):
            bar(**{field: rp(0)})

    def test_prices_must_be_in_the_instrument_currency(self) -> None:
        with pytest.raises(InvalidBarError, match="BBRI 2026-01-05: close is in USD, expected IDR"):
            bar(close=Money(415_000, usd()))

    @pytest.mark.parametrize("volume", [-1, True, "1"])
    def test_volume_must_be_a_non_negative_int(self, volume: object) -> None:
        with pytest.raises(InvalidBarError, match="volume must be a non-negative int"):
            bar(volume=volume)

    @pytest.mark.parametrize(("field", "amount"), [("high", 4_150), ("low", 4_100)])
    def test_high_and_low_may_touch_open_or_close(self, field: str, amount: int) -> None:
        assert bar(**{field: rp(amount)}).volume == 1_000_000

    @pytest.mark.parametrize(("field", "amount"), [("high", 4_149), ("low", 4_101)])
    def test_high_and_low_must_bracket_open_and_close(self, field: str, amount: int) -> None:
        with pytest.raises(InvalidBarError, match="do not bracket open IDR 4,100 and close"):
            bar(**{field: rp(amount)})

    def test_day_must_be_a_plain_date(self) -> None:
        with pytest.raises(TypeError, match="bar day must be a date, got datetime"):
            bar(day=datetime(2026, 1, 5, tzinfo=UTC))


class TestCorporateActions:
    @pytest.mark.parametrize(("old", "new"), [(1, 5), (5, 1)])
    def test_splits_and_reverse_splits(self, old: int, new: int) -> None:
        split = Split(bbri(), DAY, old, new)
        assert (split.old_shares, split.new_shares) == (old, new)

    def test_a_split_must_change_the_share_count(self) -> None:
        with pytest.raises(ValueError, match="BBRI 2026-01-05: turning 2 shares into 2"):
            Split(bbri(), DAY, 2, 2)

    def test_split_counts_must_be_at_least_one(self) -> None:
        with pytest.raises(ValueError, match="old_shares must be at least 1, got 0"):
            Split(bbri(), DAY, 0, 1)

    def test_split_counts_refuse_bool(self) -> None:
        with pytest.raises(TypeError, match="new_shares must be an int, got bool"):
            Split(bbri(), DAY, 1, True)

    def test_split_ex_date_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="split ex_date must be a date"):
            Split(bbri(), datetime(2026, 1, 5, tzinfo=UTC), 1, 2)

    def test_fractional_dividends_are_allowed(self) -> None:
        assert CashDividend(bbri(), DAY, Decimal("12.5")).per_share == Decimal("12.5")

    @pytest.mark.parametrize("per_share", [Decimal(0), Decimal(-1), Decimal("NaN")])
    def test_dividend_must_be_positive_and_finite(self, per_share: Decimal) -> None:
        with pytest.raises(ValueError, match="per_share must be a positive finite Decimal"):
            CashDividend(bbri(), DAY, per_share)

    def test_dividend_per_share_must_be_a_decimal(self) -> None:
        with pytest.raises(TypeError, match="per_share must be a Decimal, got int"):
            CashDividend(bbri(), DAY, 12)  # type: ignore[arg-type]

    def test_dividend_ex_date_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="dividend ex_date must be a date"):
            CashDividend(bbri(), datetime(2026, 1, 5, tzinfo=UTC), Decimal(1))

    def test_other_action_needs_a_description(self) -> None:
        with pytest.raises(
            ValueError, match="BBRI 2026-01-05: an other action needs a description"
        ):
            OtherAction(bbri(), DAY, "  ")

    def test_other_action_refuses_a_non_string_description(self) -> None:
        with pytest.raises(TypeError, match="description must be a str, got NoneType"):
            OtherAction(bbri(), DAY, None)  # type: ignore[arg-type]

    def test_other_action_keeps_its_description(self) -> None:
        assert OtherAction(bbri(), DAY, "rights issue 1:4").description == "rights issue 1:4"

    def test_other_action_ex_date_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="action ex_date must be a date"):
            OtherAction(bbri(), datetime(2026, 1, 5, tzinfo=UTC), "merger")


class TestOrders:
    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="order quantity must be at least 1, got 0"):
            order(quantity=0)

    def test_quantity_refuses_bool(self) -> None:
        with pytest.raises(TypeError, match="order quantity must be an int, got bool"):
            order(quantity=True)

    def test_placed_on_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="placed_on must be a date"):
            Order(bbri(), Side.BUY, 1, datetime(2026, 1, 5, tzinfo=UTC))

    def test_a_rejection_must_say_why(self) -> None:
        with pytest.raises(ValueError, match="a rejected buy order for BBRI must say why"):
            OrderAck(order(), accepted=False, reason=" ")

    @pytest.mark.parametrize("accepted", [True, False])
    def test_a_reason_must_be_a_string(self, *, accepted: bool) -> None:
        with pytest.raises(TypeError, match="reason must be a str, got NoneType"):
            OrderAck(order(), accepted=accepted, reason=None)  # type: ignore[arg-type]

    def test_a_rejection_with_a_reason_is_accepted(self) -> None:
        ack = OrderAck(order(), accepted=False, reason="outside the auto-reject band")
        assert ack.reason == "outside the auto-reject band"

    def test_an_acceptance_needs_no_reason(self) -> None:
        assert OrderAck(order(), accepted=True).reason == ""


class TestCosts:
    def test_total_adds_the_three_parts(self) -> None:
        assert costs(fee=450, levy=30, tax=100).total == rp(580)

    def test_zero(self) -> None:
        assert Costs.zero(IDR) == costs()

    @pytest.mark.parametrize("part", ["fee", "levy", "tax"])
    def test_no_part_may_be_negative(self, part: str) -> None:
        with pytest.raises(ValueError, match=f"{part} cannot be negative, got IDR -1"):
            costs(**{part: -1})

    def test_parts_must_share_a_currency(self) -> None:
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Costs(rp(1), rp(1), Money(1, usd()))


class TestFill:
    def test_gross_is_price_times_quantity(self) -> None:
        fill = Fill(order(), DAY, 300, rp(4_150), costs())
        assert fill.gross == rp(1_245_000)

    def test_a_partial_fill_is_allowed(self) -> None:
        assert Fill(order(), DAY, 100, rp(4_150), costs()).quantity == 100

    def test_cannot_precede_its_order(self) -> None:
        with pytest.raises(ValueError, match="a fill on 2026-01-04 cannot precede its order"):
            Fill(order(), date(2026, 1, 4), 300, rp(4_150), costs())

    def test_day_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="fill day must be a date"):
            Fill(order(), datetime(2026, 1, 5, tzinfo=UTC), 300, rp(4_150), costs())

    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="fill quantity must be at least 1, got 0"):
            Fill(order(), DAY, 0, rp(4_150), costs())

    def test_cannot_exceed_the_order(self) -> None:
        with pytest.raises(ValueError, match="filled 301 shares but the order was for 300"):
            Fill(order(), DAY, 301, rp(4_150), costs())

    def test_price_must_be_in_the_instrument_currency(self) -> None:
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Fill(order(), DAY, 300, Money(4_150, usd()), costs())

    def test_costs_must_be_in_the_instrument_currency(self) -> None:
        usd_costs = Costs(Money(0, usd()), Money(0, usd()), Money(0, usd()))
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Fill(order(), DAY, 300, rp(4_150), usd_costs)

    def test_price_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="fill price must be positive, got IDR 0"):
            Fill(order(), DAY, 300, rp(0), costs())


class TestPosition:
    def test_holds_quantity_and_cost_basis(self) -> None:
        position = Position(bbri(), 300, rp(1_245_450))
        assert (position.quantity, position.cost_basis) == (300, rp(1_245_450))

    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="position quantity must be at least 1, got 0"):
            Position(bbri(), 0, rp(0))

    def test_cost_basis_must_be_in_the_instrument_currency(self) -> None:
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Position(bbri(), 1, Money(1, usd()))

    def test_cost_basis_cannot_be_negative(self) -> None:
        with pytest.raises(ValueError, match="cost basis cannot be negative, got IDR -1"):
            Position(bbri(), 1, rp(-1))


def wrong(value: object) -> Any:  # noqa: ANN401 - hands a deliberately mistyped value past mypy
    """Mark the argument a test passes with the wrong type on purpose."""
    return value


class TestFieldTypes:
    """Every field refuses a wrong type where it enters, naming the field (#21)."""

    @pytest.mark.parametrize(
        ("build", "message"),
        [
            (lambda: bar(instrument=None), "instrument must be an Instrument, got NoneType"),
            (lambda: bar(open=4_100), "open must be a Money, got int"),
            (lambda: bar(close=4_150), "close must be a Money, got int"),
            (
                lambda: Split(wrong(None), DAY, 1, 5),
                "instrument must be an Instrument, got NoneType",
            ),
            (
                lambda: CashDividend(wrong(None), DAY, Decimal(1)),
                "instrument must be an Instrument, got NoneType",
            ),
            (
                lambda: OtherAction(wrong(None), DAY, "x"),
                "instrument must be an Instrument, got NoneType",
            ),
            (
                lambda: Order(wrong("BBRI"), Side.BUY, 1, DAY),
                "instrument must be an Instrument, got str",
            ),
            (lambda: Order(bbri(), wrong("buy"), 1, DAY), "side must be a Side, got str"),
            (lambda: OrderAck(wrong(None), True), "order must be an Order, got NoneType"),
            (lambda: OrderAck(order(), wrong("no"), "x"), "accepted must be a bool, got str"),
            (lambda: OrderAck(order(), wrong(1)), "accepted must be a bool, got int"),
            (lambda: Costs(wrong(0), rp(0), rp(0)), "fee must be a Money, got int"),
            (lambda: Costs(rp(0), wrong(0), rp(0)), "levy must be a Money, got int"),
            (lambda: Costs(rp(0), rp(0), wrong(0)), "tax must be a Money, got int"),
            (
                lambda: Fill(wrong(None), DAY, 1, rp(1), costs()),
                "order must be an Order, got NoneType",
            ),
            (lambda: Fill(order(), DAY, 1, wrong(1), costs()), "price must be a Money, got int"),
            (
                lambda: Fill(order(), DAY, 1, rp(1), wrong(None)),
                "costs must be a Costs, got NoneType",
            ),
            (
                lambda: Position(wrong(None), 1, rp(1)),
                "instrument must be an Instrument, got NoneType",
            ),
            (lambda: Position(bbri(), 1, wrong(1)), "cost_basis must be a Money, got int"),
        ],
    )
    def test_a_wrong_type_is_refused(self, build: Callable[[], object], message: str) -> None:
        with pytest.raises(TypeError, match=f"^{re.escape(message)}$"):
            build()
