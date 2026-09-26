"""SimulatedBroker: yesterday's orders fill at today's open (M3 spec §5), on real IDX rules."""

from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.broker import FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.money import IDR, Money
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import Bar, Costs, Fill, Instrument, Order, Side
from steadyhand_idx import IdxMarketRules

YESTERDAY = date(2025, 6, 2)
TODAY = date(2025, 6, 3)
SETTLES = date(2025, 6, 5)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
REFERENCES = {BBCA: Money(9_000, IDR), BBRI: Money(4_000, IDR)}


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def bar(stock: Instrument, open_: int, volume: int = 1_000_000, day: date = TODAY) -> Bar:
    return Bar(stock, day, rp(open_), rp(open_ * 2), rp(1), rp(open_), volume)


def portfolio(cash: int, held: dict[Instrument, int] | None = None) -> Portfolio:
    """*cash* spendable today, plus *held* shares bought yesterday at no cost."""
    book = Portfolio.empty(IDR)
    if cash:
        book = book.deposit(rp(cash), YESTERDAY)
    for stock, quantity in (held or {}).items():
        book = book.deposit(rp(quantity), YESTERDAY)
        order = Order(stock, Side.BUY, quantity, YESTERDAY)
        book = book.apply_fill(Fill(order, YESTERDAY, quantity, rp(1), Costs.zero(IDR)), SETTLES)
    return book


def buy(quantity: int, stock: Instrument = BBCA) -> Order:
    return Order(stock, Side.BUY, quantity, YESTERDAY)


def sell(quantity: int, stock: Instrument = BBCA) -> Order:
    return Order(stock, Side.SELL, quantity, YESTERDAY)


def run(
    book: Portfolio, *orders: Order, bars: list[Bar] | None = None, **frozen: str
) -> FillResult:
    """Fill *orders* today. Keyword arguments freeze a stock by symbol, with the reason."""
    today = {b.instrument: b for b in (bars if bars is not None else [bar(BBCA, 9_000)])}
    stocks = {stock.symbol: stock for stock in (BBCA, BBRI)}
    kept = {stocks[symbol]: reason for symbol, reason in frozen.items()}
    return SimulatedBroker(rules()).fill(
        book, list(orders), Opening(TODAY, today, REFERENCES, kept)
    )


def test_a_buy_pays_the_open_plus_slippage_rounded_up_to_a_tick() -> None:
    result = run(portfolio(10_000_000), buy(100))
    (only,) = result.fills
    assert (only.day, only.quantity, only.price) == (TODAY, 100, rp(9_025))
    assert only.costs == Costs(rp(1_504), rp(390), rp(0))
    assert result.portfolio.cash_balance() == rp(10_000_000 - 902_500 - 1_894)
    assert (result.rejected, result.cuts, result.daily_cost) == ((), (), rp(0))


def test_a_sale_receives_the_open_less_slippage_rounded_down_and_settles_at_t_plus_2() -> None:
    result = run(portfolio(0, {BBCA: 100}), sell(100))
    (only,) = result.fills
    assert (only.quantity, only.price) == (100, rp(8_975))
    assert only.costs.total == rp(2_781)
    assert result.portfolio.spendable_cash(TODAY) == rp(0)
    assert result.portfolio.spendable_cash(SETTLES) == rp(897_500 - 2_781)
    assert result.portfolio.position(BBCA) is None


def test_slippage_rounds_against_the_trader_before_the_tick() -> None:
    stock = Instrument("WIKA", "IDX", IDR)
    today = {stock: bar(stock, 150)}
    references = {stock: rp(150)}
    bought = SimulatedBroker(rules()).fill(
        portfolio(100_000), [buy(100, stock)], Opening(TODAY, today, references, {})
    )
    sold = SimulatedBroker(rules()).fill(
        portfolio(0, {stock: 100}), [sell(100, stock)], Opening(TODAY, today, references, {})
    )
    assert [f.price for f in bought.fills] == [rp(151)]
    assert [f.price for f in sold.fills] == [rp(149)]


def test_every_sell_fills_before_any_buy() -> None:
    orders = (buy(100, BBRI), sell(100), buy(100))
    bars = [bar(BBCA, 9_000), bar(BBRI, 4_000)]
    result = run(portfolio(2_000_000, {BBCA: 100}), *orders, bars=bars)
    assert [(f.order.side, f.order.instrument) for f in result.fills] == [
        (Side.SELL, BBCA),
        (Side.BUY, BBRI),
        (Side.BUY, BBCA),
    ]


@pytest.mark.parametrize(
    ("bars", "frozen", "reason"),
    [
        ([bar(BBCA, 9_000)], {"BBCA": "rights issue"}, "frozen: rights issue"),
        ([], {}, "no bar for BBCA on 2025-06-03"),
        ([bar(BBCA, 9_000, volume=0)], {}, "BBCA did not trade on 2025-06-03"),
        (
            [bar(BBCA, 10_800)],
            {},
            "fill price IDR 10,825 is outside the band IDR 7,650 to IDR 10,800",
        ),
    ],
)
def test_an_order_that_cannot_trade_is_rejected_with_its_reason(
    bars: list[Bar], frozen: dict[str, str], reason: str
) -> None:
    result = run(portfolio(10_000_000), buy(100), bars=bars, **frozen)
    assert result.fills == ()
    assert [(r.order, r.reason) for r in result.rejected] == [(buy(100), reason)]
    assert result.portfolio == portfolio(10_000_000)


def test_a_price_band_needs_a_previous_close() -> None:
    stock = Instrument("GOTO", "IDX", IDR)
    result = run(portfolio(10_000_000), buy(100, stock), bars=[bar(stock, 60)])
    assert [r.reason for r in result.rejected] == [
        "no previous close for GOTO to set the price band"
    ]


def test_a_price_on_the_band_edge_is_accepted() -> None:
    result = run(portfolio(0, {BBCA: 100}), sell(100), bars=[bar(BBCA, 7_665)])
    assert [f.price for f in result.fills] == [rp(7_650)]


def test_an_order_is_cut_to_a_tenth_of_the_volume_in_whole_lots() -> None:
    result = run(portfolio(10_000_000), buy(500), bars=[bar(BBCA, 9_000, volume=1_999)])
    assert [f.quantity for f in result.fills] == [100]
    assert [(c.quantity, c.reason) for c in result.cuts] == [
        (100, "cut to 10% of the day's 1,999 shares traded")
    ]


def test_an_order_is_rejected_when_a_tenth_of_the_volume_is_under_a_lot() -> None:
    result = run(portfolio(10_000_000), buy(100), bars=[bar(BBCA, 9_000, volume=999)])
    assert [r.reason for r in result.rejected] == [
        "10% of the day's 999 shares traded is less than a lot"
    ]


def test_a_buy_is_cut_to_the_lots_the_cash_pays_for() -> None:
    cash = 2 * (902_500 + 1_894)
    result = run(portfolio(cash), buy(300))
    assert [f.quantity for f in result.fills] == [200]
    assert [(c.quantity, c.reason) for c in result.cuts] == [
        (200, "cut to the IDR 1,808,788 that can be spent")
    ]
    # The costs of a trade round once, so two lots cost a rupiah less than two single lots.
    assert result.fills[0].costs.total == rp(3_787)
    assert result.portfolio.spendable_cash(TODAY) == rp(1)


def test_a_buy_the_cash_cannot_pay_for_is_rejected() -> None:
    result = run(portfolio(902_500 + 1_893), buy(100))
    assert [r.reason for r in result.rejected] == ["not enough cash: IDR 904,393 can be spent"]


def test_the_days_stamp_duty_is_held_back_from_a_buy_and_charged_once() -> None:
    cash = 10_830_000 + 22_722 + 10_000
    exact = run(portfolio(cash), buy(1_200))
    assert [f.quantity for f in exact.fills] == [1_200]
    assert exact.daily_cost == rp(10_000)
    assert exact.portfolio.spendable_cash(TODAY) == rp(0)
    assert exact.portfolio.ledger[-1].kind is MovementKind.DAILY_COST
    assert exact.portfolio.ledger[-1].settles_on == TODAY
    short = run(portfolio(cash - 1), buy(1_200))
    assert [f.quantity for f in short.fills] == [1_100]


def test_no_stamp_duty_on_a_day_of_ten_million_or_less() -> None:
    result = run(portfolio(10_000_000), buy(100))
    assert result.daily_cost == rp(0)
    assert MovementKind.DAILY_COST not in {m.kind for m in result.portfolio.ledger}


def test_a_sales_only_day_nets_its_stamp_duty_with_the_sales() -> None:
    result = run(portfolio(0, {BBCA: 1_200}), sell(1_200))
    assert result.daily_cost == rp(10_000)
    charge = result.portfolio.ledger[-1]
    assert (charge.kind, charge.amount, charge.settles_on) == (
        MovementKind.DAILY_COST,
        rp(-10_000),
        SETTLES,
    )
    assert result.portfolio.settled_cash(TODAY) == rp(0)
    assert result.portfolio.settled_cash(SETTLES) == rp(10_770_000 - 33_366 - 10_000)


def test_a_sale_is_refused_when_even_its_proceeds_cannot_pay_the_days_charge() -> None:
    day = date(2021, 6, 2)
    stock = Instrument("XXXX", "IDX", IDR)
    book = Portfolio.empty(IDR).deposit(rp(100), date(2021, 6, 1))
    order = Order(stock, Side.BUY, 100, date(2021, 6, 1))
    book = book.apply_fill(Fill(order, date(2021, 6, 1), 100, rp(1), Costs.zero(IDR)), day)
    today = {stock: bar(stock, 60, day=day)}
    result = SimulatedBroker(rules()).fill(
        book,
        [Order(stock, Side.SELL, 100, date(2021, 6, 1))],
        Opening(day, today, {stock: rp(60)}, {}),
    )
    assert [r.reason for r in result.rejected] == [
        "the day's charges of IDR 10,000 exceed the IDR 5,881 that could pay them"
    ]
    assert result.daily_cost == rp(0)


def test_settings_change_the_slippage_and_the_volume_cap() -> None:
    settings = FillSettings(slippage=Decimal(0), volume_cap=Decimal(1))
    today = {BBCA: bar(BBCA, 9_000, volume=500)}
    result = SimulatedBroker(rules(), settings).fill(
        portfolio(10_000_000), [buy(500)], Opening(TODAY, today, REFERENCES, {})
    )
    assert [(f.quantity, f.price) for f in result.fills] == [(500, rp(9_000))]


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({"slippage": 0.001}, TypeError, r"^slippage must be a finite Decimal, got 0\.001$"),
        ({"volume_cap": Decimal("Infinity")}, TypeError, r"^volume_cap must be a finite Decimal"),
        ({"slippage": Decimal(1)}, ValueError, r"^slippage must be at least 0 and below 1, got 1$"),
        ({"slippage": Decimal(-1)}, ValueError, r"^slippage must be at least 0 and below 1"),
        (
            {"volume_cap": Decimal(0)},
            ValueError,
            r"^volume_cap must be above 0 and at most 1, got 0$",
        ),
        ({"volume_cap": Decimal("1.1")}, ValueError, r"^volume_cap must be above 0 and at most 1"),
    ],
)
def test_settings_are_checked(
    kwargs: dict[str, object], error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        FillSettings(**kwargs)  # type: ignore[arg-type]


def test_the_defaults_are_the_specs() -> None:
    assert FillSettings() == FillSettings(Decimal("0.001"), Decimal("0.10"))


@given(
    cash=st.integers(0, 30_000_000),
    held=st.integers(0, 40),
    orders=st.lists(
        st.tuples(
            st.sampled_from([Side.BUY, Side.SELL]),
            st.sampled_from([BBCA, BBRI]),
            st.integers(1, 30),
        ),
        max_size=6,
    ),
    opens=st.tuples(st.integers(7_700, 10_700), st.integers(3_450, 4_950)),
    volumes=st.tuples(st.integers(0, 50_000), st.integers(0, 50_000)),
)
def test_fills_keep_cash_whole_lots_ticks_and_bands(
    cash: int,
    held: int,
    orders: list[tuple[Side, Instrument, int]],
    opens: tuple[int, int],
    volumes: tuple[int, int],
) -> None:
    book = portfolio(cash, {BBCA: held * 100, BBRI: held * 100} if held else {})
    selling = dict.fromkeys((BBCA, BBRI), 0)
    placed = []
    for side, stock, lots in orders:
        if side is Side.SELL:
            if selling[stock] + lots > held:
                continue  # the sizer never sells more than is held
            selling[stock] += lots
        placed.append(Order(stock, side, lots * 100, YESTERDAY))
    bars = [bar(BBCA, opens[0], volumes[0]), bar(BBRI, opens[1], volumes[1])]
    result = run(book, *placed, bars=bars)
    for probe in (TODAY, date(2025, 6, 4), SETTLES):
        assert result.portfolio.settled_cash(probe).amount >= 0
    movements = result.portfolio.ledger[len(book.ledger) :]
    expected = [
        -(f.gross + f.costs.total) if f.order.side is Side.BUY else f.gross - f.costs.total
        for f in result.fills
    ]
    traded = sum((f.gross for f in result.fills), rp(0))
    daily = rules().daily_costs(traded, TODAY) if result.fills else rp(0)
    if daily.amount:
        expected.append(-daily)
    assert [m.amount for m in movements] == expected
    assert result.daily_cost == daily
    for f in result.fills:
        assert f.quantity % 100 == 0
        assert rules().round_to_tick(f.order.instrument, f.price, f.order.side, TODAY) == f.price
        low, high = rules().price_band(f.order.instrument, REFERENCES[f.order.instrument], TODAY)
        assert low <= f.price <= high
    assert len(result.fills) + len(result.rejected) == len(placed)
