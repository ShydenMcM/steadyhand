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
from steadyhand.notes import EXEMPTION_CLAIM_BROKEN, EXEMPTION_DEADLINE_MISSED, Note
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
    shortfall_since: date | None
    tax: Money
    notes: tuple[Note, ...]


def settle_claims(
    portfolio: Portfolio,
    claims: tuple[DividendClaim, ...],
    shortfall_since: date | None,
    day: date,
    rules: MarketRules,
) -> ClaimDay:
    """The claims at the day's close, with any tax they book on *day*.

    What missed its deadline is taxed (M4 spec §6.3). Protections past their date fall away.
    Then the protected amount is compared with the cost basis still invested: a shortfall that
    lasts to the close of the settlement date of its first day breaks, latest protection first
    (§6.4). A claim with nothing left to reinvest and nothing protected is closed.
    """
    close = _Close(portfolio, day, rules)
    current = [close.deadline(claim) for claim in claims]
    current = [replace(c, protections=_unexpired(c.protections, day)) for c in current]
    protected = sum(
        (p.amount for c in current for p in c.protections), Money.zero(portfolio.currency)
    )
    invested = sum((p.cost_basis for p in portfolio.positions), Money.zero(portfolio.currency))
    since = None
    if protected > invested:
        since = day if shortfall_since is None else shortfall_since
        if day >= rules.settlement_date(since):
            current = close.breaks(current, protected - invested)
            since = None
    kept = tuple(c for c in current if c.uncovered.amount > 0 or c.protections)
    return ClaimDay(close.portfolio, kept, since, close.tax, tuple(close.notes))


class _Close:
    """One day's claim bookings in progress: the portfolio they charge, and what they said."""

    def __init__(self, portfolio: Portfolio, day: date, rules: MarketRules) -> None:
        self.portfolio = portfolio
        self.tax = Money.zero(portfolio.currency)
        self.notes: list[Note] = []
        self._day = day
        self._rules = rules

    def deadline(self, claim: DividendClaim) -> DividendClaim:
        """Tax the part of *claim* still to reinvest once its deadline has passed."""
        if self._day <= claim.deadline or claim.uncovered.amount == 0:
            return claim
        owed = self._book(claim, claim.uncovered)
        if owed.amount > 0:
            self.notes.append(_deadline_missed(claim, owed))
        return replace(claim, uncovered=Money.zero(claim.uncovered.currency))

    def breaks(self, claims: list[DividendClaim], shortfall: Money) -> list[DividendClaim]:
        """Remove protections, latest ``until`` first, until *shortfall* is covered.

        Ties go to the newest claim, then to its protection added last, so the order is total.
        """
        amounts = [[protection.amount for protection in claim.protections] for claim in claims]
        removed = [Money.zero(shortfall.currency) for _ in claims]
        pieces = [
            (protection.until, _age(claim), place, index)
            for index, claim in enumerate(claims)
            for place, protection in enumerate(claim.protections)
        ]
        left = shortfall
        for _, _, place, index in sorted(pieces, reverse=True):
            if left.amount == 0:
                break
            taken = min(amounts[index][place], left)
            amounts[index][place] -= taken
            removed[index] += taken
            left -= taken
        broken: list[DividendClaim] = []
        for claim, rests, amount in zip(claims, amounts, removed, strict=True):
            if amount.amount > 0:
                owed = self._book(claim, amount)
                if owed.amount > 0:
                    self.notes.append(_claim_broken(claim, amount, owed))
            protections = zip(claim.protections, rests, strict=True)
            left_over = tuple(replace(p, amount=rest) for p, rest in protections if rest.amount)
            broken.append(replace(claim, protections=left_over))
        return broken

    def _book(self, claim: DividendClaim, amount: Money) -> Money:
        """Book the tax on *amount* of *claim* today, at the rate of the claim's pay date."""
        owed = self._rules.dividend_tax(amount, on=claim.pay_date)
        if owed.amount > 0:
            self.portfolio = self.portfolio.charge(MovementKind.TAX, owed, self._day)
            self.tax += owed
        return owed


def _unexpired(protections: tuple[Protection, ...], day: date) -> tuple[Protection, ...]:
    return tuple(protection for protection in protections if protection.until >= day)


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


def _claim_broken(claim: DividendClaim, amount: Money, tax: Money) -> Note:
    pay = claim.pay_date.isoformat()
    return Note(
        EXEMPTION_CLAIM_BROKEN,
        f"{claim.instrument.symbol}: {amount} reinvested from the dividend paid on {pay} was no "
        f"longer invested when the settlement grace ended, so its tax of {tax}, owed from {pay}, "
        "is booked today",
    )


def _deadline_missed(claim: DividendClaim, tax: Money) -> Note:
    pay = claim.pay_date.isoformat()
    return Note(
        EXEMPTION_DEADLINE_MISSED,
        f"{claim.instrument.symbol}: {claim.uncovered} of the dividend paid on {pay} was not "
        f"reinvested by {claim.deadline.isoformat()}, so its tax of {tax}, owed from {pay}, is "
        "booked today",
    )
