"""The engine's state and day reports as JSON documents, for saving (M5 spec §6.3).

A document is a ``dict`` of strings, whole numbers, lists, ``None`` and further documents, and
``to_json`` writes it canonically: sorted keys and no whitespace, so the same values always give
the same bytes. Money is its amount in minor units and its currency's code, a ``Decimal`` its
exact string (the exponent is kept, since ``1.0`` and ``1`` print differently), a date its ISO
form, an enum its value, and an instrument its currency, market and symbol. A mapping keyed by an
instrument becomes a list of ``[instrument, value]`` pairs sorted by market, then symbol, because
a JSON object's keys can only be strings.

Every document carries ``version``. An older one is brought up to date by ``upgrade_snapshot``,
one step per version, before it is read; a newer one raises ``SnapshotVersionError``. Anything
else that cannot be read (a missing or unknown field, a wrong type, a value the engine's own
checks refuse) raises ``SnapshotError``. Decoding rebuilds the portfolio once, through its
constructor, which checks the ledger and the positions as the forward path does (#84).

Standard library only (core spec §4.2).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final

from steadyhand.corporate import Entitlement, Holdings
from steadyhand.engine import DayReport, EngineState
from steadyhand.exemption import DividendClaim, Protection
from steadyhand.money import IDR, Currency, Money
from steadyhand.notes import Note
from steadyhand.outcomes import Cut, Rejected
from steadyhand.portfolio import CashMovement, MovementKind, Portfolio
from steadyhand.risk import Halt, UnitValue
from steadyhand.types import Costs, Fill, Instrument, Order, Position, Side

SNAPSHOT_VERSION: Final = 1
"""The version this code writes, and the newest it reads."""

type SnapshotUpgrade = Callable[[dict[str, object]], dict[str, object]]
"""One step: a document of version N made into one of version N + 1."""

SNAPSHOT_UPGRADES: Final[Mapping[int, SnapshotUpgrade]] = {}
"""The step from each older version, keyed by the version it upgrades. None yet at version 1."""

SNAPSHOT_CURRENCIES: Final[Mapping[str, Currency]] = {IDR.code: IDR}
"""The currencies a snapshot can hold, by code: a saved state is always one this code reads."""

_UNREADABLE = (TypeError, ValueError)
"""What the readers below, and the engine's own constructors, raise for a bad document."""


class SnapshotError(ValueError):
    """A document this code cannot write or read."""


class SnapshotVersionError(SnapshotError):
    """A document written by a newer steadyhand. M5 exits with code 2."""

    def __init__(self, version: int, newest: int) -> None:
        super().__init__(
            f"this state was written by a newer steadyhand: its version is {version}, and this "
            f"one reads versions up to {newest}"
        )


def encode_state(state: EngineState) -> dict[str, object]:
    """*state* as a document of the current version."""
    holdings = state.holdings
    return {
        "version": SNAPSHOT_VERSION,
        "holdings": {
            "portfolio": _portfolio(holdings.portfolio),
            "pending": [_order(order) for order in holdings.pending],
            "entitlements": [_entitlement(e) for e in holdings.entitlements],
            "frozen": _pairs(holdings.frozen, str),
            "last_closes": _pairs(holdings.last_closes, _money),
            "claims": [_claim(claim) for claim in holdings.claims],
            "shortfall_since": _day_or_none(holdings.shortfall_since),
        },
        "units": {
            "units": str(state.units.units),
            "price": str(state.units.price),
            "high_water": str(state.units.high_water),
        },
        "halt": _halt(state.halt),
        "last_day": _day_or_none(state.last_day),
        "memory": dict(state.memory),
    }


def decode_state(document: object) -> EngineState:
    """The state *document* holds, upgraded first if it is older."""
    current = upgrade_snapshot(document)
    try:
        return _read_state(current)
    except _UNREADABLE as error:
        msg = f"the saved state cannot be read: {error}"
        raise SnapshotError(msg) from error


def encode_report(report: DayReport) -> dict[str, object]:
    """*report* as a document of the current version."""
    return {
        "version": SNAPSHOT_VERSION,
        "day": report.day.isoformat(),
        "fills": [_fill(fill) for fill in report.fills],
        "rejected": [
            {"order": _order(r.order), "reason": _note(r.reason)} for r in report.rejected
        ],
        "cuts": [
            {"order": _order(c.order), "quantity": c.quantity, "reason": _note(c.reason)}
            for c in report.cuts
        ],
        "queued": [_order(order) for order in report.queued],
        "entitled": [_entitlement(e) for e in report.entitled],
        "paid": [_entitlement(e) for e in report.paid],
        "tax": _money(report.tax),
        "daily_cost": _money(report.daily_cost),
        "deposit": _money(report.deposit),
        "frozen": [[_instrument(i), reason] for i, reason in report.frozen],
        "halt": _halt(report.halt),
        "settled": _money(report.settled),
        "unsettled": _money(report.unsettled),
        "holdings_value": _money(report.holdings_value),
        "value": _money(report.value),
        "unit_price": str(report.unit_price),
        "warnings": [_note(note) for note in report.warnings],
        "notes": [_note(note) for note in report.notes],
    }


def decode_report(document: object) -> DayReport:
    """The day report *document* holds, upgraded first if it is older."""
    current = upgrade_snapshot(document)
    try:
        return _read_report(current)
    except _UNREADABLE as error:
        msg = f"the saved day report cannot be read: {error}"
        raise SnapshotError(msg) from error


def upgrade_snapshot(
    document: object,
    steps: Mapping[int, SnapshotUpgrade] = SNAPSHOT_UPGRADES,
    newest: int = SNAPSHOT_VERSION,
) -> dict[str, object]:
    """*document* brought up to version *newest*, one step at a time, oldest first."""
    version = document.get("version") if isinstance(document, dict) else None
    if not isinstance(document, dict) or type(version) is not int or version < 1:
        msg = f"a snapshot needs a whole-number version from 1, got {version!r}"
        raise SnapshotError(msg)
    if version > newest:
        raise SnapshotVersionError(version, newest)
    upgraded: dict[str, object] = dict(document)
    while version < newest:
        upgraded = {**steps[version](upgraded), "version": version + 1}
        version += 1
    return upgraded


def to_json(document: Mapping[str, object]) -> str:
    """*document* as canonical JSON: sorted keys, no whitespace, ASCII only."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)


def from_json(text: str) -> object:
    """The document *text* holds."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        msg = f"a snapshot is not valid JSON: {error}"
        raise SnapshotError(msg) from error


def _code(currency: Currency) -> str:
    if SNAPSHOT_CURRENCIES.get(currency.code) != currency:
        msg = f"a snapshot cannot hold {currency.code} with {currency.minor_units} minor units"
        raise SnapshotError(msg)
    return currency.code


def _money(value: Money) -> dict[str, object]:
    return {"amount": value.amount, "currency": _code(value.currency)}


def _instrument(instrument: Instrument) -> dict[str, object]:
    return {
        "currency": _code(instrument.currency),
        "market": instrument.market,
        "symbol": instrument.symbol,
    }


def _order(order: Order) -> dict[str, object]:
    return {
        "instrument": _instrument(order.instrument),
        "side": order.side.value,
        "quantity": order.quantity,
        "placed_on": order.placed_on.isoformat(),
    }


def _fill(fill: Fill) -> dict[str, object]:
    return {
        "order": _order(fill.order),
        "day": fill.day.isoformat(),
        "quantity": fill.quantity,
        "price": _money(fill.price),
        "costs": {
            "fee": _money(fill.costs.fee),
            "levy": _money(fill.costs.levy),
            "tax": _money(fill.costs.tax),
        },
    }


def _portfolio(portfolio: Portfolio) -> dict[str, object]:
    return {
        "currency": _code(portfolio.currency),
        "positions": [
            {
                "instrument": _instrument(p.instrument),
                "quantity": p.quantity,
                "cost_basis": _money(p.cost_basis),
            }
            for p in portfolio.positions
        ],
        "ledger": [
            {
                "day": m.day.isoformat(),
                "kind": m.kind.value,
                "amount": _money(m.amount),
                "settles_on": m.settles_on.isoformat(),
            }
            for m in portfolio.ledger
        ],
    }


def _entitlement(entitlement: Entitlement) -> dict[str, object]:
    return {
        "instrument": _instrument(entitlement.instrument),
        "ex_date": entitlement.ex_date.isoformat(),
        "pay_date": entitlement.pay_date.isoformat(),
        "gross": _money(entitlement.gross),
    }


def _claim(claim: DividendClaim) -> dict[str, object]:
    return {
        "instrument": _instrument(claim.instrument),
        "ex_date": claim.ex_date.isoformat(),
        "pay_date": claim.pay_date.isoformat(),
        "gross": _money(claim.gross),
        "deadline": claim.deadline.isoformat(),
        "uncovered": _money(claim.uncovered),
        "protections": [
            {"amount": _money(p.amount), "until": p.until.isoformat()} for p in claim.protections
        ],
    }


def _pairs[V](mapping: Mapping[Instrument, V], encode: Callable[[V], object]) -> list[object]:
    ordered = sorted(mapping.items(), key=lambda item: (item[0].market, item[0].symbol))
    return [[_instrument(instrument), encode(value)] for instrument, value in ordered]


def _halt(halt: Halt | None) -> dict[str, object] | None:
    return None if halt is None else {"day": halt.day.isoformat(), "cause": _note(halt.cause)}


def _note(note: Note) -> dict[str, object]:
    return {"key": note.key, "text": note.text}


def _day_or_none(day: date | None) -> str | None:
    return None if day is None else day.isoformat()


def _fields(document: object, *names: str) -> tuple[object, ...]:
    """The values of *names* in *document*, which must hold exactly those fields."""
    if not isinstance(document, dict):
        msg = f"expected an object with {', '.join(names)}, got {type(document).__name__}"
        raise TypeError(msg)
    if set(document) != set(names):
        msg = f"expected the fields {sorted(names)}, got {sorted(document)}"
        raise ValueError(msg)
    return tuple(document[name] for name in names)


def _int(value: object) -> int:
    if type(value) is not int:
        msg = f"expected a whole number, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _str(value: object) -> str:
    if not isinstance(value, str):
        msg = f"expected a string, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        msg = f"expected a list, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _date(value: object) -> date:
    return date.fromisoformat(_str(value))


def _optional_date(value: object) -> date | None:
    return None if value is None else _date(value)


def _decimal(value: object) -> Decimal:
    text = _str(value)
    try:
        number = Decimal(text)
    except InvalidOperation:
        number = Decimal("NaN")
    if not number.is_finite():
        msg = f"expected a finite number, got {text!r}"
        raise ValueError(msg)
    return number


def _read_currency(value: object) -> Currency:
    code = _str(value)
    if code not in SNAPSHOT_CURRENCIES:
        msg = f"unknown currency {code!r}"
        raise ValueError(msg)
    return SNAPSHOT_CURRENCIES[code]


def _read_money(value: object) -> Money:
    amount, currency = _fields(value, "amount", "currency")
    return Money(_int(amount), _read_currency(currency))


def _read_instrument(value: object) -> Instrument:
    currency, market, symbol = _fields(value, "currency", "market", "symbol")
    return Instrument(_str(symbol), _str(market), _read_currency(currency))


def _read_order(value: object) -> Order:
    instrument, side, quantity, placed_on = _fields(
        value, "instrument", "side", "quantity", "placed_on"
    )
    return Order(_read_instrument(instrument), Side(side), _int(quantity), _date(placed_on))


def _read_fill(value: object) -> Fill:
    order, day, quantity, price, costs = _fields(
        value, "order", "day", "quantity", "price", "costs"
    )
    fee, levy, tax = _fields(costs, "fee", "levy", "tax")
    return Fill(
        _read_order(order),
        _date(day),
        _int(quantity),
        _read_money(price),
        Costs(_read_money(fee), _read_money(levy), _read_money(tax)),
    )


def _read_position(value: object) -> Position:
    instrument, quantity, cost_basis = _fields(value, "instrument", "quantity", "cost_basis")
    return Position(_read_instrument(instrument), _int(quantity), _read_money(cost_basis))


def _read_movement(value: object) -> CashMovement:
    day, kind, amount, settles_on = _fields(value, "day", "kind", "amount", "settles_on")
    return CashMovement(_date(day), MovementKind(kind), _read_money(amount), _date(settles_on))


def _read_portfolio(value: object) -> Portfolio:
    currency, positions, ledger = _fields(value, "currency", "positions", "ledger")
    return Portfolio(
        _read_currency(currency),
        tuple(_read_position(p) for p in _list(positions)),
        tuple(_read_movement(m) for m in _list(ledger)),
    )


def _read_entitlement(value: object) -> Entitlement:
    instrument, ex_date, pay_date, gross = _fields(
        value, "instrument", "ex_date", "pay_date", "gross"
    )
    return Entitlement(
        _read_instrument(instrument), _date(ex_date), _date(pay_date), _read_money(gross)
    )


def _read_claim(value: object) -> DividendClaim:
    instrument, ex_date, pay_date, gross, deadline, uncovered, protections = _fields(
        value, "instrument", "ex_date", "pay_date", "gross", "deadline", "uncovered", "protections"
    )
    return DividendClaim(
        _read_instrument(instrument),
        _date(ex_date),
        _date(pay_date),
        _read_money(gross),
        _date(deadline),
        _read_money(uncovered),
        tuple(_read_protection(p) for p in _list(protections)),
    )


def _read_protection(value: object) -> Protection:
    amount, until = _fields(value, "amount", "until")
    return Protection(_read_money(amount), _date(until))


def _read_pairs[V](value: object, read: Callable[[object], V]) -> dict[Instrument, V]:
    pairs: dict[Instrument, V] = {}
    for pair in _list(value):
        instrument, item = _list(pair)
        pairs[_read_instrument(instrument)] = read(item)
    return pairs


def _read_halt(value: object) -> Halt | None:
    if value is None:
        return None
    day, cause = _fields(value, "day", "cause")
    return Halt(_date(day), _read_note(cause))


def _read_note(value: object) -> Note:
    key, text = _fields(value, "key", "text")
    return Note(_str(key), _str(text))


def _read_memory(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        msg = f"expected the strategy memory as an object, got {type(value).__name__}"
        raise TypeError(msg)
    return {_str(key): _str(item) for key, item in value.items()}


def _read_state(document: dict[str, object]) -> EngineState:
    _version, holdings, units, halt, last_day, memory = _fields(
        document, "version", "holdings", "units", "halt", "last_day", "memory"
    )
    portfolio, pending, entitlements, frozen, last_closes, claims, shortfall_since = _fields(
        holdings,
        "portfolio",
        "pending",
        "entitlements",
        "frozen",
        "last_closes",
        "claims",
        "shortfall_since",
    )
    count, price, high_water = _fields(units, "units", "price", "high_water")
    return EngineState(
        Holdings(
            _read_portfolio(portfolio),
            tuple(_read_order(order) for order in _list(pending)),
            tuple(_read_entitlement(e) for e in _list(entitlements)),
            _read_pairs(frozen, _str),
            _read_pairs(last_closes, _read_money),
            tuple(_read_claim(claim) for claim in _list(claims)),
            _optional_date(shortfall_since),
        ),
        UnitValue(_decimal(count), _decimal(price), _decimal(high_water)),
        _read_halt(halt),
        _optional_date(last_day),
        _read_memory(memory),
    )


def _read_report(document: dict[str, object]) -> DayReport:
    names = (
        "version",
        "day",
        "fills",
        "rejected",
        "cuts",
        "queued",
        "entitled",
        "paid",
        "tax",
        "daily_cost",
        "deposit",
        "frozen",
        "halt",
        "settled",
        "unsettled",
        "holdings_value",
        "value",
        "unit_price",
        "warnings",
        "notes",
    )
    field = dict(zip(names, _fields(document, *names), strict=True))
    return DayReport(
        day=_date(field["day"]),
        fills=tuple(_read_fill(fill) for fill in _list(field["fills"])),
        rejected=tuple(_read_rejected(r) for r in _list(field["rejected"])),
        cuts=tuple(_read_cut(cut) for cut in _list(field["cuts"])),
        queued=tuple(_read_order(order) for order in _list(field["queued"])),
        entitled=tuple(_read_entitlement(e) for e in _list(field["entitled"])),
        paid=tuple(_read_entitlement(e) for e in _list(field["paid"])),
        tax=_read_money(field["tax"]),
        daily_cost=_read_money(field["daily_cost"]),
        deposit=_read_money(field["deposit"]),
        frozen=tuple(_read_frozen(pair) for pair in _list(field["frozen"])),
        halt=_read_halt(field["halt"]),
        settled=_read_money(field["settled"]),
        unsettled=_read_money(field["unsettled"]),
        holdings_value=_read_money(field["holdings_value"]),
        value=_read_money(field["value"]),
        unit_price=_decimal(field["unit_price"]),
        warnings=tuple(_read_note(note) for note in _list(field["warnings"])),
        notes=tuple(_read_note(note) for note in _list(field["notes"])),
    )


def _read_rejected(value: object) -> Rejected:
    order, reason = _fields(value, "order", "reason")
    return Rejected(_read_order(order), _read_note(reason))


def _read_cut(value: object) -> Cut:
    order, quantity, reason = _fields(value, "order", "quantity", "reason")
    return Cut(_read_order(order), _int(quantity), _read_note(reason))


def _read_frozen(value: object) -> tuple[Instrument, str]:
    instrument, reason = _list(value)
    return _read_instrument(instrument), _str(reason)
