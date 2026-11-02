"""New cash shared by water-filling (#486): hand-computed, one test per case.

A 1,000 portfolio throughout. TLKM is held but never bought, so the cash and the stocks bought
add up to 1,000 with the room each case needs.
"""

from decimal import Decimal

from steadyhand._ratio import ratio_down
from steadyhand.money import IDR, Money
from steadyhand.strategies._top_up import top_up
from steadyhand.types import Instrument
from steadyhand.view import PortfolioView

BBCA, BBRI, TLKM, UNVR = (Instrument(code, "IDX", IDR) for code in ("BBCA", "BBRI", "TLKM", "UNVR"))
QUARTER = Decimal("0.25")


def portfolio(spendable: int, held: dict[Instrument, int]) -> PortfolioView:
    holdings = {stock: Money(value, IDR) for stock, value in held.items()}
    return PortfolioView(
        Money(spendable + sum(held.values()), IDR), Money(spendable, IDR), holdings
    )


def test_a_stock_with_little_room_leaves_the_rest_of_its_share_to_the_others() -> None:
    # BBRI at 24%, with least room, is filled first though BBCA comes first by symbol: it takes
    # 1% (10), and the other 290 go to BBCA, which takes its 25%. 50 stay cash.
    found = top_up(portfolio(300, {BBRI: 240, TLKM: 460}), [BBCA, BBRI], QUARTER)
    assert found == {BBCA: Decimal("0.25"), BBRI: Decimal("0.25")}


def test_cash_short_of_every_cap_is_shared_equally() -> None:
    found = top_up(portfolio(300, {TLKM: 700}), [BBCA, BBRI], QUARTER)
    assert found == {BBCA: Decimal("0.15"), BBRI: Decimal("0.15")}


def test_ample_cash_fills_every_stock_to_its_cap() -> None:
    found = top_up(portfolio(1000, {}), [BBCA, BBRI], QUARTER)
    assert found == {BBCA: Decimal("0.25"), BBRI: Decimal("0.25")}


def test_a_stock_at_or_above_its_cap_gets_nothing_and_the_others_get_its_share() -> None:
    found = top_up(portfolio(200, {BBCA: 300, BBRI: 250, TLKM: 250}), [BBCA, BBRI, UNVR], QUARTER)
    assert found == {BBCA: Decimal("0.3"), BBRI: Decimal("0.25"), UNVR: Decimal("0.2")}


def test_equal_room_is_filled_by_market_then_symbol_so_the_odd_rupiah_goes_last() -> None:
    # 301 // 2 = 150 to BBCA first; the 151 left go to BBRI.
    found = top_up(portfolio(301, {TLKM: 699}), [BBRI, BBCA], QUARTER)
    assert found == {BBCA: Decimal("0.15"), BBRI: Decimal("0.151")}


def test_a_stock_capped_mid_way_counts_its_part_rupiah_as_a_whole_one() -> None:
    # A 3,000 portfolio and a cap of 1/3 (999.99... rupiah). BBCA at 999 has room for 0.99...,
    # which uses a whole rupiah of the 501, so BBRI, uncapped, is offered 500, not 501.
    target = Decimal(1) / Decimal(3)
    found = top_up(portfolio(501, {BBCA: 999, TLKM: 1500}), [BBCA, BBRI], target)
    assert found == {BBCA: target, BBRI: ratio_down(500, 3000)}


def test_nothing_to_buy_gives_nothing() -> None:
    assert top_up(portfolio(500, {TLKM: 500}), [], QUARTER) == {}
