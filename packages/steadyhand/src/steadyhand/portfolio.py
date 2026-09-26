"""A cash-only portfolio: a ledger of cash movements plus the positions they bought.

A ``Portfolio`` is an immutable snapshot, and every operation returns a new one. That makes a
failed step harmless (the old snapshot is still there) and lets the daily run commit or discard
a whole day at once.

Each ``CashMovement`` carries the date it settles, so T+2 is a date comparison, not a separate
balance to keep in step. Buys are debited on the trade date, which is conservative: the broker
takes the money at settlement, but the cash is never available to spend twice. A debit that
settles later, such as a day's stamp duty netted with its trades, is held back the same way:
``spendable_cash`` subtracts every debit at once and adds a credit only once it has settled.

Each snapshot also keeps its cash balance and the few movements that settle after its last day,
so the day's cash is read without summing the ledger, and booking a movement checks only that
movement. A ten-year backtest books over a hundred thousand of them (M3 spec §9).

The ledger is kept as a chain of links, newest first, that every later snapshot shares, so
booking adds one link instead of copying the ledger (#84). ``Portfolio.ledger`` is still a
tuple: it is built from the chain the first time a snapshot's ledger is read, then kept.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum

from steadyhand._validate import require_date, require_type
from steadyhand.money import Currency, CurrencyMismatchError, Money
from steadyhand.types import Fill, Instrument, Position, Side, Split


class MovementKind(Enum):
    DEPOSIT = "deposit"
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    TAX = "tax"
    DAILY_COST = "daily cost"


_CHARGES = frozenset({MovementKind.TAX, MovementKind.DAILY_COST})
"""The movements ``Portfolio.charge`` books: money taken that buys nothing."""


@dataclass(frozen=True, slots=True)
class CashMovement:
    """One change to cash. Credits are positive and debits negative."""

    day: date
    kind: MovementKind
    amount: Money
    settles_on: date

    def __post_init__(self) -> None:
        require_date(self.day, "movement day")
        require_type(self.kind, MovementKind, "kind")
        require_type(self.amount, Money, "amount")
        require_date(self.settles_on, "settles_on")
        if self.settles_on < self.day:
            raise _settlement_before_trade(self.settles_on, self.day)


class InsufficientCashError(ValueError):
    """A buy needs more cash than the portfolio can spend."""

    def __init__(self, day: date, needed: Money, available: Money) -> None:
        super().__init__(f"{day.isoformat()}: needs {needed} but only {available} can be spent")


class InsufficientSharesError(ValueError):
    """A sell asks for more shares than are held. There is no shorting."""

    def __init__(self, day: date, instrument: Instrument, wanted: int, held: int) -> None:
        super().__init__(
            f"{day.isoformat()}: cannot sell {wanted} {instrument.symbol}, only {held} held"
        )


class NegativeProceedsError(ValueError):
    """A sell would cost more than it raises."""

    def __init__(self, fill: Fill) -> None:
        super().__init__(
            f"{fill.day.isoformat()}: selling {fill.quantity} {fill.order.instrument.symbol} "
            f"raises {fill.gross} but costs {fill.costs.total}"
        )


class ChronologyError(ValueError):
    """An operation is dated before the last one already recorded."""

    def __init__(self, day: date, last: date) -> None:
        super().__init__(
            f"{day.isoformat()} is before the last recorded movement, on {last.isoformat()}"
        )


class MissingPriceError(LookupError):
    """A held instrument has no price to value it at."""


def _settlement_before_trade(settles_on: date, day: date) -> ValueError:
    return ValueError(f"settles on {settles_on.isoformat()}, before the trade on {day.isoformat()}")


def _sort_key(position: Position) -> tuple[str, str]:
    return (position.instrument.market, position.instrument.symbol)


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

    def _check_positions(self) -> None:
        require_type(self.positions, tuple, "positions")
        for position in self.positions:
            require_type(position, Position, "position")
        keys = [_sort_key(p) for p in self.positions]
        if keys != sorted(set(keys)):
            msg = "positions must be unique and sorted by market, then symbol"
            raise ValueError(msg)
        for position in self.positions:
            if position.instrument.currency != self.currency:
                raise CurrencyMismatchError(self.currency, position.instrument.currency)

    @classmethod
    def empty(cls, currency: Currency) -> Portfolio:
        return cls(currency)

    @property
    def last_day(self) -> date | None:
        return None if self._chain is None else self._chain[0].day

    def cash_balance(self) -> Money:
        return self._balance

    def settled_cash(self, on: date) -> Money:
        require_date(on, "on")
        return self._balance - self._settling_after(on, credits_only=False)

    def spendable_cash(self, on: date) -> Money:
        """What can be spent on *on* without ever overdrawing: settled credits, less every debit."""
        require_date(on, "on")
        return self._balance - self._settling_after(on, credits_only=True)

    def _settling_after(self, on: date, *, credits_only: bool) -> Money:
        """The movements (or only the credits) that settle after *on*.

        From *on* the last day onwards those are all among ``_open``; an earlier day needs the
        whole ledger.
        """
        last = self.last_day
        pool = self._open if last is None or on >= last else self.ledger
        later = (
            m.amount
            for m in pool
            if m.settles_on > on and not (credits_only and m.amount.amount < 0)
        )
        return sum(later, start=Money.zero(self.currency))

    def unsettled_cash(self, on: date) -> Money:
        return self.cash_balance() - self.settled_cash(on)

    def position(self, instrument: Instrument) -> Position | None:
        for position in self.positions:
            if position.instrument == instrument:
                return position
        return None

    def holdings_value(self, closes: Mapping[Instrument, Money]) -> Money:
        total = Money.zero(self.currency)
        for position in self.positions:
            close = closes.get(position.instrument)
            if close is None:
                msg = f"no close price for {position.instrument.symbol}"
                raise MissingPriceError(msg)
            total += close * position.quantity
        return total

    def deposit(self, amount: Money, on: date) -> Portfolio:
        self._require_not_before_last(on)
        if amount.currency != self.currency:
            raise CurrencyMismatchError(self.currency, amount.currency)
        if amount.amount <= 0:
            msg = f"a deposit must be positive, got {amount}"
            raise ValueError(msg)
        movement = CashMovement(on, MovementKind.DEPOSIT, amount, on)
        return self._next(self.positions, movement)

    def credit_dividend(self, gross: Money, on: date) -> Portfolio:
        """Book a dividend paid on *on*. It settles that day, so the next decision can spend it."""
        return self._book(MovementKind.DIVIDEND, gross, on)

    def charge(
        self, kind: MovementKind, amount: Money, on: date, *, settles_on: date | None = None
    ) -> Portfolio:
        """Take *amount* for tax or a daily cost on *on*, settling on *settles_on* (default *on*).

        Either way it is held back from ``spendable_cash`` at once.
        """
        require_type(kind, MovementKind, "kind")
        if kind not in _CHARGES:
            msg = f"charge books tax or a daily cost, not a {kind.value}"
            raise ValueError(msg)
        return self._book(kind, amount, on, sign=-1, settles_on=settles_on)

    def apply_split(self, split: Split) -> Portfolio:
        """Turn every ``old_shares`` held into ``new_shares``, keeping the total cost basis.

        A fraction of a share left by the ratio is dropped (cash in lieu is not modelled), and a
        holding that rounds to no shares at all is removed with its basis. The caller reports it.
        """
        require_type(split, Split, "split")
        self._require_not_before_last(split.ex_date)
        held = self.position(split.instrument)
        if held is None:
            msg = f"{split.ex_date.isoformat()}: no {split.instrument.symbol} is held to split"
            raise ValueError(msg)
        quantity = held.quantity * split.new_shares // split.old_shares
        updated = Position(held.instrument, quantity, held.cost_basis) if quantity else None
        return self._replaced(held.instrument, updated, None)

    def apply_fill(self, fill: Fill, settles_on: date) -> Portfolio:
        """Book a fill. A buy is debited on its trade date; a sell is credited on *settles_on*."""
        self._require_not_before_last(fill.day)
        require_date(settles_on, "settles_on")
        if settles_on < fill.day:
            raise _settlement_before_trade(settles_on, fill.day)
        if fill.price.currency != self.currency:
            raise CurrencyMismatchError(self.currency, fill.price.currency)
        if fill.order.side is Side.BUY:
            return self._buy(fill)
        return self._sell(fill, settles_on)

    def _book(
        self,
        kind: MovementKind,
        amount: Money,
        on: date,
        *,
        sign: int = 1,
        settles_on: date | None = None,
    ) -> Portfolio:
        self._require_not_before_last(on)
        require_type(amount, Money, "amount")
        if amount.currency != self.currency:
            raise CurrencyMismatchError(self.currency, amount.currency)
        if amount.amount <= 0:
            msg = f"a {kind.value} must be positive, got {amount}"
            raise ValueError(msg)
        movement = CashMovement(on, kind, amount * sign, on if settles_on is None else settles_on)
        return self._next(self.positions, movement)

    def _require_not_before_last(self, day: date) -> None:
        require_date(day, "day")
        last = self.last_day
        if last is not None and day < last:
            raise ChronologyError(day, last)

    def _buy(self, fill: Fill) -> Portfolio:
        instrument = fill.order.instrument
        cost = fill.gross + fill.costs.total
        available = self.spendable_cash(fill.day)
        if cost > available:
            raise InsufficientCashError(fill.day, cost, available)
        held = self.position(instrument)
        if held is None:
            updated = Position(instrument, fill.quantity, cost)
        else:
            updated = Position(instrument, held.quantity + fill.quantity, held.cost_basis + cost)
        movement = CashMovement(fill.day, MovementKind.BUY, -cost, fill.day)
        return self._with(movement, instrument, updated)

    def _sell(self, fill: Fill, settles_on: date) -> Portfolio:
        instrument = fill.order.instrument
        held = self.position(instrument)
        if held is None or fill.quantity > held.quantity:
            held_quantity = 0 if held is None else held.quantity
            raise InsufficientSharesError(fill.day, instrument, fill.quantity, held_quantity)
        proceeds = fill.gross - fill.costs.total
        if proceeds.amount < 0:
            raise NegativeProceedsError(fill)
        remaining: Position | None = None
        if fill.quantity < held.quantity:
            # The basis released by a partial sale rounds up, so the gain reported on the
            # shares sold is never overstated.
            released = -(-held.cost_basis.amount * fill.quantity // held.quantity)
            remaining = Position(
                instrument,
                held.quantity - fill.quantity,
                Money(held.cost_basis.amount - released, self.currency),
            )
        movement = CashMovement(fill.day, MovementKind.SELL, proceeds, settles_on)
        return self._with(movement, instrument, remaining)

    def _with(
        self, movement: CashMovement, instrument: Instrument, position: Position | None
    ) -> Portfolio:
        return self._replaced(instrument, position, movement)

    def _replaced(
        self, instrument: Instrument, position: Position | None, movement: CashMovement | None
    ) -> Portfolio:
        others = [p for p in self.positions if p.instrument != instrument]
        if position is not None:
            others.append(position)
        return self._next(tuple(sorted(others, key=_sort_key)), movement)

    def _next(self, positions: tuple[Position, ...], movement: CashMovement | None) -> Portfolio:
        """This snapshot with *positions* held and *movement* booked after the rest.

        Only what is new is checked. Every caller has already refused a movement dated before
        the last or in another currency, so the ledger holds without reading it again.
        """
        chain, ledger, balance, still_open = self._chain, self._ledger, self._balance, self._open
        if movement is not None:
            chain, ledger = (movement, chain), None
            balance += movement.amount
            still_open = tuple(m for m in (*still_open, movement) if m.settles_on > movement.day)
        snapshot = object.__new__(Portfolio)
        for name, value in (
            ("currency", self.currency),
            ("positions", positions),
            ("_chain", chain),
            ("_ledger", ledger),
            ("_balance", balance),
            ("_open", still_open),
        ):
            object.__setattr__(snapshot, name, value)
        snapshot._check_positions()
        return snapshot
