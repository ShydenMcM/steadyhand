"""Every strategy steadyhand ships, by the name the configuration uses.

Each one has a one-line summary, how much it trades, its settings, how many years of corporate
actions before a run it reads, and a complete plain-English guide in ``guides/<name>.md``, which
ships inside the package (core spec §8, §10.1; M5 spec §5.5, §5.6; M6 spec §4.3, §4.5).
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from importlib.resources.abc import Traversable
from types import MappingProxyType
from typing import Final

from steadyhand._validate import require_type
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Strategy

_NAME = re.compile(r"[a-z]+(_[a-z]+)*")


class Turnover(StrEnum):
    """How much a strategy trades, as ``steadyhand-idx strategies`` shows it."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class Setting:
    """One of a strategy's settings: a whole number, its default and bounds, and the one line of
    help ``init`` writes above its key in ``steadyhand.toml`` (M6 spec §4.5)."""

    name: str
    default: int
    minimum: int
    maximum: int
    help: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _NAME.fullmatch(self.name) is None:
            msg = f"a setting's name is a lowercase identifier, got {self.name!r}"
            raise ValueError(msg)
        for part in ("default", "minimum", "maximum"):
            value = getattr(self, part)
            if type(value) is not int:
                msg = f"{self.name}: the {part} must be an int, got {type(value).__name__}"
                raise TypeError(msg)
        if not self.minimum <= self.default <= self.maximum:
            msg = (
                f"{self.name}: the default {self.default} must be from {self.minimum} "
                f"to {self.maximum}"
            )
            raise ValueError(msg)
        require_type(self.help, str, f"{self.name} help")
        if not self.help.strip() or "\n" in self.help:
            msg = f"{self.name}: the help is one line of text"
            raise ValueError(msg)

    def check(self, value: object) -> int:
        """*value*, once it is a whole number within the bounds."""
        if type(value) is not int:
            msg = f"{self.name} must be a whole number, got {type(value).__name__}"
            raise TypeError(msg)
        if not self.minimum <= value <= self.maximum:
            msg = f"{self.name} must be from {self.minimum} to {self.maximum}, got {value}"
            raise ValueError(msg)
        return value


def _no_lookback(values: Mapping[str, int]) -> int:
    del values
    return 0


@dataclass(frozen=True, slots=True)
class Registered:
    """One shipped strategy: what makes it, a one-line summary, how much it trades, its settings,
    and how many calendar years of corporate actions before a run's first day it reads.

    ``make`` takes each setting as a keyword argument. Calling the entry checks the values and
    makes the strategy, from every setting's default when no values are given; ``lookback_years``
    takes the same values (M6 spec §4.3, §4.5). The registry is fixed data, so
    ``tests/engine/test_registry.py`` checks every summary and turnover.
    """

    make: Callable[..., Strategy]
    summary: str
    turnover: Turnover
    settings: tuple[Setting, ...] = ()
    lookback: Callable[[Mapping[str, int]], int] = _no_lookback

    def __post_init__(self) -> None:
        require_type(self.settings, tuple, "settings")
        names: set[str] = set()
        for setting in self.settings:
            require_type(setting, Setting, "setting")
            if setting.name in names:
                msg = f"the setting {setting.name} is registered twice"
                raise ValueError(msg)
            names.add(setting.name)

    def values(self, given: Mapping[str, int] | None = None) -> dict[str, int]:
        """This strategy's settings, checked: each from *given*, which may hold other
        strategies' settings too, as the flat ``[strategy]`` table does, or every default."""
        if given is None:
            return {setting.name: setting.default for setting in self.settings}
        found: dict[str, int] = {}
        for setting in self.settings:
            if setting.name not in given:
                msg = f"missing the setting {setting.name}"
                raise ValueError(msg)
            found[setting.name] = setting.check(given[setting.name])
        return found

    def __call__(self, values: Mapping[str, int] | None = None) -> Strategy:
        return self.make(**self.values(values))

    def lookback_years(self, values: Mapping[str, int] | None = None) -> int:
        """The calendar years of corporate actions the strategy reads before a run's first
        day: 0 for a strategy that reads none."""
        return self.lookback(self.values(values))


STRATEGIES: Final[Mapping[str, Registered]] = MappingProxyType(
    {
        "buy-and-hold": Registered(
            BuyAndHold,
            "Buys every stock it can on its first day in equal parts, then holds and reinvests.",
            Turnover.LOW,
        ),
    }
)

GUIDES: Final[Traversable] = files("steadyhand.strategies") / "guides"
"""The strategy guides, shipped inside the wheel."""


def guide(name: str) -> str:
    """The plain-English guide to the registered strategy *name*."""
    if name not in STRATEGIES:
        msg = f"no registered strategy is named {name!r}"
        raise KeyError(msg)
    return (GUIDES / f"{name}.md").read_text(encoding="utf-8")
