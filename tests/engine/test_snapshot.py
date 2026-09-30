"""Saving and reading the engine's state and day reports (M5 spec §6.3, §9.2 "Codec")."""

from collections.abc import Callable
from contextlib import suppress
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand import (
    IDR,
    RISK_HALT_DAILY_LOSS,
    SNAPSHOT_CURRENCIES,
    SNAPSHOT_UPGRADES,
    SNAPSHOT_VERSION,
    CashMovement,
    Costs,
    Currency,
    Cut,
    DayReport,
    DividendClaim,
    EngineState,
    Entitlement,
    Fill,
    Halt,
    Holdings,
    Instrument,
    Money,
    MovementKind,
    Note,
    Order,
    Portfolio,
    Position,
    Protection,
    Rejected,
    Side,
    SnapshotError,
    SnapshotVersionError,
    UnitValue,
    decode_report,
    decode_state,
    encode_report,
    encode_state,
    from_json,
    to_json,
    upgrade_snapshot,
)

D0 = date(2026, 1, 5)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


# Generated values: every type a state or a report holds, within the engine's own checks.

DAYS = st.dates(date(2000, 1, 1), date(2099, 12, 31))
INSTRUMENTS = st.builds(
    Instrument,
    st.from_regex(r"[A-Z0-9][A-Z0-9.\-]{0,5}", fullmatch=True),
    st.sampled_from(["IDX", "NYSE"]),
    st.just(IDR),
)
TEXT = st.text(min_size=1).filter(lambda text: text.strip() != "")
MONEY = st.integers(-(10**15), 10**15).map(rp)
POSITIVE = st.integers(1, 10**15).map(rp)
NOT_NEGATIVE = st.integers(0, 10**15).map(rp)
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
            protections.append(Protection(rp(part), draw(DAYS)))
    uncovered = draw(st.integers(0, gross - covered))
    instrument = draw(INSTRUMENTS)
    return DividendClaim(
        instrument, ex_date, pay_date, rp(gross), deadline, rp(uncovered), tuple(protections)
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
    text = to_json(encode_state(state))
    back = decode_state(from_json(text))
    assert back == state
    assert to_json(encode_state(back)) == text


@given(REPORTS)
def test_every_report_reads_back_equal_and_writes_the_same_json_again(report: DayReport) -> None:
    text = to_json(encode_report(report))
    back = decode_report(from_json(text))
    assert back == report
    assert to_json(encode_report(back)) == text


# The worked example: one small state, and exactly the JSON it saves as.


def small_state() -> EngineState:
    opened = EngineState.opening(rp(10_000_000), D0)
    portfolio = opened.holdings.portfolio.charge(
        MovementKind.DAILY_COST, rp(1_500), D0, settles_on=D0 + timedelta(days=2)
    )
    holdings = Holdings(
        portfolio,
        pending=(Order(BBRI, Side.BUY, 500, D0),),
        frozen={TLKM: "excluded: suspended", BBRI: "excluded: under review"},
        last_closes={BBRI: rp(4_150)},
        shortfall_since=D0,
    )
    units = UnitValue(Decimal("10000000"), Decimal("0.9998500"), Decimal("1.000"))
    halt = Halt(D0, Note(RISK_HALT_DAILY_LOSS, "daily loss limit"))
    return EngineState(holdings, units, halt, D0, {"set": "IDX:BBRI"})


SMALL_STATE_JSON = (
    '{"halt":{"cause":{"key":"risk.halt.daily_loss","text":"daily loss limit"},'
    '"day":"2026-01-05"},'
    '"holdings":{"claims":[],"entitlements":[],'
    '"frozen":[[{"currency":"IDR","market":"IDX","symbol":"BBRI"},"excluded: under review"],'
    '[{"currency":"IDR","market":"IDX","symbol":"TLKM"},"excluded: suspended"]],'
    '"last_closes":[[{"currency":"IDR","market":"IDX","symbol":"BBRI"},'
    '{"amount":4150,"currency":"IDR"}]],'
    '"pending":[{"instrument":{"currency":"IDR","market":"IDX","symbol":"BBRI"},'
    '"placed_on":"2026-01-05","quantity":500,"side":"buy"}],'
    '"portfolio":{"currency":"IDR","ledger":['
    '{"amount":{"amount":10000000,"currency":"IDR"},"day":"2026-01-05","kind":"deposit",'
    '"settles_on":"2026-01-05"},'
    '{"amount":{"amount":-1500,"currency":"IDR"},"day":"2026-01-05","kind":"daily cost",'
    '"settles_on":"2026-01-07"}],"positions":[]},'
    '"shortfall_since":"2026-01-05"},'
    '"last_day":"2026-01-05","memory":{"set":"IDX:BBRI"},'
    '"units":{"high_water":"1.000","price":"0.9998500","units":"10000000"},"version":1}'
)


def test_a_small_state_saves_as_exactly_this_json() -> None:
    assert to_json(encode_state(small_state())) == SMALL_STATE_JSON


def test_a_small_state_reads_back_equal_with_its_open_movement_still_unsettled() -> None:
    back = decode_state(from_json(SMALL_STATE_JSON))
    assert back == small_state()
    portfolio = back.holdings.portfolio
    assert portfolio.settled_cash(D0) == rp(10_000_000)
    assert portfolio.spendable_cash(D0) == rp(9_998_500)
    assert portfolio.settled_cash(D0 + timedelta(days=2)) == rp(9_998_500)


def test_a_decimal_keeps_its_exponent_so_a_restored_unit_price_prints_the_same() -> None:
    units = decode_state(from_json(SMALL_STATE_JSON)).units
    assert (str(units.price), str(units.high_water)) == ("0.9998500", "1.000")


def test_stock_keyed_maps_save_the_same_whatever_order_they_were_built_in() -> None:
    state = small_state()
    reordered = Holdings(
        state.holdings.portfolio,
        pending=state.holdings.pending,
        frozen={BBRI: "excluded: under review", TLKM: "excluded: suspended"},
        last_closes=state.holdings.last_closes,
        shortfall_since=state.holdings.shortfall_since,
    )
    same = EngineState(reordered, state.units, state.halt, state.last_day, state.memory)
    assert list(same.holdings.frozen) != list(state.holdings.frozen)
    assert to_json(encode_state(same)) == to_json(encode_state(state))


def test_a_reports_frozen_stocks_keep_the_order_the_day_froze_them_in() -> None:
    report = small_report()
    text = to_json(encode_report(report))
    assert text.index('"TLKM"') < text.index('"BBRI"')
    assert decode_report(from_json(text)).frozen == report.frozen


def small_report() -> DayReport:
    zero = rp(0)
    return DayReport(
        day=D0,
        fills=(),
        rejected=(),
        cuts=(),
        queued=(),
        entitled=(),
        paid=(),
        tax=zero,
        daily_cost=zero,
        deposit=zero,
        frozen=((TLKM, "excluded: suspended"), (BBRI, "excluded: under review")),
        halt=None,
        settled=zero,
        unsettled=zero,
        holdings_value=zero,
        value=zero,
        unit_price=Decimal(1),
        warnings=(),
    )


# A restored portfolio behaves as the one it was saved from (M5 spec §6.3).

STOCKS = (BBRI, TLKM)
type Step = tuple[str, int, int, int, int, int]  # kind, days forward, stock, shares, price, lag

STEPS = st.tuples(
    st.sampled_from(["deposit", "buy", "sell", "dividend", "tax", "cost"]),
    st.integers(0, 3),
    st.integers(0, len(STOCKS) - 1),
    st.integers(1, 2_000),
    st.integers(50, 20_000),
    st.integers(0, 3),
)


def take(portfolio: Portfolio, step: Step, today: date) -> Portfolio:
    kind, _forward, stock, shares, price, lag = step
    later = today + timedelta(days=lag)
    if kind == "deposit":
        return portfolio.deposit(rp(shares * price), today)
    if kind == "dividend":
        return portfolio.credit_dividend(rp(shares), today)
    if kind in {"tax", "cost"}:
        charge = MovementKind.TAX if kind == "tax" else MovementKind.DAILY_COST
        return portfolio.charge(charge, rp(shares), today, settles_on=later)
    side = Side.BUY if kind == "buy" else Side.SELL
    order = Order(STOCKS[stock], side, shares, today)
    fill = Fill(order, today, shares, rp(price), Costs(rp(price // 10), rp(0), rp(0)))
    return portfolio.apply_fill(fill, later)


def outcome(portfolio: Portfolio, step: Step, today: date) -> object:
    try:
        return take(portfolio, step, today)
    except ValueError as error:
        return (type(error), str(error))


@given(st.lists(STEPS, max_size=30), STEPS)
def test_a_restored_portfolio_behaves_as_the_one_it_was_saved_from(
    steps: list[Step], following: Step
) -> None:
    portfolio = Portfolio.empty(IDR)
    today = D0
    for step in steps:
        today += timedelta(days=step[1])
        with suppress(ValueError):
            portfolio = take(portfolio, step, today)
    saved = EngineState(Holdings(portfolio))
    restored = decode_state(from_json(to_json(encode_state(saved)))).holdings.portfolio
    assert restored == portfolio
    assert (restored.last_day, restored.cash_balance()) == (
        portfolio.last_day,
        portfolio.cash_balance(),
    )
    for offset in range(-4, 5):
        on = today + timedelta(days=offset)
        assert restored.settled_cash(on) == portfolio.settled_cash(on)
        assert restored.spendable_cash(on) == portfolio.spendable_cash(on)
    assert outcome(restored, following, today) == outcome(portfolio, following, today)


# Documents that cannot be read, and states that cannot be saved.

type Change = Callable[[dict[str, object]], None]


def ledger(document: dict[str, object]) -> list[dict[str, object]]:
    return document["holdings"]["portfolio"]["ledger"]  # type: ignore[index,no-any-return]


def swap_ledger(document: dict[str, object]) -> None:
    moves = ledger(document)
    moves[0], moves[1] = moves[1], moves[0]


def two_positions(document: dict[str, object]) -> None:
    position = {
        "instrument": {"currency": "IDR", "market": "IDX", "symbol": "BBRI"},
        "quantity": 100,
        "cost_basis": {"amount": 400_000, "currency": "IDR"},
    }
    document["holdings"]["portfolio"]["positions"] = [position, dict(position)]  # type: ignore[index]


def set_in(path: tuple[str | int, ...], value: object) -> Change:
    def change(document: dict[str, object]) -> None:
        target: object = document
        for step in path[:-1]:
            target = target[step]  # type: ignore[index]
        target[path[-1]] = value  # type: ignore[index]

    return change


def drop(name: str) -> Change:
    def change(document: dict[str, object]) -> None:
        del document[name]

    return change


AMOUNT = ("holdings", "portfolio", "ledger", 0, "amount", "amount")
STATE_FIELDS = r"\['halt', 'holdings', 'last_day', 'memory', 'units', 'version'\]"

UNREADABLE_STATES: list[tuple[str, Change, str]] = [
    (
        "a ledger out of date order",
        swap_ledger,
        "2026-01-05 is before the last recorded movement, on 2026-01-06",
    ),
    (
        "a movement in a currency it cannot hold",
        set_in(("holdings", "portfolio", "ledger", 0, "amount", "currency"), "USD"),
        "unknown currency 'USD'",
    ),
    (
        "a position of no shares",
        set_in(
            ("holdings", "portfolio", "positions"),
            [
                {
                    "instrument": {"currency": "IDR", "market": "IDX", "symbol": "BBRI"},
                    "quantity": 0,
                    "cost_basis": {"amount": 0, "currency": "IDR"},
                }
            ],
        ),
        "position quantity must be at least 1, got 0",
    ),
    (
        "two positions in one stock",
        two_positions,
        "positions must be unique and sorted by market, then symbol",
    ),
    (
        "a missing field",
        drop("memory"),
        (
            rf"expected the fields {STATE_FIELDS}, "
            r"got \['halt', 'holdings', 'last_day', 'units', 'version'\]"
        ),
    ),
    (
        "an unknown field",
        set_in(("extra",), 1),
        (
            rf"expected the fields {STATE_FIELDS}, "
            r"got \['extra', 'halt', 'holdings', 'last_day', 'memory', 'units', 'version'\]"
        ),
    ),
    ("an amount written as a fraction", set_in(AMOUNT, 1.5), "expected a whole number, got float"),
    ("an amount written as true", set_in(AMOUNT, value=True), "expected a whole number, got bool"),
    (
        "a unit price that is not a number",
        set_in(("units", "price"), "NaN"),
        "expected a finite number, got 'NaN'",
    ),
    (
        "a unit price in words",
        set_in(("units", "price"), "one"),
        "expected a finite number, got 'one'",
    ),
    ("a day that is not a date", set_in(("last_day",), "5 Jan 2026"), "Invalid isoformat"),
    (
        "a strategy memory holding a number",
        set_in(("memory",), {"set": 5}),
        "expected a string, got int",
    ),
    (
        "an object where a list belongs",
        set_in(("holdings", "pending"), {}),
        "expected a list, got dict",
    ),
    (
        "a strategy memory that is not an object",
        set_in(("memory",), ["set"]),
        "expected the strategy memory as an object, got list",
    ),
    (
        "a list where an object belongs",
        set_in(("units",), []),
        "expected an object with units, price, high_water, got list",
    ),
]


@pytest.mark.parametrize(
    ("change", "message"),
    [pytest.param(change, message, id=name) for name, change, message in UNREADABLE_STATES],
)
def test_a_state_that_cannot_be_read_is_refused_naming_what_is_wrong(
    change: Change, message: str
) -> None:
    opened = EngineState.opening(rp(10_000_000), D0)
    portfolio = opened.holdings.portfolio.deposit(rp(1_000), D0 + timedelta(days=1))
    document = encode_state(EngineState(Holdings(portfolio), opened.units))
    change(document)
    with pytest.raises(SnapshotError, match=rf"^the saved state cannot be read: .*{message}"):
        decode_state(document)


def test_a_report_that_cannot_be_read_is_refused_naming_what_is_wrong() -> None:
    document = encode_report(small_report())
    document["tax"] = {"amount": "0", "currency": "IDR"}
    with pytest.raises(
        SnapshotError, match=r"^the saved day report cannot be read: expected a whole number"
    ):
        decode_report(document)


@pytest.mark.parametrize(
    ("currency", "message"),
    [
        (Currency("USD", 2), "a snapshot cannot hold USD with 2 minor units"),
        (Currency("IDR", 2), "a snapshot cannot hold IDR with 2 minor units"),
    ],
)
def test_a_state_in_a_currency_a_snapshot_cannot_hold_is_refused_before_it_is_saved(
    currency: Currency, message: str
) -> None:
    state = EngineState.opening(Money(10_000, currency), D0)
    with pytest.raises(SnapshotError, match=f"^{message}$"):
        encode_state(state)


def test_the_currencies_a_snapshot_can_hold_are_the_rupiah_alone() -> None:
    assert SNAPSHOT_CURRENCIES == {"IDR": IDR}


# Versions (M5 spec §6.3).


def test_this_code_writes_version_1_and_has_no_upgrades_yet() -> None:
    assert SNAPSHOT_VERSION == 1
    assert SNAPSHOT_UPGRADES == {}
    assert encode_state(small_state())["version"] == 1
    assert encode_report(small_report())["version"] == 1


@pytest.mark.parametrize("decode", [decode_state, decode_report])
def test_a_document_from_a_newer_steadyhand_is_refused(decode: Callable[[object], object]) -> None:
    newer = {"version": 2}
    with pytest.raises(
        SnapshotVersionError,
        match=(
            r"^this state was written by a newer steadyhand: its version is 2, and this one "
            r"reads versions up to 1$"
        ),
    ):
        decode(newer)


@pytest.mark.parametrize(
    ("document", "shown"),
    [
        ({}, "None"),
        ({"version": 0}, "0"),
        ({"version": "1"}, "'1'"),
        ({"version": True}, "True"),
        ({"version": 1.0}, "1.0"),
        ([1], "None"),
    ],
)
def test_a_document_without_a_whole_number_version_is_refused(document: object, shown: str) -> None:
    with pytest.raises(
        SnapshotError, match=rf"^a snapshot needs a whole-number version from 1, got {shown}$"
    ):
        upgrade_snapshot(document)


def trail(step: str) -> Callable[[dict[str, object]], dict[str, object]]:
    def upgrade(document: dict[str, object]) -> dict[str, object]:
        done = document.get("trail", [])
        return {**document, "trail": [*done, step]}  # type: ignore[misc]

    return upgrade


def test_an_older_document_is_upgraded_one_version_at_a_time_oldest_first() -> None:
    steps = {1: trail("1 to 2"), 2: trail("2 to 3")}
    original = {"version": 1, "kept": "yes"}
    assert upgrade_snapshot(original, steps, 3) == {
        "version": 3,
        "kept": "yes",
        "trail": ["1 to 2", "2 to 3"],
    }
    assert original == {"version": 1, "kept": "yes"}
    assert upgrade_snapshot({"version": 2}, steps, 3) == {"version": 3, "trail": ["2 to 3"]}
    assert upgrade_snapshot({"version": 3}, steps, 3) == {"version": 3}


def test_canonical_json_has_sorted_keys_and_no_whitespace() -> None:
    assert to_json({"b": 1, "a": [1, "x"], "c": {"z": None, "y": "é"}}) == (
        '{"a":[1,"x"],"b":1,"c":{"y":"\\u00e9","z":null}}'
    )


def test_text_that_is_not_json_is_refused() -> None:
    with pytest.raises(SnapshotError, match=r"^a snapshot is not valid JSON: Expecting value"):
        from_json("not json")
