"""Portfolio: an immutable cash ledger plus positions, with T+2 on sale proceeds."""

from datetime import UTC, date, datetime, timedelta

import pytest

from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.portfolio import (
    CashMovement,
    ChronologyError,
    InsufficientCashError,
    InsufficientSharesError,
    MissingPriceError,
    MovementKind,
    NegativeProceedsError,
    Portfolio,
)
from steadyhand.types import Costs, Fill, Instrument, Order, Position, Side

D0 = date(2026, 1, 5)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
USD = Currency("USD", 2)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def day(offset: int) -> date:
    return D0 + timedelta(days=offset)


def fill(
    side: Side, quantity: int, price: int, on: date, *, fee: int = 0, stock: Instrument = BBRI
) -> Fill:
    order = Order(stock, side, quantity, on)
    return Fill(order, on, quantity, rp(price), Costs(rp(fee), rp(0), rp(0)))


def funded(amount: int = 10_000_000) -> Portfolio:
    return Portfolio.empty(IDR).deposit(rp(amount), D0)


class TestEmpty:
    def test_has_nothing(self) -> None:
        empty = Portfolio.empty(IDR)
        assert empty.cash_balance() == rp(0)
        assert empty.settled_cash(D0) == rp(0)
        assert empty.positions == ()
        assert empty.last_day is None


class TestDeposit:
    def test_is_settled_at_once(self) -> None:
        portfolio = funded()
        assert portfolio.cash_balance() == rp(10_000_000)
        assert portfolio.settled_cash(D0) == rp(10_000_000)
        assert portfolio.ledger == (CashMovement(D0, MovementKind.DEPOSIT, rp(10_000_000), D0),)

    def test_leaves_the_original_untouched(self) -> None:
        empty = Portfolio.empty(IDR)
        empty.deposit(rp(1), D0)
        assert empty.cash_balance() == rp(0)

    def test_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="a deposit must be positive, got IDR 0"):
            Portfolio.empty(IDR).deposit(rp(0), D0)

    def test_must_be_in_the_portfolio_currency(self) -> None:
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Portfolio.empty(IDR).deposit(Money(1, USD), D0)

    def test_day_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="day must be a date, got datetime"):
            Portfolio.empty(IDR).deposit(rp(1), datetime(2026, 1, 5, tzinfo=UTC))


class TestBuy:
    def test_debits_gross_plus_costs_on_the_trade_date(self) -> None:
        portfolio = funded().apply_fill(fill(Side.BUY, 300, 4_150, D0, fee=450), day(2))
        assert portfolio.cash_balance() == rp(10_000_000 - 1_245_000 - 450)
        assert portfolio.settled_cash(D0) == portfolio.cash_balance()
        assert portfolio.position(BBRI) == Position(BBRI, 300, rp(1_245_450))

    def test_a_second_buy_adds_to_the_position(self) -> None:
        portfolio = (
            funded()
            .apply_fill(fill(Side.BUY, 100, 4_000, D0), day(2))
            .apply_fill(fill(Side.BUY, 200, 4_300, day(1), fee=10), day(3))
        )
        assert portfolio.position(BBRI) == Position(BBRI, 300, rp(400_000 + 860_010))

    def test_exactly_enough_settled_cash_is_accepted(self) -> None:
        portfolio = funded(1_245_450).apply_fill(fill(Side.BUY, 300, 4_150, D0, fee=450), day(2))
        assert portfolio.cash_balance() == rp(0)

    def test_one_rupiah_short_is_refused(self) -> None:
        with pytest.raises(
            InsufficientCashError,
            match="2026-01-05: needs IDR 1,245,450 but only IDR 1,245,449 is settled",
        ):
            funded(1_245_449).apply_fill(fill(Side.BUY, 300, 4_150, D0, fee=450), day(2))

    def test_positions_stay_sorted_by_symbol(self) -> None:
        portfolio = (
            funded()
            .apply_fill(fill(Side.BUY, 100, 3_000, D0, stock=TLKM), day(2))
            .apply_fill(fill(Side.BUY, 100, 4_000, D0), day(2))
        )
        assert [p.instrument.symbol for p in portfolio.positions] == ["BBRI", "TLKM"]


class TestSell:
    def held(self) -> Portfolio:
        return funded().apply_fill(fill(Side.BUY, 300, 4_000, D0), day(2))

    def test_proceeds_are_unsettled_until_the_settlement_date(self) -> None:
        portfolio = self.held().apply_fill(fill(Side.SELL, 300, 4_000, day(1), fee=100), day(3))
        assert portfolio.unsettled_cash(day(2)) == rp(1_200_000 - 100)
        assert portfolio.settled_cash(day(2)) == rp(10_000_000 - 1_200_000)
        assert portfolio.settled_cash(day(3)) == rp(10_000_000 - 100)
        assert portfolio.unsettled_cash(day(3)) == rp(0)

    def test_sale_proceeds_cannot_fund_a_same_day_buy(self) -> None:
        cash_poor = (
            funded(1_200_000)
            .apply_fill(fill(Side.BUY, 300, 4_000, D0), day(2))
            .apply_fill(fill(Side.SELL, 300, 4_000, day(1)), day(3))
        )
        with pytest.raises(InsufficientCashError, match="needs IDR 400,000 but only IDR 0"):
            cash_poor.apply_fill(fill(Side.BUY, 100, 4_000, day(1), stock=TLKM), day(3))

    def test_a_full_sale_removes_the_position(self) -> None:
        portfolio = self.held().apply_fill(fill(Side.SELL, 300, 4_100, day(1)), day(3))
        assert portfolio.position(BBRI) is None
        assert portfolio.positions == ()

    def test_a_partial_sale_releases_cost_basis_rounded_up(self) -> None:
        portfolio = (
            funded()
            .apply_fill(fill(Side.BUY, 3, 333, D0, fee=1), day(2))  # basis Rp 1,000 for 3
            .apply_fill(fill(Side.SELL, 1, 333, day(1)), day(3))
        )
        # 1/3 of Rp 1,000 is 333.33; the released basis rounds up to 334, leaving 666.
        assert portfolio.position(BBRI) == Position(BBRI, 2, rp(666))

    def test_cannot_sell_more_than_is_held(self) -> None:
        with pytest.raises(
            InsufficientSharesError, match="2026-01-06: cannot sell 301 BBRI, only 300 held"
        ):
            self.held().apply_fill(fill(Side.SELL, 301, 4_000, day(1)), day(3))

    def test_cannot_sell_what_is_not_held(self) -> None:
        with pytest.raises(InsufficientSharesError, match="cannot sell 1 TLKM, only 0 held"):
            self.held().apply_fill(fill(Side.SELL, 1, 3_000, day(1), stock=TLKM), day(3))

    def test_costs_above_the_gross_are_refused(self) -> None:
        with pytest.raises(
            NegativeProceedsError,
            match="2026-01-06: selling 1 BBRI raises IDR 4,000 but costs IDR 4,001",
        ):
            self.held().apply_fill(fill(Side.SELL, 1, 4_000, day(1), fee=4_001), day(3))

    def test_costs_equal_to_the_gross_are_allowed(self) -> None:
        portfolio = self.held().apply_fill(fill(Side.SELL, 1, 4_000, day(1), fee=4_000), day(3))
        assert portfolio.cash_balance() == rp(10_000_000 - 1_200_000)


class TestRefusals:
    def test_a_back_dated_fill_is_refused_and_changes_nothing(self) -> None:
        later = funded().deposit(rp(1), day(1))
        with pytest.raises(
            ChronologyError, match="2026-01-05 is before the last recorded movement, on 2026-01-06"
        ):
            later.apply_fill(fill(Side.BUY, 1, 100, D0), day(2))
        assert later.cash_balance() == rp(10_000_001)

    @pytest.mark.parametrize("side", [Side.BUY, Side.SELL])
    def test_settlement_cannot_precede_the_trade(self, side: Side) -> None:
        held = funded().apply_fill(fill(Side.BUY, 100, 100, D0), D0)
        with pytest.raises(
            ValueError, match="settles on 2026-01-05, before the trade on 2026-01-06"
        ):
            held.apply_fill(fill(side, 1, 100, day(1)), D0)

    def test_settles_on_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="settles_on must be a date, got datetime"):
            funded().apply_fill(fill(Side.BUY, 1, 100, D0), datetime(2026, 1, 7, tzinfo=UTC))

    def test_a_fill_in_another_currency_is_refused(self) -> None:
        apple = Instrument("AAPL", "NASDAQ", USD)
        order = Order(apple, Side.BUY, 1, D0)
        usd_fill = Fill(order, D0, 1, Money(100, USD), Costs.zero(USD))
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            funded().apply_fill(usd_fill, day(2))

    def test_settled_cash_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="on must be a date, got datetime"):
            funded().settled_cash(datetime(2026, 1, 5, tzinfo=UTC))


class TestValuation:
    def test_values_holdings_at_the_given_closes(self) -> None:
        portfolio = (
            funded()
            .apply_fill(fill(Side.BUY, 300, 4_000, D0), day(2))
            .apply_fill(fill(Side.BUY, 100, 3_000, D0, stock=TLKM), day(2))
        )
        closes = {BBRI: rp(4_200), TLKM: rp(2_900)}
        assert portfolio.holdings_value(closes) == rp(300 * 4_200 + 100 * 2_900)

    def test_an_empty_portfolio_is_worth_nothing(self) -> None:
        assert Portfolio.empty(IDR).holdings_value({}) == rp(0)

    def test_a_missing_close_is_named(self) -> None:
        portfolio = funded().apply_fill(fill(Side.BUY, 100, 3_000, D0, stock=TLKM), day(2))
        with pytest.raises(MissingPriceError, match="no close price for TLKM"):
            portfolio.holdings_value({BBRI: rp(1)})


class TestDirectConstruction:
    def test_a_valid_snapshot_is_accepted(self) -> None:
        movement = CashMovement(D0, MovementKind.DEPOSIT, rp(5), D0)
        snapshot = Portfolio(IDR, (Position(BBRI, 1, rp(1)), Position(TLKM, 1, rp(1))), (movement,))
        assert snapshot.cash_balance() == rp(5)

    def test_positions_must_be_sorted(self) -> None:
        with pytest.raises(ValueError, match="positions must be unique and sorted"):
            Portfolio(IDR, (Position(TLKM, 1, rp(1)), Position(BBRI, 1, rp(1))))

    def test_positions_must_be_unique(self) -> None:
        with pytest.raises(ValueError, match="positions must be unique and sorted"):
            Portfolio(IDR, (Position(BBRI, 1, rp(1)), Position(BBRI, 2, rp(2))))

    def test_positions_must_be_in_the_portfolio_currency(self) -> None:
        apple = Instrument("AAPL", "NASDAQ", USD)
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Portfolio(IDR, (Position(apple, 1, Money(1, USD)),))

    def test_the_ledger_must_be_in_date_order(self) -> None:
        later = CashMovement(day(1), MovementKind.DEPOSIT, rp(1), day(1))
        earlier = CashMovement(D0, MovementKind.DEPOSIT, rp(1), D0)
        with pytest.raises(ChronologyError, match="2026-01-05 is before the last recorded"):
            Portfolio(IDR, (), (later, earlier))

    def test_movements_must_be_in_the_portfolio_currency(self) -> None:
        movement = CashMovement(D0, MovementKind.DEPOSIT, Money(1, USD), D0)
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Portfolio(IDR, (), (movement,))

    def test_a_movement_cannot_settle_before_it_happens(self) -> None:
        with pytest.raises(
            ValueError, match="settles on 2026-01-05, before the trade on 2026-01-06"
        ):
            CashMovement(day(1), MovementKind.SELL, rp(1), D0)

    def test_movement_dates_refuse_datetime(self) -> None:
        with pytest.raises(TypeError, match="movement day must be a date"):
            CashMovement(datetime(2026, 1, 5, tzinfo=UTC), MovementKind.DEPOSIT, rp(1), D0)
