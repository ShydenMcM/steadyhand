"""Corporate actions: splits, dividend entitlements and payments, freezes (M3 spec §4)."""

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from steadyhand.corporate import PAY_LAG_TRADING_DAYS, Entitlement, Holdings, apply_actions
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import (
    CashDividend,
    CorporateAction,
    Costs,
    Fill,
    Instrument,
    Order,
    OtherAction,
    Side,
    Split,
)
from steadyhand_idx import IdxMarketRules

EX = date(2025, 6, 2)
PAY = date(2025, 6, 24)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


class _TaxFree(IdxMarketRules):
    """IDX, but in a market that taxes no dividend."""

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        return Money.zero(gross.currency)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def holding(**shares: int) -> Portfolio:
    """A portfolio holding the given shares of BBCA and BBRI, bought before the ex-date."""
    book = Portfolio.empty(IDR)
    for symbol, quantity in shares.items():
        stock = Instrument(symbol, "IDX", IDR)
        order = Order(stock, Side.BUY, quantity, date(2025, 5, 28))
        fill = Fill(order, date(2025, 5, 28), quantity, rp(1_000), Costs.zero(IDR))
        book = book.deposit(rp(quantity * 1_000), date(2025, 5, 28)).apply_fill(fill, EX)
    return book


def shares(portfolio: Portfolio, stock: Instrument) -> int:
    position = portfolio.position(stock)
    return 0 if position is None else position.quantity


def test_the_pay_lag_is_the_specs() -> None:
    assert PAY_LAG_TRADING_DAYS == 14


def test_a_split_scales_the_holding_and_the_last_close_and_cancels_its_orders() -> None:
    pending = (
        Order(BBCA, Side.SELL, 100, date(2025, 5, 30)),
        Order(BBRI, Side.BUY, 100, date(2025, 5, 30)),
    )
    before = Holdings(holding(BBCA=300), pending, last_closes={BBCA: rp(9_001)})
    outcome = apply_actions(before, [Split(BBCA, EX, 1, 5)], EX, rules())
    assert shares(outcome.holdings.portfolio, BBCA) == 1_500
    assert outcome.holdings.last_closes == {BBCA: rp(1_800)}
    assert outcome.holdings.pending == (pending[1],)
    assert [(r.order, r.reason) for r in outcome.cancelled] == [(pending[0], "split on ex-date")]
    assert outcome.warnings == ()


def test_a_split_of_a_stock_not_held_still_cancels_its_orders() -> None:
    pending = (Order(BBCA, Side.BUY, 100, date(2025, 5, 30)),)
    outcome = apply_actions(Holdings(holding(), pending), [Split(BBCA, EX, 1, 2)], EX, rules())
    assert outcome.holdings.pending == ()
    assert outcome.holdings.last_closes == {}


def test_a_reverse_split_warns_about_the_dropped_fraction() -> None:
    outcome = apply_actions(Holdings(holding(BBCA=1_203)), [Split(BBCA, EX, 5, 1)], EX, rules())
    assert shares(outcome.holdings.portfolio, BBCA) == 240
    assert outcome.warnings == (
        (
            "BBCA: the 1-for-5 split on 2025-06-02 turned 1203 shares into 240; the fraction of "
            "a share left over is dropped (cash in lieu is not modelled)"
        ),
    )


def test_a_split_that_leaves_no_whole_share_warns_with_zero() -> None:
    outcome = apply_actions(Holdings(holding(BBCA=4)), [Split(BBCA, EX, 5, 1)], EX, rules())
    assert outcome.holdings.portfolio.positions == ()
    assert "turned 4 shares into 0" in outcome.warnings[0]


def test_a_dividend_entitles_what_was_held_at_the_previous_close() -> None:
    dividend = CashDividend(BBCA, EX, Decimal("12.5"))
    outcome = apply_actions(Holdings(holding(BBCA=333, BBRI=100)), [dividend], EX, rules())
    assert outcome.entitled == (Entitlement(BBCA, EX, PAY, rp(4_162)),)
    assert outcome.holdings.entitlements == outcome.entitled
    assert outcome.paid == ()


def test_a_dividend_on_a_stock_not_held_entitles_nothing() -> None:
    outcome = apply_actions(
        Holdings(holding(BBRI=100)), [CashDividend(BBCA, EX, Decimal(50))], EX, rules()
    )
    assert outcome.entitled == ()


def test_a_dividend_worth_less_than_a_rupiah_entitles_nothing() -> None:
    outcome = apply_actions(
        Holdings(holding(BBCA=1)), [CashDividend(BBCA, EX, Decimal("0.5"))], EX, rules()
    )
    assert outcome.entitled == ()


def test_a_same_day_split_and_dividend_pays_on_the_shares_before_the_split() -> None:
    actions: list[CorporateAction] = [CashDividend(BBCA, EX, Decimal(10)), Split(BBCA, EX, 1, 5)]
    outcome = apply_actions(Holdings(holding(BBCA=100)), actions, EX, rules())
    assert [e.gross for e in outcome.entitled] == [rp(1_000)]
    assert shares(outcome.holdings.portfolio, BBCA) == 500


def test_an_entitlement_is_paid_and_taxed_on_its_pay_date_even_after_a_sale() -> None:
    due = Entitlement(BBCA, EX, PAY, rp(12_500))
    later = Entitlement(BBRI, EX, date(2025, 6, 25), rp(7_000))
    outcome = apply_actions(Holdings(holding(), entitlements=(due, later)), [], PAY, rules())
    assert outcome.paid == (due,)
    assert outcome.holdings.entitlements == (later,)
    assert outcome.tax == rp(1_250)
    kinds = [(m.kind, m.amount, m.settles_on) for m in outcome.holdings.portfolio.ledger]
    assert kinds == [(MovementKind.DIVIDEND, rp(12_500), PAY), (MovementKind.TAX, rp(-1_250), PAY)]


def test_an_untaxed_dividend_books_no_tax() -> None:
    due = Entitlement(BBCA, EX, PAY, rp(12_500))
    outcome = apply_actions(Holdings(holding(), entitlements=(due,)), [], PAY, _TaxFree())
    assert outcome.tax == rp(0)
    assert [m.kind for m in outcome.holdings.portfolio.ledger] == [MovementKind.DIVIDEND]


def test_another_action_freezes_a_held_stock_once() -> None:
    rights = OtherAction(BBCA, EX, "rights issue")
    outcome = apply_actions(
        Holdings(holding(BBCA=100)), [rights, OtherAction(BBRI, EX, "merger")], EX, rules()
    )
    assert outcome.holdings.frozen == {BBCA: "rights issue"}
    assert outcome.frozen == ((BBCA, "rights issue"),)
    again = apply_actions(
        outcome.holdings, [OtherAction(BBCA, date(2025, 6, 3), "second")], date(2025, 6, 3), rules()
    )
    assert again.holdings.frozen == {BBCA: "rights issue"}
    assert again.frozen == ()


def test_actions_must_be_dated_today_and_the_lag_positive() -> None:
    with pytest.raises(
        ValueError, match=r"^BBCA: an action dated 2025-06-03 applied on 2025-06-02$"
    ):
        apply_actions(Holdings(holding()), [Split(BBCA, date(2025, 6, 3), 1, 2)], EX, rules())
    with pytest.raises(ValueError, match=r"^pay_lag_trading_days must be at least 1, got 0$"):
        apply_actions(Holdings(holding()), [], EX, rules(), 0)


def test_an_entitlement_must_be_a_positive_amount_paid_after_its_ex_date() -> None:
    with pytest.raises(ValueError, match=r"^BBCA: paid 2025-06-02, not after its ex-date$"):
        Entitlement(BBCA, EX, EX, rp(1))
    with pytest.raises(ValueError, match=r"^BBCA: an entitlement must be positive, got IDR 0$"):
        Entitlement(BBCA, EX, PAY, rp(0))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        Entitlement(BBCA, EX, PAY, Money(1, Currency("USD", 2)))


def test_holdings_check_their_parts() -> None:
    with pytest.raises(TypeError, match=r"^portfolio must be a Portfolio, got NoneType$"):
        Holdings(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^pending order must be an Order, got str$"):
        Holdings(holding(), ("BBCA",))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^entitlement must be an Entitlement, got str$"):
        Holdings(holding(), entitlements=("BBCA",))  # type: ignore[arg-type]
