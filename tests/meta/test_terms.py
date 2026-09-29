"""Every figure a report can show has a term, and ``FIGURES`` names only real fields (T1 §3.2).

The figure fields are derived here, never listed: the walk starts at the report types and
follows their fields and properties into every dataclass they hold, through tuples, mappings
and optionals. A field or property typed ``Money`` or ``Decimal`` is a figure. Private names are
skipped, since no report shows them. So a figure added to any nested dataclass fails this test
until ``FIGURES`` gives it a term, without anyone adding the class to a list.
"""

import dataclasses
import typing
from collections.abc import Mapping
from decimal import Decimal
from types import NoneType

from key_walk import TERM_MODULE, key_constants

from steadyhand import FIGURES, BacktestResult, DayReport, IncomeReport, Money
from steadyhand_idx.paper import PaperRun

REPORTS: tuple[type, ...] = (DayReport, BacktestResult, IncomeReport, PaperRun)
FIGURE_TYPES = (Money, Decimal)


def figure_fields(roots: tuple[type, ...]) -> tuple[set[str], dict[str, set[type]]]:
    """Every public ``Money`` or ``Decimal`` field or property reachable from *roots*, as
    ``"Class.name"``, and every class visited under its name (two classes sharing a name would
    make a ``"Class.name"`` ambiguous)."""
    figures: set[str] = set()
    visited: dict[str, set[type]] = {}

    def visit_class(cls: type) -> None:
        if cls in visited.get(cls.__name__, set()):
            return
        visited.setdefault(cls.__name__, set()).add(cls)
        hints = typing.get_type_hints(cls)
        members = [(field.name, hints[field.name]) for field in dataclasses.fields(cls)]
        for name, member in vars(cls).items():
            if isinstance(member, property) and member.fget is not None:
                members.append((name, typing.get_type_hints(member.fget).get("return", NoneType)))
        for name, hint in members:
            if not name.startswith("_"):
                visit_type(f"{cls.__name__}.{name}", hint)

    def visit_type(where: str, hint: object) -> None:
        if hint in FIGURE_TYPES:
            figures.add(where)
        elif isinstance(hint, type) and dataclasses.is_dataclass(hint):
            visit_class(hint)
        else:
            for argument in typing.get_args(hint):
                visit_type(where, argument)

    for root in roots:
        visit_class(root)
    return figures, visited


@dataclasses.dataclass(frozen=True)
class _Leaf:
    amount: Money
    count: int


@dataclasses.dataclass(frozen=True)
class _Root:
    rate: Decimal
    maybe: Decimal | None
    leaves: tuple[_Leaf, ...]
    by_name: Mapping[str, _Leaf]
    parent: "_Root | None"
    label: str
    _hidden: Money

    @property
    def total(self) -> Money:
        return self._hidden

    @property
    def _secret(self) -> Money:
        return self._hidden

    @property
    def described(self) -> str:
        return self.label


def test_the_walk_follows_fields_properties_and_containers() -> None:
    figures, visited = figure_fields((_Root,))
    assert figures == {"_Root.rate", "_Root.maybe", "_Root.total", "_Leaf.amount"}
    assert set(visited) == {"_Root", "_Leaf"}


def test_the_walk_reaches_every_report() -> None:
    figures, visited = figure_fields(REPORTS)
    assert {
        "DayReport.value",
        "Fill.price",
        "Metrics.total_return",
        "RunRate.annual_gross",
        "ScenarioProjection.years",
        "Costs.total",
    } <= figures
    assert len(figures) >= 60
    assert {name: classes for name, classes in visited.items() if len(classes) > 1} == {}


def test_every_figure_has_a_term() -> None:
    figures, _ = figure_fields(REPORTS)
    assert sorted(figures - set(FIGURES)) == []


def test_figures_names_only_fields_that_exist() -> None:
    figures, _ = figure_fields(REPORTS)
    assert sorted(set(FIGURES) - figures) == []


def test_every_term_is_a_figures_value_and_every_value_is_a_term() -> None:
    terms = {value for _, value in key_constants(TERM_MODULE.read_text(encoding="utf-8"))}
    assert len(terms) >= 30
    assert sorted(terms - set(FIGURES.values())) == []
    assert sorted(set(FIGURES.values()) - terms) == []
