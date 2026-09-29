"""run_day: one pure trading day, from yesterday's state to today's (M3 spec §3, §4-§7.4)."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from steadyhand.corporate import Entitlement, Holdings
from steadyhand.engine import (
    DataValidationError,
    DayInputs,
    DayOrderError,
    DayReport,
    EngineSettings,
    EngineState,
    run_day,
)
from steadyhand.exemption import DividendClaim, Protection
from steadyhand.money import IDR, Money
from steadyhand.notes import (
    CORPORATE_SPLIT_ORDER_CANCELLED,
    DATA_BAR_MISSING,
    EXEMPTION_CLAIM_BROKEN,
    EXEMPTION_DEADLINE_MISSED,
    RISK_HALT_DAILY_LOSS,
    TRADE_EXCLUDED,
    TRADE_FROZEN,
    TRADE_NO_BAR,
    TRADE_NOT_IN_UNIVERSE,
    TRADE_REFUSED,
    Note,
)
from steadyhand.portfolio import MissingPriceError, MovementKind
from steadyhand.risk import Halt, RiskLimits
from steadyhand.strategies import BuyAndHold, Decision, Memory
from steadyhand.types import Bar, CashDividend, Instrument, Order, Side, Split
from steadyhand.view import MarketView, PortfolioView, PriceHistory
from steadyhand_idx import IdxMarketRules

D1, D2, D3, D4 = date(2025, 6, 2), date(2025, 6, 3), date(2025, 6, 4), date(2025, 6, 5)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
MEMBERS = frozenset({BBCA, BBRI})


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


@cache
def half() -> EngineSettings:
    """At most half the portfolio in one stock, so two stocks can be fully invested."""
    return EngineSettings(limits=RiskLimits(max_weight=Decimal("0.5")))


class _Fixed:
    """A strategy that always asks for the same weights."""

    def __init__(self, weights: Mapping[Instrument, Decimal]) -> None:
        self._weights = weights

    @property
    def name(self) -> str:
        return "fixed"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        return Decision(self._weights)


class _Untouchable:
    """A strategy that must not be asked: ordering has halted."""

    @property
    def name(self) -> str:
        return "untouchable"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        msg = "a halted run asked its strategy to decide"
        raise AssertionError(msg)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def bar(stock: Instrument, day: date, open_: int, close: int | None = None) -> Bar:
    shut = open_ if close is None else close
    return Bar(stock, day, rp(open_), rp(max(open_, shut)), rp(min(open_, shut)), rp(shut), 10**6)


def market(bbca: list[tuple[int, int]], bbri: list[tuple[int, int]]) -> PriceHistory:
    """Bars from D1 on, one (open, close) pair per day for each stock."""
    days = [D1, D2, D3, D4]
    return PriceHistory(
        [bar(BBCA, day, *pair) for day, pair in zip(days, bbca, strict=False)]
        + [bar(BBRI, day, *pair) for day, pair in zip(days, bbri, strict=False)]
    )


def steady() -> PriceHistory:
    return market(
        [(9_000, 9_000), (9_000, 9_100), (9_100, 9_100)],
        [(4_000, 4_000), (4_000, 4_050), (4_050, 4_050)],
    )


def day_one() -> tuple[EngineState, DayReport]:
    state = EngineState.opening(rp(10_000_000), D1)
    return run_day(state, DayInputs(D1, steady(), members=MEMBERS), BuyAndHold(), rules(), half())


def day_two() -> tuple[EngineState, DayReport]:
    state, _ = day_one()
    return run_day(state, DayInputs(D2, steady(), members=MEMBERS), BuyAndHold(), rules(), half())


def test_day_one_queues_buy_and_holds_orders_and_remembers_its_set() -> None:
    state, report = day_one()
    assert report.fills == ()
    assert report.queued == (Order(BBCA, Side.BUY, 500, D1), Order(BBRI, Side.BUY, 1_200, D1))
    assert (report.value, report.holdings_value, report.settled) == (
        rp(10_000_000),
        rp(0),
        rp(10_000_000),
    )
    assert state.holdings.pending == report.queued
    assert state.memory == {"set": "IDX:BBCA IDX:BBRI"}
    assert (state.last_day, state.halt) == (D1, None)
    assert state.units.price == 1


def test_orders_fill_at_the_next_open_and_the_day_is_valued_at_the_close() -> None:
    state, report = day_two()
    assert [(f.order.instrument, f.quantity, f.price) for f in report.fills] == [
        (BBCA, 500, rp(9_025)),
        (BBRI, 1_200, rp(4_010)),
    ]
    spent = sum((f.gross + f.costs.total for f in report.fills), rp(0))
    assert report.holdings_value == rp(500 * 9_100 + 1_200 * 4_050)
    assert report.value == rp(10_000_000) - spent + report.holdings_value
    assert report.settled == rp(10_000_000) - spent
    assert report.daily_cost == rp(0)
    assert state.holdings.last_closes == {BBCA: rp(9_100), BBRI: rp(4_050)}
    assert state.units.price == Decimal(report.value.amount) / Decimal(10_000_000)


def test_run_day_is_pure_and_repeatable() -> None:
    before, _ = day_one()
    snapshot = repr(before)
    inputs = DayInputs(D2, steady(), members=MEMBERS)
    first = run_day(before, inputs, BuyAndHold(), rules(), half())
    second = run_day(before, inputs, BuyAndHold(), rules(), half())
    assert repr(before) == snapshot
    assert first == second


def test_a_day_must_follow_the_last_and_be_a_trading_day() -> None:
    state, _ = day_one()
    with pytest.raises(
        DayOrderError, match=r"^2025-06-02 is not after the last day run, 2025-06-02$"
    ):
        run_day(state, DayInputs(D1, steady()), BuyAndHold(), rules())
    with pytest.raises(DayOrderError, match=r"^2025-06-06 is not a trading day$"):
        run_day(state, DayInputs(date(2025, 6, 6), steady()), BuyAndHold(), rules())


def test_a_close_outside_the_band_stops_the_day() -> None:
    history = market([(9_000, 9_000), (9_000, 7_625)], [])
    state = EngineState.opening(rp(1_000_000), D2)
    with pytest.raises(
        DataValidationError,
        match=(
            r"^BBCA on 2025-06-03: the close IDR 7,625 is outside the band IDR 7,650 to "
            r"IDR 10,800 around the previous close IDR 9,000$"
        ),
    ):
        run_day(state, DayInputs(D2, history), BuyAndHold(), rules())


@pytest.mark.parametrize(
    "exempt",
    [
        {"resumed": frozenset({BBCA})},
        {"actions": (Split(BBCA, D2, 1, 5),)},
    ],
    ids=["resumed after refused days", "split ex-date"],
)
def test_the_band_check_skips_resumed_stocks_and_split_ex_dates(exempt: dict[str, object]) -> None:
    history = market([(9_000, 9_000), (1_800, 1_800)], [])
    state = EngineState.opening(rp(1_000_000), D2)
    _, report = run_day(state, DayInputs(D2, history, **exempt), BuyAndHold(), rules())  # type: ignore[arg-type]
    assert report.day == D2


def test_a_stocks_first_bar_is_not_band_checked() -> None:
    history = PriceHistory([bar(BBCA, D2, 1_800)])
    _, report = run_day(
        EngineState.opening(rp(1_000_000), D2), DayInputs(D2, history), BuyAndHold(), rules()
    )
    assert report.value == rp(1_000_000)


def test_a_loss_at_the_limit_halts_ordering_for_the_rest_of_the_run() -> None:
    state, _ = day_two()
    crash = market(
        [(9_000, 9_000), (9_000, 9_100), (9_100, 7_900)],
        [(4_000, 4_000), (4_000, 4_050), (4_050, 3_450)],
    )
    state, report = run_day(
        state, DayInputs(D3, crash, members=MEMBERS), BuyAndHold(), rules(), half()
    )
    assert report.halt is not None
    assert report.halt.day == D3
    assert report.halt.cause.key == RISK_HALT_DAILY_LOSS
    assert report.halt.cause.text.startswith("daily loss limit: the unit value fell ")
    assert (report.queued, state.holdings.pending) == ((), ())
    assert state.halt == report.halt
    later = market(
        [(9_000, 9_000), (9_000, 9_100), (9_100, 7_900), (7_900, 8_000)],
        [(4_000, 4_000), (4_000, 4_050), (4_050, 3_450), (3_450, 3_500)],
    )
    state, report = run_day(
        state, DayInputs(D4, later, members=MEMBERS), _Untouchable(), rules(), half()
    )
    assert (report.halt, report.queued) == (None, ())
    assert state.halt is not None
    assert state.halt.day == D3
    assert [p.quantity for p in state.holdings.portfolio.positions] == [500, 1_200]


def test_dividends_still_arrive_while_halted() -> None:
    state, _ = day_one()
    due = Entitlement(BBCA, D1, D2, rp(12_500))
    halted = EngineState(
        Holdings(state.holdings.portfolio, (), (due,)),
        state.units,
        Halt(D1, Note(RISK_HALT_DAILY_LOSS, "test")),
        D1,
    )
    after, report = run_day(
        halted, DayInputs(D2, steady(), members=MEMBERS), _Untouchable(), rules()
    )
    assert report.paid == (due,)
    assert (report.tax, report.fills, report.queued) == (rp(1_250), (), ())
    assert after.holdings.portfolio.cash_balance() == rp(10_000_000 + 12_500 - 1_250)
    assert (report.notes, after.holdings.claims) == ((), ())


def test_with_the_exemption_on_a_dividend_opens_a_claim_the_next_state_keeps() -> None:
    state, _ = day_one()
    due = Entitlement(BBCA, D1, D2, rp(12_500))
    halted = EngineState(
        Holdings(state.holdings.portfolio, (), (due,)),
        state.units,
        Halt(D1, Note(RISK_HALT_DAILY_LOSS, "test")),
        D1,
    )
    exempt = EngineSettings(dividend_reinvestment_exemption=True)
    inputs = DayInputs(D2, steady(), members=MEMBERS)
    after, report = run_day(halted, inputs, _Untouchable(), rules(), exempt)
    assert (report.paid, report.tax, report.notes) == ((due,), rp(0), ())
    assert after.holdings.portfolio.cash_balance() == rp(10_000_000 + 12_500)  # no tax booked
    claim = DividendClaim(BBCA, D1, D2, rp(12_500), date(2026, 3, 31), rp(12_500))
    assert after.holdings.claims == (claim,)
    later, _ = run_day(after, DayInputs(D3, steady(), members=MEMBERS), _Untouchable(), rules())
    assert later.holdings.claims == (claim,)


def with_claim(state: EngineState, claim: DividendClaim) -> EngineState:
    return replace(state, holdings=replace(state.holdings, claims=(claim,)))


def test_with_the_exemption_on_todays_buys_cover_an_open_claim() -> None:
    state, _ = day_one()
    claim = DividendClaim(BBCA, date(2025, 5, 28), D1, rp(12_500), date(2026, 3, 31), rp(12_500))
    exempt = replace(half(), dividend_reinvestment_exemption=True)
    inputs = DayInputs(D2, steady(), members=MEMBERS)
    after, report = run_day(with_claim(state, claim), inputs, BuyAndHold(), rules(), exempt)
    assert [fill.order.instrument for fill in report.fills] == [BBCA, BBRI]
    # The first buy, BBCA's 500 shares at about 9,000, covers all 12,500; held through 2027.
    protected = (Protection(rp(12_500), date(2027, 12, 31)),)
    assert after.holdings.claims == (replace(claim, uncovered=rp(0), protections=protected),)
    assert (report.tax, report.notes) == (rp(0), ())


def test_a_missed_deadline_adds_its_tax_and_note_to_the_days_report() -> None:
    state, _ = day_one()
    claim = DividendClaim(BBCA, date(2025, 5, 27), date(2025, 5, 28), rp(12_500), D1, rp(12_500))
    exempt = replace(half(), dividend_reinvestment_exemption=True)
    inputs = DayInputs(D2, steady(), members=MEMBERS)
    after, report = run_day(with_claim(state, claim), inputs, BuyAndHold(), rules(), exempt)
    assert report.tax == rp(1_250)  # the day's buys come after the 2 June deadline
    assert [note.key for note in report.notes] == [EXEMPTION_DEADLINE_MISSED]
    assert after.holdings.claims == ()
    taxes = [m for m in after.holdings.portfolio.ledger if m.kind is MovementKind.TAX]
    assert [(m.amount, m.day) for m in taxes] == [(rp(-1_250), D2)]


def test_a_shortfall_is_kept_across_days_and_breaks_when_its_trade_would_settle() -> None:
    state, _ = day_one()  # cash only: nothing is invested
    protected = (Protection(rp(12_500), date(2027, 12, 31)),)
    claim = DividendClaim(
        BBCA, date(2025, 5, 27), date(2025, 5, 28), rp(12_500), date(2026, 3, 31), rp(0), protected
    )
    holdings = Holdings(state.holdings.portfolio, claims=(claim,))
    current = EngineState(holdings, state.units, Halt(D1, Note(RISK_HALT_DAILY_LOSS, "test")), D1)
    kept: list[tuple[date | None, Money]] = []
    for day in (D2, D3, D4):  # D2's trade would settle on D4
        current, report = run_day(
            current, DayInputs(day, steady(), members=MEMBERS), _Untouchable(), rules()
        )
        kept.append((current.holdings.shortfall_since, report.tax))
    assert kept == [(D2, rp(0)), (D2, rp(0)), (None, rp(1_250))]
    assert [note.key for note in report.notes] == [EXEMPTION_CLAIM_BROKEN]
    assert current.holdings.claims == ()


def test_a_stock_bought_at_todays_open_has_no_entitlement() -> None:
    state, _ = day_one()
    dividend = CashDividend(BBCA, D2, Decimal(100))
    inputs = DayInputs(D2, steady(), actions=(dividend,), members=MEMBERS)
    _, report = run_day(state, inputs, BuyAndHold(), rules(), half())
    assert report.entitled == ()
    assert [f.order.instrument for f in report.fills] == [BBCA, BBRI]


def test_a_dividend_on_a_holding_is_entitled_on_its_ex_date() -> None:
    state, _ = day_two()
    inputs = DayInputs(
        D3, steady(), actions=(CashDividend(BBCA, D3, Decimal(100)),), members=MEMBERS
    )
    after, report = run_day(state, inputs, BuyAndHold(), rules(), half())
    assert report.entitled == (Entitlement(BBCA, D3, date(2025, 6, 26), rp(50_000)),)
    assert after.holdings.entitlements == report.entitled


def test_a_split_cancels_pending_orders_and_rescales_the_last_close() -> None:
    state, _ = day_two()
    pending = Order(BBCA, Side.SELL, 100, D2)
    state = EngineState(
        Holdings(state.holdings.portfolio, (pending,), (), {}, state.holdings.last_closes),
        state.units,
        None,
        D2,
        state.memory,
    )
    history = market(
        [(9_000, 9_000), (9_000, 9_100)], [(4_000, 4_000), (4_000, 4_050), (4_050, 4_050)]
    )
    inputs = DayInputs(D3, history, actions=(Split(BBCA, D3, 1, 5),), members=MEMBERS)
    after, report = run_day(state, inputs, BuyAndHold(), rules(), half())
    cancelled = Note(CORPORATE_SPLIT_ORDER_CANCELLED, "split on ex-date")
    assert (report.rejected[0].order, report.rejected[0].reason) == (pending, cancelled)
    assert after.holdings.last_closes[BBCA] == rp(1_820)
    assert report.holdings_value == rp(2_500 * 1_820 + 1_200 * 4_050)


def test_a_held_stock_without_a_bar_is_valued_at_its_last_close_and_not_sold() -> None:
    state, _ = day_two()
    history = market(
        [(9_000, 9_000), (9_000, 9_100)], [(4_000, 4_000), (4_000, 4_050), (4_050, 4_050)]
    )
    seller = _Fixed({BBRI: Decimal("0.4")})
    _, report = run_day(state, DayInputs(D3, history, members=MEMBERS), seller, rules(), half())
    assert report.warnings == (
        Note(
            DATA_BAR_MISSING,
            "BBCA has no bar on 2025-06-04, so it is not traded; it is valued at its last "
            "close, IDR 9,100",
        ),
    )
    assert report.holdings_value == rp(500 * 9_100 + 1_200 * 4_050)
    assert [(r.order.side, r.reason) for r in report.rejected] == [
        (Side.SELL, Note(TRADE_NO_BAR, "no bar on 2025-06-04"))
    ]


def test_a_held_stock_that_becomes_excluded_is_frozen_and_not_sold() -> None:
    state, _ = day_two()
    inputs = DayInputs(D3, steady(), members=MEMBERS, excluded={BBCA: "Special Monitoring Board"})
    after, report = run_day(state, inputs, _Fixed({}), rules(), half())
    assert report.frozen == ((BBCA, "excluded: Special Monitoring Board"),)
    assert after.holdings.frozen == {BBCA: "excluded: Special Monitoring Board"}
    assert [(r.order.instrument, r.reason) for r in report.rejected] == [
        (BBCA, Note(TRADE_FROZEN, "frozen: excluded: Special Monitoring Board"))
    ]
    assert [o.instrument for o in report.queued] == [BBRI]


def test_an_exclusion_freezes_only_a_held_stock_and_only_once() -> None:
    state, _ = day_two()
    inputs = DayInputs(D3, steady(), members=MEMBERS, excluded={BBCA: "board"})
    state, _ = run_day(state, inputs, BuyAndHold(), rules(), half())
    history = market(
        [(9_000, 9_000), (9_000, 9_100), (9_100, 9_100), (9_100, 9_100)],
        [(4_000, 4_000), (4_000, 4_050), (4_050, 4_050), (4_050, 4_050)],
    )
    later = DayInputs(D4, history, members=MEMBERS, excluded={BBCA: "board"})
    _, report = run_day(state, later, BuyAndHold(), rules(), half())
    assert report.frozen == ()
    fresh = EngineState.opening(rp(10_000_000), D1)
    inputs = DayInputs(D1, steady(), members=MEMBERS, excluded={BBRI: "board"})
    after, report = run_day(fresh, inputs, _Fixed({BBRI: Decimal("0.1")}), rules(), half())
    assert (report.frozen, after.holdings.frozen) == ((), {})
    assert [r.reason for r in report.rejected] == [Note(TRADE_EXCLUDED, "excluded: board")]


def test_a_member_without_a_bar_is_not_bought_and_is_warned_about() -> None:
    history = PriceHistory([bar(BBCA, D1, 9_000)])
    state = EngineState.opening(rp(10_000_000), D1)
    _, report = run_day(
        state, DayInputs(D1, history, members=MEMBERS), BuyAndHold(), rules(), half()
    )
    assert report.warnings == (
        Note(DATA_BAR_MISSING, "BBRI has no bar on 2025-06-02, so it is not traded"),
    )
    assert [o.instrument for o in report.queued] == [BBCA]


def test_a_held_stock_with_no_price_at_all_stops_the_day() -> None:
    state, _ = day_two()
    blind = EngineState(Holdings(state.holdings.portfolio), state.units, None, D2)
    history = market(
        [(9_000, 9_000), (9_000, 9_100)], [(4_000, 4_000), (4_000, 4_050), (4_050, 4_050)]
    )
    with pytest.raises(MissingPriceError, match=r"^no close price for BBCA$"):
        run_day(blind, DayInputs(D3, history, members=MEMBERS), BuyAndHold(), rules(), half())


def test_a_refused_stock_is_neither_bought_nor_sold() -> None:
    state, _ = day_two()
    inputs = DayInputs(D3, steady(), members=MEMBERS, refused=frozenset({BBRI}))
    _, report = run_day(state, inputs, _Fixed({}), rules(), half())
    assert [(r.order.instrument, r.reason) for r in report.rejected] == [
        (BBRI, Note(TRADE_REFUSED, "the data source refused 2025-06-04"))
    ]


def test_a_weight_on_a_stock_outside_the_universe_is_dropped_with_its_reason() -> None:
    state = EngineState.opening(rp(10_000_000), D1)
    inputs = DayInputs(D1, steady(), members=frozenset({BBRI}))
    _, report = run_day(state, inputs, _Fixed({BBCA: Decimal("0.3")}), rules(), half())
    assert [(r.order.instrument, r.reason) for r in report.rejected] == [
        (BBCA, Note(TRADE_NOT_IN_UNIVERSE, "not in the universe on 2025-06-02"))
    ]


def test_the_monthly_contribution_arrives_on_the_months_first_trading_day() -> None:
    topped = EngineSettings(
        limits=RiskLimits(max_weight=Decimal("0.5")), monthly_contribution=rp(1_000_000)
    )
    state = EngineState.opening(rp(10_000_000), D1)
    state, report = run_day(
        state, DayInputs(D1, steady(), members=MEMBERS), BuyAndHold(), rules(), topped
    )
    assert report.deposit == rp(1_000_000)
    assert report.value == rp(11_000_000)
    assert (state.units.units, state.units.price) == (Decimal(11_000_000), Decimal(1))
    _, report = run_day(
        state, DayInputs(D2, steady(), members=MEMBERS), BuyAndHold(), rules(), topped
    )
    assert report.deposit == rp(0)


def test_each_report_carries_the_unit_price_at_the_close() -> None:
    _, first = day_one()
    assert first.unit_price == Decimal(1)
    state, second = day_two()
    # Rp10,000,000 bought 10,000,000 units at 1, so a unit is worth a ten-millionth of the value.
    assert second.unit_price == Decimal(second.value.amount) / Decimal(10_000_000)
    assert second.unit_price != Decimal(1)
    assert second.unit_price == state.units.price


def test_settings_and_state_check_their_parts() -> None:
    with pytest.raises(ValueError, match=r"^a monthly contribution must be positive, got IDR 0$"):
        EngineSettings(monthly_contribution=rp(0))
    with pytest.raises(ValueError, match=r"^pay_lag_trading_days must be at least 1, got 0$"):
        EngineSettings(pay_lag_trading_days=0)
    with pytest.raises(TypeError, match=r"^limits must be a RiskLimits, got NoneType$"):
        EngineSettings(limits=None)  # type: ignore[arg-type]
    with pytest.raises(
        TypeError, match=r"^dividend_reinvestment_exemption must be a bool, got str$"
    ):
        EngineSettings(dividend_reinvestment_exemption="yes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^holdings must be a Holdings, got NoneType$"):
        EngineState(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^halt must be a Halt, got str$"):
        EngineState(day_one()[0].holdings, halt="halted")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^members must be a frozenset, got set$"):
        DayInputs(D1, steady(), members={BBCA})  # type: ignore[arg-type]


@settings(max_examples=40)
@given(
    moves=st.lists(st.tuples(st.integers(-12, 12), st.integers(-12, 12)), min_size=3, max_size=3),
    capital=st.integers(1_000_000, 50_000_000),
)
def test_every_day_keeps_cash_whole_and_the_value_adding_up(
    moves: list[tuple[int, int]], capital: int
) -> None:
    closes = {BBCA: [9_000], BBRI: [4_000]}
    for bbca, bbri in moves:
        closes[BBCA].append(closes[BBCA][-1] // 25 * 25 + 25 * bbca)
        closes[BBRI].append(closes[BBRI][-1] // 10 * 10 + 10 * bbri)
    days = [D1, D2, D3, D4]
    history = PriceHistory(
        [
            bar(stock, day, path[n - 1] if n else path[0], path[n])
            for stock, path in closes.items()
            for n, day in enumerate(days)
        ]
    )
    state = EngineState.opening(rp(capital), D1)
    for day in days:
        state, report = run_day(
            state, DayInputs(day, history, members=MEMBERS), BuyAndHold(), rules(), half()
        )
        portfolio = state.holdings.portfolio
        assert report.settled.amount >= 0
        assert report.value == portfolio.cash_balance() + report.holdings_value
        assert all(p.quantity % 100 == 0 for p in portfolio.positions)
        charges = [
            m for m in portfolio.ledger if m.kind is MovementKind.DAILY_COST and m.day == day
        ]
        assert len(charges) == (1 if report.daily_cost.amount else 0)
