"""Decision and buy-and-hold: fix the day-one set, never sell, reinvest equally (M3 spec §6.6)."""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.money import IDR, Money
from steadyhand.strategies import BuyAndHold, Decision, InvalidWeightsError, Strategy
from steadyhand.types import Instrument
from steadyhand.view import MarketView, PortfolioView, PriceHistory, Tradable

D0 = date(2025, 6, 2)
STOCKS = [Instrument(code, "IDX", IDR) for code in ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")]
ASII, BBCA, BBRI, TLKM, UNVR = STOCKS


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def view(buyable: set[Instrument], sellable: set[Instrument] | None = None) -> MarketView:
    tradable = Tradable(D0, frozenset(buyable), frozenset(sellable or set()), {})
    return MarketView(PriceHistory([]), D0, tradable)


def test_a_decision_holds_weights_and_memory() -> None:
    decision = Decision({BBCA: Decimal("0.6"), BBRI: Decimal("0.4")})
    assert decision.memory == {}
    assert sum(decision.weights.values()) == 1


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ({BBCA: 0.5}, r"^BBCA: a weight must be a Decimal, got float$"),
        ({BBCA: Decimal("-0.1")}, r"^BBCA: a weight must be finite and not negative, got -0\.1$"),
        ({BBCA: Decimal("NaN")}, r"^BBCA: a weight must be finite and not negative, got NaN$"),
        (
            {BBCA: Decimal("0.6"), BBRI: Decimal("0.4000001")},
            r"^weights sum to 1\.0000001, more than 1$",
        ),
    ],
)
def test_weights_that_cannot_be_a_portfolio_are_refused(weights: object, message: str) -> None:
    with pytest.raises(InvalidWeightsError, match=message):
        Decision(weights)  # type: ignore[arg-type]


def test_a_decision_checks_its_keys_and_memory() -> None:
    with pytest.raises(TypeError, match=r"^weighted stock must be an Instrument, got str$"):
        Decision({"BBCA": Decimal("0.5")})  # type: ignore[dict-item]
    with pytest.raises(TypeError, match=r"^memory value must be a str, got int$"):
        Decision({}, {"set": 1})  # type: ignore[dict-item]
    with pytest.raises(TypeError, match=r"^memory key must be a str, got int$"):
        Decision({}, {1: "x"})  # type: ignore[dict-item]


def test_it_is_a_strategy_named_buy_and_hold() -> None:
    strategy: Strategy = BuyAndHold()
    assert isinstance(strategy, Strategy)
    assert strategy.name == "buy-and-hold"


def test_day_one_fixes_the_set_and_splits_the_cash_equally() -> None:
    portfolio = PortfolioView(rp(9_000_000), rp(9_000_000), {})
    decision = BuyAndHold().decide(view({BBCA, BBRI, TLKM}), portfolio, {})
    third = Decimal("0.3333333333333333333333333333")
    assert decision.weights == {BBCA: third, BBRI: third, TLKM: third}
    assert decision.memory == {"set": "IDX:BBCA IDX:BBRI IDX:TLKM"}


def test_later_days_keep_holdings_and_buy_only_the_set() -> None:
    portfolio = PortfolioView(
        rp(10_000_000), rp(900_000), {BBCA: rp(4_000_000), BBRI: rp(5_000_000)}
    )
    memory = {"set": "IDX:BBCA IDX:BBRI IDX:TLKM"}
    decision = BuyAndHold().decide(view({BBCA, TLKM, ASII}, {BBCA, BBRI}), portfolio, memory)
    each = Decimal("0.045")
    assert decision.weights == {BBCA: Decimal("0.4") + each, BBRI: Decimal("0.5"), TLKM: each}
    assert decision.memory == memory


def test_an_empty_first_day_leaves_an_empty_set() -> None:
    portfolio = PortfolioView(rp(1_000_000), rp(1_000_000), {})
    first = BuyAndHold().decide(view(set()), portfolio, {})
    assert first.weights == {}
    later = BuyAndHold().decide(view({BBCA}), portfolio, first.memory)
    assert later.weights == {}


@given(
    held=st.dictionaries(st.sampled_from(STOCKS), st.integers(1, 10**10), max_size=5),
    spendable=st.integers(0, 10**10),
    unsettled=st.integers(0, 10**10),
    chosen=st.sets(st.sampled_from(STOCKS)),
    buyable=st.sets(st.sampled_from(STOCKS)),
)
def test_it_never_sells_and_buys_only_its_set(
    held: dict[Instrument, int],
    spendable: int,
    unsettled: int,
    chosen: set[Instrument],
    buyable: set[Instrument],
) -> None:
    value = sum(held.values()) + spendable + unsettled
    portfolio = PortfolioView(rp(value), rp(spendable), {i: rp(v) for i, v in held.items()})
    memory = {"set": " ".join(sorted(f"IDX:{i.symbol}" for i in chosen))}
    decision = BuyAndHold().decide(view(buyable), portfolio, memory)
    for instrument in held:
        assert decision.weights[instrument] >= portfolio.weight(instrument)
    bought = {i for i, weight in decision.weights.items() if weight > portfolio.weight(i)}
    assert bought <= chosen & buyable
    assert decision.memory == memory
