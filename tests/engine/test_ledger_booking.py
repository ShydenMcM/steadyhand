"""Booking a cash movement costs the same whatever the ledger's length (#84).

The ledger is a chain each snapshot extends by one link, so booking never copies it. These tests
pin the cost of a booking, that snapshots sharing a chain still keep their own ledgers, and that
``Portfolio`` compares, hashes, prints and copies exactly as the frozen dataclass it was.
"""

import copy
import tracemalloc
from dataclasses import FrozenInstanceError
from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.money import IDR, Money
from steadyhand.portfolio import CashMovement, MovementKind, Portfolio

D0 = date(2026, 1, 5)
LONG = 100_000


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def deposits(count: int) -> tuple[CashMovement, ...]:
    return tuple(CashMovement(D0, MovementKind.DEPOSIT, rp(1), D0) for _ in range(count))


def booked(count: int) -> Portfolio:
    """A portfolio whose *count* deposits were each booked, not passed to the constructor."""
    portfolio = Portfolio.empty(IDR)
    for _ in range(count):
        portfolio = portfolio.deposit(rp(1), D0)
    return portfolio


def booking_bytes(portfolio: Portfolio) -> int:
    """The peak memory one more deposit allocates on top of *portfolio*."""
    portfolio.deposit(rp(1), D0)  # warm every code path first
    tracemalloc.start()
    try:
        portfolio.deposit(rp(1), D0)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


def test_booking_onto_a_long_ledger_allocates_no_more_than_onto_a_short_one() -> None:
    short = booking_bytes(Portfolio(IDR, (), deposits(100)))
    long = booking_bytes(Portfolio(IDR, (), deposits(LONG)))
    # Copying a 100,000-entry ledger allocated about 1.7 MB; one more link, a few hundred bytes.
    assert short > 0
    assert long <= 2 * short, f"booking allocated {long} bytes on {LONG:,} entries, {short} on 100"


def test_two_bookings_on_one_snapshot_leave_three_ledgers() -> None:
    base = booked(2)
    first = base.deposit(rp(5), D0)
    second = base.charge(MovementKind.TAX, rp(1), D0)
    start = (CashMovement(D0, MovementKind.DEPOSIT, rp(1), D0),) * 2
    assert base.ledger == start
    assert first.ledger == (*start, CashMovement(D0, MovementKind.DEPOSIT, rp(5), D0))
    assert second.ledger == (*start, CashMovement(D0, MovementKind.TAX, rp(-1), D0))
    assert (base.cash_balance(), first.cash_balance(), second.cash_balance()) == (
        rp(2),
        rp(7),
        rp(1),
    )


def test_booking_onto_a_built_portfolio_keeps_the_ledger_it_was_built_from() -> None:
    start = deposits(3)
    portfolio = Portfolio(IDR, (), start).deposit(rp(5), D0)
    assert portfolio.ledger == (*start, CashMovement(D0, MovementKind.DEPOSIT, rp(5), D0))


# Each step books onto an earlier snapshot (picked by index) or reads one snapshot's ledger,
# which fills its cache part-way through the tree.
STEP = st.tuples(
    st.sampled_from(["deposit", "tax", "read"]),
    st.integers(min_value=0, max_value=50),
    st.integers(min_value=1, max_value=1_000),
)


@given(st.lists(STEP, max_size=40))
def test_every_snapshot_in_a_tree_of_bookings_keeps_its_own_ledger(
    steps: list[tuple[str, int, int]],
) -> None:
    snapshots = [Portfolio.empty(IDR)]
    expected: list[tuple[CashMovement, ...]] = [()]
    for number, (kind, pick, amount) in enumerate(steps):
        index = pick % len(snapshots)
        parent = snapshots[index]
        if kind == "read":
            assert parent.ledger == expected[index]
            continue
        # A later step is a later day, so a booking is never before its parent's last day.
        on = D0 + timedelta(days=number)
        if kind == "deposit":
            child = parent.deposit(rp(amount), on)
            movement = CashMovement(on, MovementKind.DEPOSIT, rp(amount), on)
        else:
            child = parent.charge(MovementKind.TAX, rp(amount), on)
            movement = CashMovement(on, MovementKind.TAX, rp(-amount), on)
        snapshots.append(child)
        expected.append((*expected[index], movement))
    for snapshot, ledger in zip(snapshots, expected, strict=True):
        assert snapshot.ledger == ledger
        assert snapshot.last_day == (ledger[-1].day if ledger else None)
        assert snapshot.cash_balance() == sum((m.amount for m in ledger), start=rp(0))
        assert snapshot == Portfolio(IDR, (), ledger)


def test_a_booked_portfolio_equals_and_hashes_as_one_built_from_its_ledger() -> None:
    portfolio = booked(3).charge(MovementKind.DAILY_COST, rp(1), D0 + timedelta(days=1))
    rebuilt = Portfolio(IDR, (), portfolio.ledger)
    assert portfolio == rebuilt
    assert hash(portfolio) == hash(rebuilt)
    assert portfolio != booked(3)
    assert portfolio != booked(4)
    assert portfolio != "a portfolio"


def test_repr_names_every_field_as_the_dataclass_did() -> None:
    movement = CashMovement(D0, MovementKind.DEPOSIT, rp(1), D0)
    assert repr(booked(1)) == f"Portfolio(currency={IDR!r}, positions=(), ledger=({movement!r},))"


def test_a_portfolio_cannot_be_changed_in_place() -> None:
    portfolio = booked(1)
    with pytest.raises(FrozenInstanceError, match=r"cannot assign to field 'ledger'"):
        portfolio.ledger = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError, match=r"cannot assign to field 'currency'"):
        portfolio.currency = IDR  # type: ignore[misc]


def test_a_long_ledger_survives_deepcopy() -> None:
    portfolio = Portfolio(IDR, (), deposits(LONG)).deposit(rp(1), D0)
    # The chain is LONG links deep; copied (or pickled) link by link it would exceed the
    # recursion limit, so it travels as the ledger tuple.
    restored = copy.deepcopy(portfolio)
    assert restored == portfolio
    assert restored.cash_balance() == rp(LONG + 1)
