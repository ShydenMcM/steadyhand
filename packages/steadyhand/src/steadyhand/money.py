"""Money in integer minor units, with explicit rounding.

``float`` never appears in this module (a meta-guard enforces it): a float cannot hold most
decimal amounts exactly, and a trading simulation that drifts by a rupiah a day is wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, Inexact, localcontext
from enum import Enum
from typing import Final

MAX_MINOR_UNITS: Final = 4
_CURRENCY_CODE = re.compile(r"[A-Z]{3}")


class CurrencyMismatchError(ValueError):
    """Two amounts in different currencies were combined or compared."""

    def __init__(self, left: Currency, right: Currency) -> None:
        super().__init__(f"cannot combine {left.code} with {right.code}")


@dataclass(frozen=True, slots=True)
class Currency:
    """An ISO 4217 currency and the number of decimal places in its minor unit."""

    code: str
    minor_units: int

    def __post_init__(self) -> None:
        if not isinstance(self.code, str):
            msg = f"currency code must be a str, got {type(self.code).__name__}"
            raise TypeError(msg)
        if _CURRENCY_CODE.fullmatch(self.code) is None:
            msg = f"currency code must be three capital letters, got {self.code!r}"
            raise ValueError(msg)
        if type(self.minor_units) is not int or not 0 <= self.minor_units <= MAX_MINOR_UNITS:
            msg = (
                f"minor_units must be an int from 0 to {MAX_MINOR_UNITS}, got {self.minor_units!r}"
            )
            raise ValueError(msg)


IDR: Final = Currency("IDR", 0)
"""Indonesian rupiah. It has no minor unit in practical use, so one unit is one rupiah."""


class Rounding(Enum):
    """Which way a rate calculation rounds to a whole minor unit."""

    UP = ROUND_CEILING
    """Towards positive infinity. Use it for what you pay: costs and buy prices."""
    DOWN = ROUND_FLOOR
    """Towards negative infinity. Use it for what you receive: proceeds and dividends."""


@dataclass(frozen=True, slots=True)
class Money:
    """An exact amount: an ``int`` of minor units plus its currency."""

    amount: int
    currency: Currency

    def __post_init__(self) -> None:
        if type(self.amount) is not int:
            msg = f"Money amount must be an int of minor units, got {type(self.amount).__name__}"
            raise TypeError(msg)
        if not isinstance(self.currency, Currency):
            msg = f"Money currency must be a Currency, got {type(self.currency).__name__}"
            raise TypeError(msg)

    @classmethod
    def zero(cls, currency: Currency) -> Money:
        return cls(0, currency)

    def _require_same_currency(self, other: Money) -> None:
        if other.currency != self.currency:
            raise CurrencyMismatchError(self.currency, other.currency)

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __mul__(self, quantity: int) -> Money:
        if type(quantity) is not int:
            msg = (
                f"multiply Money by an int quantity, got {type(quantity).__name__}; "
                "use times() for a rate"
            )
            raise TypeError(msg)
        return Money(self.amount * quantity, self.currency)

    def __rmul__(self, quantity: int) -> Money:
        return self * quantity

    def __lt__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return self.amount >= other.amount

    def times(self, rate: Decimal, rounding: Rounding) -> Money:
        """Multiply by *rate* exactly, then round once to a whole minor unit."""
        if not isinstance(rate, Decimal):
            msg = f"rate must be a Decimal, got {type(rate).__name__}"
            raise TypeError(msg)
        if not rate.is_finite():
            msg = f"rate must be finite, got {rate}"
            raise ValueError(msg)
        # A product has at most as many digits as its two factors together. Giving the context
        # that much precision makes the multiplication exact, and trapping Inexact makes any
        # future mistake in this sum fail loudly instead of rounding twice.
        digits = len(str(abs(self.amount))) + len(rate.as_tuple().digits)
        with localcontext() as context:
            context.prec = digits + 1
            context.traps[Inexact] = True
            whole = (Decimal(self.amount) * rate).to_integral_value(rounding=rounding.value)
        return Money(int(whole), self.currency)

    def __str__(self) -> str:
        sign = "-" if self.amount < 0 else ""
        places = self.currency.minor_units
        units, minor = divmod(abs(self.amount), 10**places)
        if places == 0:
            return f"{self.currency.code} {sign}{units:,}"
        return f"{self.currency.code} {sign}{units:,}.{minor:0{places}d}"
