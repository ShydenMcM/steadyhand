# Constant-Time Ledger Booking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make booking a cash movement onto a `Portfolio` cost the same whatever the ledger's length, so the ten-year backtest stops paying for a quadratic copy, without changing anything a caller of `Portfolio` can see.

**Architecture:** Each snapshot keeps its ledger as a chain of two-slot tuples, newest movement first, and shares every link with the snapshots it was built from. Booking adds one link. `Portfolio.ledger` stays a `tuple`, built by walking the chain the first time a snapshot's ledger is read and then kept on that snapshot. Equality, hashing, `repr`, copying and pickling all go through that tuple, so they behave exactly as they did when `Portfolio` was a plain frozen dataclass.

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18, pytest + hypothesis, mypy `--strict`, ruff. The engine gains no dependency.

**Spec:** issue #84, carried forward from the M3b plan `docs/superpowers/plans/2026-09-26-m3b-backtester.md` ("Carried forward to M4 and later"), on top of `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md` (the "core spec") and `docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md` (the "M3 spec"). Every code block below was generated from a tree that passed the whole gate, not typed; the plan review log says how each claim was checked.

## Global Constraints

- The engine (`steadyhand`) stays standard-library only at runtime (core §4.2, M3 §3.2).
- `float` never appears in the engine; `tests/meta/test_no_float.py` scans every engine module on disk.
- TDD (core §10): the tests come first and a red run of the **whole** suite is recorded. This story changes no public name, so its red phase is the new tests against the old `Portfolio`; a test that passes there is listed with its reason.
- No test computes a shared value from new code at module level.
- 100% branch coverage (core §10.5). No new `# pragma: no cover` and no new `noqa` in package code.
- Test file basenames are unique across `tests/`.
- English only. The phrase "robot trading" never appears (core §1.3).
- The story gets its own branch and PR into `develop`; nothing merges into `main` (core §11).

## Review Focus

1. **Two bookings onto one snapshot.** The daily run is pure: a test runs it twice from the same state (`test_run_day_is_pure_and_repeatable`), and it may discard a day it has built. Expected: the original and both results each keep exactly their own ledger. Pinned by `test_two_bookings_on_one_snapshot_leave_three_ledgers` and by the property `test_every_snapshot_in_a_tree_of_bookings_keeps_its_own_ledger`, which also reads ledgers part-way through so that a kept tuple can never leak from a parent into a child.
2. **A snapshot built from a tuple and then booked onto.** The constructor keeps the tuple it was given as the snapshot's read-back ledger, so a chain built wrongly underneath would only show after the next booking. Pinned by `test_booking_onto_a_built_portfolio_keeps_the_ledger_it_was_built_from` (M66).
3. **Copying a long ledger.** A chain 100,000 links deep, copied or pickled link by link, exceeds Python's recursion limit. Expected: it copies as the ledger tuple. Pinned by `test_a_long_ledger_survives_deepcopy` (M64).

## Scope decisions (read before starting)

1. **Design note (#84, criterion 1): `Portfolio.ledger` stays `tuple[CashMovement, ...]`.** The two candidates were keeping a `tuple`, built from the chain when it is read, and exposing a `Sequence[CashMovement]` view over the chain.
   - *A tuple* is what every caller has today: `metrics.measure`'s deposit total, sixteen lines of the existing tests, the constructor's own argument, and `==` against a literal tuple. It is hashable, compares by value, and is the value M5 will save, whatever format that takes. Its cost is that the **first** read of a snapshot's ledger walks the whole chain; every later read of that snapshot is free.
   - *A `Sequence` view* would make the first read free, but it would need its own equality (a view never equals the tuple a test writes), hashing and slicing, indexing a linked chain is linear anyway, and every consumer, M5 included, would have to accept a type that is not a tuple.
   - **Chosen: the tuple.** The engine never reads a snapshot's ledger during a run (the only reader in package code is `measure`, once, on the final snapshot), so the walk is paid once per backtest. A future caller that wants the ledger after every day should get a method that yields only the new movements rather than reading `.ledger` each day, which would be quadratic again.
2. **The chain is nested two-slot tuples** (`type _Chain = tuple[CashMovement, _Chain] | None`). A two-slot tuple is small and quick to allocate, cannot be changed once built, and is freed without recursion however deep the chain gets. Measured on CPython 3.12.8 and 3.13.1: deleting a 1,000,000-link chain is fine, while `pickle.dumps` and `copy.deepcopy` of it raise `RecursionError` (scope decision 4).
3. **`Portfolio` declares `__slots__` itself and is a frozen dataclass without `slots=True`.** With `slots=True` the dataclass decorator builds a new class, and its frozen `__setattr__` then compares against the old one: assigning to a name that is not a field, as `ledger` now is not, raised `TypeError: super(type, obj)` instead of `FrozenInstanceError`. Found by `test_a_portfolio_cannot_be_changed_in_place` on the first gate run.
4. **Copying and pickling go through `__reduce__`, as the ledger tuple.** Without it, the dataclass's state holds the chain itself (M64).
5. **The cost of a booking is measured in bytes allocated, not seconds.** `tracemalloc` reports the same peak for the same code path on every run, whereas a timing on a shared CI runner can flake. On the old `Portfolio`, one booking onto 100,000 movements allocated 1,700,232 bytes against 1,928 onto 100; on the new one, 616 bytes onto 100 and 648 onto 100,000.
6. **Equality and hashing read the ledger tuple.** Comparing two snapshots therefore costs a walk the first time, as comparing two tuples of that length always did.

## File map

| File | Task | Responsibility |
|---|---|---|
| `packages/steadyhand/src/steadyhand/portfolio.py` | 1 | The chain, the kept ledger tuple, `__init__`, `__eq__`, `__hash__`, `__repr__`, `__reduce__`, `last_day` and `_next` |
| `tests/engine/test_ledger_booking.py` | 1 | The cost of a booking, snapshots sharing a chain, and the dataclass behaviour kept |

## Stories

| Task | Story | Issue |
|---|---|---|
| 1 | Book a cash movement in constant time | #84 |

**Merging a story (every task):** push the branch and open a PR into `develop` whose body says `Refs #<story>`. Never put `close`, `fix` or `resolve` next to an issue number, not even in a negation. Write the PR head SHA to a file so it is never retyped: `gh pr view <pr> --json headRefOid --jq .headRefOid > "${TMPDIR}/head-sha"`. Find the CI run for exactly that SHA with `gh run list --branch <branch> --json databaseId,headSha,status,conclusion`, matching `headSha` against the file yourself. Poll `gh run view <id> --json status,jobs` until `status` is `completed`, then read every job by name; each must be `success`. Then ask Shyden to approve the merge with `AskUserQuestion`, naming the PR, the head SHA **as read from the file in that same turn** (`cut -c1-7 "${TMPDIR}/head-sha"`), and the CI state. Merge with `gh pr merge <pr> --squash --delete-branch --match-head-commit "$(cat "${TMPDIR}/head-sha")"`. **Deploy:** the `develop` run that follows publishes both packages to TestPyPI; find it the same way, by the merge commit's SHA, and read `publish-dev` by name. Then close the story with a comment linking the PR and the develop run, and move its card to Done, reading the card back through its `PVTI_` node (not `gh project item-list`, which lags).

**Pushing:** agent sessions push, open PRs and merge as the `steadyhand-agent` GitHub App. The board stays on the operator's login.

**Running a step's commands:** the shell is zsh. Capture a command's exit status with no pipe in between (`uv run pytest … > out.txt 2>&1; rc=$?`), then read the file: a status read through `| tail` is `tail`'s, and it always looks like success.

---

### Task 1: #84 Book a cash movement in constant time

**Acceptance criteria (story text, #84):**
1. A short design note fixes the public type of `Portfolio.ledger`, comparing a `tuple` with a `Sequence[CashMovement]` (scope decision 1).
2. Booking a movement costs amortised constant time whatever the ledger's length, shown by a test that does not flake (scope decision 5).
3. Snapshots stay immutable: two different movements booked onto one snapshot leave the original and both results each with exactly their own ledger, as a hypothesis property over any sequence of bookings and branch points.
4. `Portfolio.ledger` still returns every movement in booking order; `==`, `measure`'s deposit total and every existing test behave exactly as before.
5. The ten-year performance test is faster on CI than 20.85 s (py3.12) and 12.43 s (py3.13); both new times are recorded on #84.
6. TDD with a recorded red phase, mutations listed and each turning the whole suite red, 100% branch coverage, and every CI gate green.

**Files:**
- Modify: `packages/steadyhand/src/steadyhand/portfolio.py`
- Test: create `tests/engine/test_ledger_booking.py`

**Interfaces:**
- Consumes: M3b's `Portfolio` (`_balance`, `_open`, `_next`).
- Produces: nothing new in the public API. `Portfolio(currency, positions=(), ledger=())` and `Portfolio.ledger` keep their types.

- [ ] **Step 1: Branch.** `git switch -c perf/84-constant-time-ledger origin/develop`

- [ ] **Step 2: Write the failing tests.** No public name changes, so there are no stubs.

**`tests/engine/test_ledger_booking.py`** (new)

<!-- file: tests/engine/test_ledger_booking.py -->
```python
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
```


- [ ] **Step 3: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=746 failed=1 -->
Expected: 746 run, 1 failed: `test_booking_onto_a_long_ledger_allocates_no_more_than_onto_a_short_one`, with about 1.7 MB allocated against about 1.9 kB. The other seven new tests pass against the old `Portfolio` by design: they pin behaviour it already had (its ledgers, equality, hash, `repr`, frozenness and copying), so that the rewrite in Step 4 cannot change it.

- [ ] **Step 4: Implement.**

**`packages/steadyhand/src/steadyhand/portfolio.py`** (rewritten: 6 edits)

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
movement. A ten-year backtest books over a hundred thousand of them (M3 spec §9).
"""
```
with:
```python
movement. A ten-year backtest books over a hundred thousand of them (M3 spec §9).

The ledger is kept as a chain of links, newest first, that every later snapshot shares, so
booking adds one link instead of copying the ledger (#84). ``Portfolio.ledger`` is still a
tuple: it is built from the chain the first time a snapshot's ledger is read, then kept.
"""
```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
```
with:
```python
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python

@dataclass(frozen=True, slots=True)
class Portfolio:
    """An immutable snapshot of cash (as a ledger) and positions (sorted by market, symbol)."""

    currency: Currency
    positions: tuple[Position, ...] = ()
    ledger: tuple[CashMovement, ...] = ()
    _balance: Money = field(init=False, repr=False, compare=False)
    """The sum of every movement in the ledger."""
    _open: tuple[CashMovement, ...] = field(init=False, repr=False, compare=False)
    """Every movement that settles after the last day, in ledger order."""

    def __post_init__(self) -> None:
        require_type(self.currency, Currency, "currency")
        require_type(self.ledger, tuple, "ledger")
        self._check_positions()
        for movement in self.ledger:
            require_type(movement, CashMovement, "ledger entry")
        previous: date | None = None
        for movement in self.ledger:
            if movement.amount.currency != self.currency:
                raise CurrencyMismatchError(self.currency, movement.amount.currency)
            if previous is not None and movement.day < previous:
                raise ChronologyError(movement.day, previous)
            previous = movement.day
        balance = sum((m.amount for m in self.ledger), start=Money.zero(self.currency))
        still_open = tuple(
            m for m in self.ledger if previous is not None and m.settles_on > previous
        )
        object.__setattr__(self, "_balance", balance)
        object.__setattr__(self, "_open", still_open)

```
with:
```python

type _Chain = tuple[CashMovement, _Chain] | None
"""A ledger, newest movement first: the latest movement and the chain booked before it."""


# ``slots=True`` would rebuild the class, and the rebuilt class's frozen ``__setattr__`` then
# fails with a TypeError, not FrozenInstanceError, for a name that is not a field (``ledger``).
@dataclass(frozen=True, init=False, repr=False, eq=False)
class Portfolio:
    """An immutable snapshot of cash (as a ledger) and positions (sorted by market, symbol)."""

    __slots__ = ("_balance", "_chain", "_ledger", "_open", "currency", "positions")

    currency: Currency
    positions: tuple[Position, ...]
    _chain: _Chain
    """Every movement, newest first, sharing its links with the snapshots it was built from."""
    _ledger: tuple[CashMovement, ...] | None
    """The ledger in booking order: the tuple the snapshot was built from, or the chain walked
    the first time it is read. ``None`` until then."""
    _balance: Money
    """The sum of every movement in the ledger."""
    _open: tuple[CashMovement, ...]
    """Every movement that settles after the last day, in ledger order."""

    def __init__(
        self,
        currency: Currency,
        positions: tuple[Position, ...] = (),
        ledger: tuple[CashMovement, ...] = (),
    ) -> None:
        require_type(currency, Currency, "currency")
        require_type(ledger, tuple, "ledger")
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "positions", positions)
        self._check_positions()
        for movement in ledger:
            require_type(movement, CashMovement, "ledger entry")
        previous: date | None = None
        chain: _Chain = None
        for movement in ledger:
            if movement.amount.currency != currency:
                raise CurrencyMismatchError(currency, movement.amount.currency)
            if previous is not None and movement.day < previous:
                raise ChronologyError(movement.day, previous)
            previous = movement.day
            chain = (movement, chain)
        balance = sum((m.amount for m in ledger), start=Money.zero(currency))
        still_open = tuple(m for m in ledger if previous is not None and m.settles_on > previous)
        for name, value in (
            ("_chain", chain),
            ("_ledger", ledger),
            ("_balance", balance),
            ("_open", still_open),
        ):
            object.__setattr__(self, name, value)

    @property
    def ledger(self) -> tuple[CashMovement, ...]:
        """Every movement in booking order.

        The first read walks the chain, so it costs the ledger's length; later reads are free.
        """
        ledger = self._ledger
        if ledger is None:
            newest_first: list[CashMovement] = []
            link = self._chain
            while link is not None:
                movement, link = link
                newest_first.append(movement)
            ledger = tuple(reversed(newest_first))
            object.__setattr__(self, "_ledger", ledger)
        return ledger

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Portfolio):
            return NotImplemented
        return (self.currency, self.positions, self.ledger) == (
            other.currency,
            other.positions,
            other.ledger,
        )

    def __hash__(self) -> int:
        return hash((self.currency, self.positions, self.ledger))

    def __repr__(self) -> str:
        return (
            f"Portfolio(currency={self.currency!r}, positions={self.positions!r}, "
            f"ledger={self.ledger!r})"
        )

    def __reduce__(self) -> tuple[type[Portfolio], tuple[object, ...]]:
        """Pickle and copy the ledger as a tuple: link by link, a long chain is too deep."""
        return (Portfolio, (self.currency, self.positions, self.ledger))

```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
    def last_day(self) -> date | None:
        return self.ledger[-1].day if self.ledger else None

```
with:
```python
    def last_day(self) -> date | None:
        return None if self._chain is None else self._chain[0].day

```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
        """
        ledger, balance, still_open = self.ledger, self._balance, self._open
        if movement is not None:
            ledger = (*ledger, movement)
            balance += movement.amount
```
with:
```python
        """
        chain, ledger, balance, still_open = self._chain, self._ledger, self._balance, self._open
        if movement is not None:
            chain, ledger = (movement, chain), None
            balance += movement.amount
```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
            ("positions", positions),
            ("ledger", ledger),
            ("_balance", balance),
```
with:
```python
            ("positions", positions),
            ("_chain", chain),
            ("_ledger", ledger),
            ("_balance", balance),
```


- [ ] **Step 5: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=746 passed=746 -->
Expected: every command exits 0; 746 passed, 10 deselected, 100% branch coverage; the performance test passes. On the machine that wrote this plan, run alternately with the old code, the ten-year test took 9.8 s and 9.1 s against 13.4 s and 14.4 s.

- [ ] **Step 6: Mutations.** Run M60–M66; each must turn the whole suite red with the total unchanged.
- [ ] **Step 7: Commit, push and merge** (`perf(engine): book a cash movement in constant time (#84)`). After CI's run, record both `test` jobs' performance-step times on #84 against 20.85 s and 12.43 s (criterion 5).

---

## Mutation checks

Each mutation plants one realistic defect in the story's finished tree, runs the **whole** suite under `HYPOTHESIS_PROFILE=ci`, and must turn it red. Plant it exactly as the block after the table says: the anchor must match exactly once, and the changed lines are printed before the run. The predictions were written before the first run; "more than predicted" lists the tests that also failed.

| ID | Task | File | Defect planted | Total | Caught by | More than predicted |
|---|---|---|---|---|---|---|
| M60 | 1 | `portfolio.py` | booking copies the whole ledger again | 746 | `test_booking_onto_a_long_ledger_allocates_no_more_than_onto_a_short_one` (1 failing) | none |
| M61 | 1 | `portfolio.py` | a new snapshot keeps its parent's ledger tuple | 746 | `test_a_booked_portfolio_equals_and_hashes_as_one_built_from_its_ledger`, `test_booking_onto_a_built_portfolio_keeps_the_ledger_it_was_built_from`, `test_every_snapshot_in_a_tree_of_bookings_keeps_its_own_ledger`, `test_repr_names_every_field_as_the_dataclass_did`, `test_two_bookings_on_one_snapshot_leave_three_ledgers` (22 failing) | 16 more tests, including `test_a_charge_is_debited_on_its_day`, `test_a_dividend_is_settled_cash_on_the_day_it_is_paid`, `test_a_long_ledger_survives_deepcopy` |
| M62 | 1 | `portfolio.py` | the chain is read newest first | 746 | `test_a_booked_portfolio_equals_and_hashes_as_one_built_from_its_ledger`, `test_booking_onto_a_built_portfolio_keeps_the_ledger_it_was_built_from`, `test_every_snapshot_in_a_tree_of_bookings_keeps_its_own_ledger`, `test_two_bookings_on_one_snapshot_leave_three_ledgers` (12 failing) | 7 more tests, including `test_a_charge_is_debited_on_its_day`, `test_a_dividend_is_settled_cash_on_the_day_it_is_paid`, `test_a_sales_only_day_nets_its_stamp_duty_with_the_sales` |
| M63 | 1 | `portfolio.py` | the last day is read from the oldest movement | 746 | `test_every_snapshot_in_a_tree_of_bookings_keeps_its_own_ledger` (3 failing) | `test_a_back_dated_fill_is_refused_and_changes_nothing`, `test_the_kept_totals_agree_with_the_whole_ledger_on_every_day` |
| M64 | 1 | `portfolio.py` | a copy walks the chain link by link | 746 | `test_a_long_ledger_survives_deepcopy` (1 failing) | none |
| M65 | 1 | `portfolio.py` | equality ignores the ledger | 746 | `test_a_booked_portfolio_equals_and_hashes_as_one_built_from_its_ledger` (1 failing) | none |
| M66 | 1 | `portfolio.py` | a built portfolio's chain keeps only its last movement | 746 | `test_booking_onto_a_built_portfolio_keeps_the_ledger_it_was_built_from` (2 failing) | `test_a_long_ledger_survives_deepcopy` |

Planted exactly (id, task, path, anchor, replacement), as run:

```python
[('M60',
  1,
  'packages/steadyhand/src/steadyhand/portfolio.py',
  '            chain, ledger = (movement, chain), None\n',
  '            chain, ledger = (movement, chain), (*self.ledger, movement)\n'),
 ('M61',
  1,
  'packages/steadyhand/src/steadyhand/portfolio.py',
  '            chain, ledger = (movement, chain), None\n',
  '            chain = (movement, chain)\n'),
 ('M62',
  1,
  'packages/steadyhand/src/steadyhand/portfolio.py',
  '            ledger = tuple(reversed(newest_first))\n',
  '            ledger = tuple(newest_first)\n'),
 ('M63',
  1,
  'packages/steadyhand/src/steadyhand/portfolio.py',
  'None if self._chain is None else self._chain[0].day',
  'None if self._chain is None else self.ledger[0].day'),
 ('M64',
  1,
  'packages/steadyhand/src/steadyhand/portfolio.py',
  '    def __reduce__(self)',
  '    def _unused_reduce(self)'),
 ('M65',
  1,
  'packages/steadyhand/src/steadyhand/portfolio.py',
  '        return (self.currency, self.positions, self.ledger) == (\n'
  '            other.currency,\n'
  '            other.positions,\n'
  '            other.ledger,\n'
  '        )\n',
  '        return (self.currency, self.positions) == (other.currency, other.positions)\n'),
 ('M66',
  1,
  'packages/steadyhand/src/steadyhand/portfolio.py',
  '            chain = (movement, chain)\n',
  '            chain = (movement, None)\n')]
```

No mutation is listed for keeping the ledger tuple once it is built: dropping that write leaves every answer the same and only makes a second read walk the chain again, so no behavioural test can see it. For the same reason none is listed for a hash that ignores the ledger: equal portfolios would still hash equal, and unequal ones would only collide more often.

## Carried forward

- **M5 saves the ledger as the tuple `Portfolio.ledger` returns** (scope decision 1). If M5 wants to write each day's new movements as they happen, it gets a method that yields only those, not a read of `.ledger` every day.
- **M4** (core spec §13, the income goal tracker and projection) starts with its spec.

## Plan review log

(Passes are recorded below. The loop ends on a pass with zero findings, and then the plan is approved.)

- **Pass 1 (2026-09-26):** mechanical, then a full read. Every code block was rendered by `render.py` from a story commit that passed CI's gate (`ruff check`, `ruff format --check`, `mypy`, `HYPOTHESIS_PROFILE=ci pytest -W error --cov`, the `perf` step), and `check_plan.py` replayed the plan from its own text: red 746 run / 1 failed, gate 746 passed, tree byte-identical to the story commit. The seven mutations ran on that commit with predictions written first, each caught with the total unchanged. Six findings, all fixed: the test's comment put the old booking at about 800 kB where it measured 1.7 MB; scope decision 5 claimed "a few hundred bytes" for the new booking without a measurement (now 616 and 648, measured twice); the mutation note called a ledger-blind hash "slower" when it would be faster; the mutation ids skipped M66; the `repr` test kept redundant parentheses; scope decision 2 overclaimed a tuple as "the cheapest object Python can allocate".
- **Pass 2 (2026-09-26):** mechanical again on the amended commit, then a read of the whole document and of the final `Portfolio`. Three findings, all fixed: `_ledger`'s docstring said it is filled "once something has read it", but the constructor fills it at once; Review Focus 1 said "the daily run" twice in one sentence; scope decision 2's claims about deep chains rested on reasoning, and are now measured on CPython 3.12.8 and 3.13.1 (deleting a 1,000,000-link chain is fine; pickling or deep-copying it raises `RecursionError`).
- **Pass 3 (2026-09-26):** mechanical again on `e1e2ce2` (gate 746 passed at 100% with the `perf` step; M60–M66 each caught with the total unchanged; replay red 746 / 1, gate 746, tree byte-identical), then a read of every prose line and every count against its source: eight new tests, so seven pass in the red phase; M62's twelve failures are eleven names once parametrised cases collapse, four predicted and seven more. No findings, so the plan is approved.
