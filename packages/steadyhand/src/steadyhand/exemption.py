"""The dividend reinvestment exemption as claims the engine keeps (M4 spec §6).

With ``EngineSettings.dividend_reinvestment_exemption`` on, a dividend that can be exempt books no
tax when it is paid. It opens a ``DividendClaim`` instead, which the engine carries in
``Holdings.claims`` until its reinvestment and holding conditions are met or broken. Every figure
a claim gives is an estimate: it assumes the investor files the annual realisation reports
(docs/research/t-tax.md §7), which the engine cannot see.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date

from steadyhand._validate import require_date, require_type
from steadyhand.market import MarketRules
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import EXEMPTION_DEADLINE_MISSED, Note
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import Fill, Instrument, Side


@dataclass(frozen=True, slots=True)
class Protection:
    """Part of a claim reinvested by one purchase, which must stay invested through ``until``."""

    amount: Money
    until: date

    def __post_init__(self) -> None:
        require_type(self.amount, Money, "amount")
        require_date(self.until, "until")
        if self.amount.amount <= 0:
            msg = f"a protection must be positive, got {self.amount}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DividendClaim:
    """A paid dividend whose tax waits on its reinvestment (M4 spec §6.2).

    ``uncovered`` is the part of ``gross`` not yet reinvested. ``protections`` are the reinvested
    parts, each held through its own date. Together they never exceed ``gross``.
    """

    instrument: Instrument
    ex_date: date
    pay_date: date
    gross: Money
    deadline: date
    uncovered: Money
    protections: tuple[Protection, ...] = ()

    def __post_init__(self) -> None:
        require_type(self.instrument, Instrument, "instrument")
        require_date(self.ex_date, "ex_date")
        require_date(self.pay_date, "pay_date")
        require_date(self.deadline, "deadline")
        require_type(self.gross, Money, "gross")
        require_type(self.uncovered, Money, "uncovered")
        symbol = self.instrument.symbol
        if not self.ex_date < self.pay_date <= self.deadline:
            msg = (
                f"{symbol}: a claim needs ex-date < pay date <= deadline, got "
                f"{self.ex_date}, {self.pay_date} and {self.deadline}"
            )
            raise ValueError(msg)
        for amount in (self.gross, self.uncovered):
            if amount.currency != self.instrument.currency:
                raise CurrencyMismatchError(self.instrument.currency, amount.currency)
        covered = Money.zero(self.gross.currency)
        for protection in self.protections:
            require_type(protection, Protection, "protection")
            covered += protection.amount
        if self.gross.amount <= 0 or self.uncovered.amount < 0:
            msg = f"{symbol}: a claim's gross must be positive and its uncovered part not negative"
            raise ValueError(msg)
        if self.uncovered + covered > self.gross:
            msg = (
                f"{symbol}: uncovered {self.uncovered} and protected {covered} exceed the gross "
                f"dividend {self.gross}"
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ClaimDay:
    """The claims after a day's bookkeeping, with the tax it booked and what it has to say."""

    portfolio: Portfolio
    claims: tuple[DividendClaim, ...]
    tax: Money
    notes: tuple[Note, ...]


def settle_claims(
    portfolio: Portfolio, claims: tuple[DividendClaim, ...], day: date, rules: MarketRules
) -> ClaimDay:
    """Tax what missed its deadline at the day's close (M4 spec §6.3), booking it on *day*.

    A claim with nothing left to reinvest and nothing protected is closed.
    """
    tax = Money.zero(portfolio.currency)
    notes: list[Note] = []
    settled: list[DividendClaim] = []
    for claim in claims:
        if day <= claim.deadline or claim.uncovered.amount == 0:
            settled.append(claim)
            continue
        owed = rules.dividend_tax(claim.uncovered, on=claim.pay_date)
        if owed.amount > 0:
            portfolio = portfolio.charge(MovementKind.TAX, owed, day)
            tax += owed
            notes.append(_deadline_missed(claim, owed))
        settled.append(replace(claim, uncovered=Money.zero(claim.uncovered.currency)))
    kept = tuple(c for c in settled if c.uncovered.amount > 0 or c.protections)
    return ClaimDay(portfolio, kept, tax, tuple(notes))


def cover_claims(
    claims: tuple[DividendClaim, ...], fills: Sequence[Fill], rules: MarketRules
) -> tuple[DividendClaim, ...]:
    """Cover open claims with the day's buys (M4 spec §6.3).

    Each buy's gross, not its costs, covers the claims paid on or before its day whose deadline
    it meets, oldest pay date first. Each amount covered is protected until the market's
    ``protection_end`` of the buy's day.
    """
    current = list(claims)
    order = sorted(range(len(current)), key=lambda i: _age(current[i]))
    for fill in fills:
        if fill.order.side is not Side.BUY:
            continue
        left = fill.gross
        for index in order:
            claim = current[index]
            if left.amount == 0:
                break
            if not claim.pay_date <= fill.day <= claim.deadline or claim.uncovered.amount == 0:
                continue
            taken = min(left, claim.uncovered)
            protection = Protection(taken, rules.protection_end(fill.day))
            current[index] = replace(
                claim,
                uncovered=claim.uncovered - taken,
                protections=(*claim.protections, protection),
            )
            left -= taken
    return tuple(current)


def _age(claim: DividendClaim) -> tuple[date, date, str, str]:
    """The order claims are covered in: oldest pay date first, then a fixed tie-break."""
    return (claim.pay_date, claim.ex_date, claim.instrument.market, claim.instrument.symbol)


def _deadline_missed(claim: DividendClaim, tax: Money) -> Note:
    pay = claim.pay_date.isoformat()
    return Note(
        EXEMPTION_DEADLINE_MISSED,
        f"{claim.instrument.symbol}: {claim.uncovered} of the dividend paid on {pay} was not "
        f"reinvested by {claim.deadline.isoformat()}, so its tax of {tax}, owed from {pay}, is "
        "booked today",
    )
