"""The dividend reinvestment exemption as claims the engine keeps (M4 spec §6).

With ``EngineSettings.dividend_reinvestment_exemption`` on, a dividend that can be exempt books no
tax when it is paid. It opens a ``DividendClaim`` instead, which the engine carries in
``Holdings.claims`` until its reinvestment and holding conditions are met or broken. Every figure
a claim gives is an estimate: it assumes the investor files the annual realisation reports
(docs/research/t-tax.md §7), which the engine cannot see.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from steadyhand._validate import require_date, require_type
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.types import Instrument


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
