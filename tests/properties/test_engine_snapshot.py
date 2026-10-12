"""The snapshot properties at their full count (#290). Each calls its unit stand-in, in
tests/engine/test_snapshot.py, on every case it draws."""

from datetime import date, timedelta

import test_snapshot as unit
from hypothesis import given
from hypothesis import strategies as st

from steadyhand import (
    IDR,
    CashMovement,
    Costs,
    Cut,
    DayReport,
    DividendClaim,
    EngineState,
    Entitlement,
    Fill,
    Halt,
    Holdings,
    Instrument,
    MovementKind,
    Note,
    Order,
    Portfolio,
    Position,
    Protection,
    Rejected,
    Side,
    UnitValue,
)

# Generated values: every type a state or a report holds, within the engine's own checks.

DAYS = st.dates(date(2000, 1, 1), date(2099, 12, 31))
INSTRUMENTS = st.builds(
    Instrument,
    st.from_regex(r"[A-Z0-9][A-Z0-9.\-]{0,5}", fullmatch=True),
    st.sampled_from(["IDX", "NYSE"]),
    st.just(IDR),
)
TEXT = st.text(min_size=1).filter(lambda text: text.strip() != "")
MONEY = st.integers(-(10**15), 10**15).map(unit.rp)
POSITIVE = st.integers(1, 10**15).map(unit.rp)
NOT_NEGATIVE = st.integers(0, 10**15).map(unit.rp)
RATES = st.decimals(min_value=0, max_value=10**9, allow_nan=False, allow_infinity=False)
ORDERS = st.builds(Order, INSTRUMENTS, st.sampled_from(Side), st.integers(1, 10**6), DAYS)
NOTES = st.builds(Note, st.from_regex(r"[a-z]+(\.[a-z_]+)+", fullmatch=True), TEXT)
HALTS = st.builds(Halt, DAYS, NOTES)


@st.composite
def fills(draw: st.DrawFn) -> Fill:
    order = draw(ORDERS)
    costs = Costs(draw(NOT_NEGATIVE), draw(NOT_NEGATIVE), draw(NOT_NEGATIVE))
    day = order.placed_on + timedelta(days=draw(st.integers(0, 10)))
    return Fill(order, day, draw(st.integers(1, order.quantity)), draw(POSITIVE), costs)


@st.composite
def cuts(draw: st.DrawFn) -> Cut:
    order = draw(st.builds(Order, INSTRUMENTS, st.sampled_from(Side), st.integers(2, 10**6), DAYS))
    return Cut(order, draw(st.integers(1, order.quantity - 1)), draw(NOTES))


@st.composite
def portfolios(draw: st.DrawFn) -> Portfolio:
    held = draw(st.lists(INSTRUMENTS, max_size=4, unique_by=lambda i: (i.market, i.symbol)))
    positions = sorted(
        (Position(i, draw(st.integers(1, 10**9)), draw(NOT_NEGATIVE)) for i in held),
        key=lambda p: (p.instrument.market, p.instrument.symbol),
    )
    moves = draw(
        st.lists(
            st.tuples(DAYS, st.sampled_from(MovementKind), MONEY, st.integers(0, 5)), max_size=8
        )
    )
    ledger = tuple(
        CashMovement(day, kind, amount, day + timedelta(days=lag))
        for day, kind, amount, lag in sorted(moves, key=lambda move: move[0])
    )
    return Portfolio(IDR, tuple(positions), ledger)


@st.composite
def entitlements(draw: st.DrawFn) -> Entitlement:
    ex_date = draw(DAYS)
    pay_date = ex_date + timedelta(days=draw(st.integers(1, 30)))
    return Entitlement(draw(INSTRUMENTS), ex_date, pay_date, draw(POSITIVE))


@st.composite
def claims(draw: st.DrawFn) -> DividendClaim:
    ex_date = draw(DAYS)
    pay_date = ex_date + timedelta(days=draw(st.integers(1, 30)))
    deadline = pay_date + timedelta(days=draw(st.integers(0, 800)))
    gross = draw(st.integers(1, 10**12))
    protections: list[Protection] = []
    covered = 0
    for part in draw(st.lists(st.integers(1, gross), max_size=3)):
        if covered + part <= gross:
            covered += part
            protections.append(Protection(unit.rp(part), draw(DAYS)))
    uncovered = draw(st.integers(0, gross - covered))
    instrument = draw(INSTRUMENTS)
    return DividendClaim(
        instrument,
        ex_date,
        pay_date,
        unit.rp(gross),
        deadline,
        unit.rp(uncovered),
        tuple(protections),
    )


HOLDINGS = st.builds(
    Holdings,
    portfolios(),
    st.lists(ORDERS, max_size=3).map(tuple),
    st.lists(entitlements(), max_size=3).map(tuple),
    st.dictionaries(INSTRUMENTS, TEXT, max_size=3),
    st.dictionaries(INSTRUMENTS, POSITIVE, max_size=3),
    st.lists(claims(), max_size=3).map(tuple),
    st.none() | DAYS,
)
STATES = st.builds(
    EngineState,
    HOLDINGS,
    st.builds(UnitValue, RATES, RATES, RATES),
    st.none() | HALTS,
    st.none() | DAYS,
    st.dictionaries(st.text(), st.text(), max_size=3),
)


def tuples[T](values: st.SearchStrategy[T]) -> st.SearchStrategy[tuple[T, ...]]:
    return st.lists(values, max_size=3).map(tuple)


REPORTS = st.builds(
    DayReport,
    day=DAYS,
    fills=tuples(fills()),
    rejected=tuples(st.builds(Rejected, ORDERS, NOTES)),
    cuts=tuples(cuts()),
    queued=tuples(ORDERS),
    entitled=tuples(entitlements()),
    paid=tuples(entitlements()),
    tax=MONEY,
    daily_cost=MONEY,
    deposit=MONEY,
    frozen=tuples(st.tuples(INSTRUMENTS, TEXT)),
    halt=st.none() | HALTS,
    settled=MONEY,
    unsettled=MONEY,
    holdings_value=MONEY,
    value=MONEY,
    unit_price=RATES,
    warnings=tuples(NOTES),
    notes=tuples(NOTES),
)


@given(STATES)
def test_every_state_reads_back_equal_and_writes_the_same_json_again(state: EngineState) -> None:
    unit.test_every_state_reads_back_equal_and_writes_the_same_json_again(state)


@given(REPORTS)
def test_every_report_reads_back_equal_and_writes_the_same_json_again(report: DayReport) -> None:
    unit.test_every_report_reads_back_equal_and_writes_the_same_json_again(report)


STEPS = st.tuples(
    st.sampled_from(["deposit", "buy", "sell", "dividend", "tax", "cost"]),
    st.integers(0, 3),
    st.integers(0, len(unit.STOCKS) - 1),
    st.integers(1, 2_000),
    st.integers(50, 20_000),
    st.integers(0, 3),
)


@given(st.lists(STEPS, max_size=30), STEPS)
def test_a_restored_portfolio_behaves_as_the_one_it_was_saved_from(
    steps: list[unit.Step], following: unit.Step
) -> None:
    unit.test_a_restored_portfolio_behaves_as_the_one_it_was_saved_from(steps, following)
