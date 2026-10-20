"""The literal-floor reader (#272), planted with every form a typed-in floor takes.

Shyden's decisions (2026-10-20, on #272): a Python literal floor is EVERY typed-in lower bound, as
in TypeScript, with no exemption; a bound that uses a name the reader cannot trace is refused, not
read as safe; everything in our own code is followed and only outside libraries pass; an index is
no value; both sides of `<` are judged. Each plant is written out by hand, so a form the reader
drops cannot drop out of this list with it (the global guard-forms catalogue, #446).
"""

import ast
import textwrap
from collections.abc import Mapping

import pytest
from literal_floors import (
    LIBRARY,
    UNKNOWN,
    Owners,
    Project,
    UnreadableSourceError,
    assert_tokens,
    read,
)


class StandIn:
    """The plants' types, written by hand where the guard asks mypy: each object, by its source
    text, is of the class of ours named for it, of a type the check cannot work out, or else of an
    outside library. A class is related to itself and to the classes named for it (``None``: a
    protocol, which any class of ours may meet)."""

    def __init__(
        self,
        owners: Mapping[str, str] | None = None,
        related: Mapping[str, frozenset[str] | None] | None = None,
    ) -> None:
        self._owners = dict(owners or {})
        self._related = dict(related or {})

    def owners(self, module: str, node: ast.Attribute) -> Owners:
        named = self._owners.get(ast.unparse(node.value), LIBRARY)
        return named if named in (LIBRARY, UNKNOWN) else frozenset({named})

    def class_name(self, module: str, node: ast.ClassDef) -> str:
        """The class's full name; a class named ``class <name>`` among the owners is one the
        types cannot name."""
        named = f"{module.removesuffix('.py')}.{node.name}"
        return UNKNOWN if f"class {node.name}" in self._owners else named

    def related(self, name: str) -> frozenset[str] | None:
        return self._related.get(name, frozenset({name}))


# Our own code, for the plants that follow a name out of the test file.
SOURCES = {
    "consts": "N = 5\nM = 1\n",
    "base": "B = 5\n",
    "chained": "from base import B\nN = B\n",
    "helpers": (
        "def minimum():\n    return 5\n\n"
        "def echo(n):\n    return n\n\n"
        "class Limits:\n    def least(self):\n        return 5\n"
    ),
    "pkg": "",
    "pkg.consts": "N = 5\n",
    "shapes": "class Limits:\n    LEAST = 5\n",
}
OURS = Project(SOURCES, StandIn())


def findings(source: str, project: Project = OURS) -> list[str]:
    return read(textwrap.dedent(source), "planted.py", project).findings


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ("assert len(x) >= 5\n", ["line 1: floor len(x) >= 5"]),
        ("assert len(x) > 5\n", ["line 1: floor len(x) > 5"]),
        ("assert 5 <= len(x)\n", ["line 1: floor 5 <= len(x)"]),
        ("assert 5 < len(x)\n", ["line 1: floor 5 < len(x)"]),
        ("assert 0 < 5 <= len(x)\n", ["line 1: floor 0 < 5 <= len(x)"]),
        ("assert len(x) >= 1_122\n", ["line 1: floor len(x) >= 1122"]),
        ("assert x >= -3\n", ["line 1: floor x >= -3"]),
        ("assert ratio >= 0.5\n", ["line 1: floor ratio >= 0.5"]),
        ("assert len(x) >= 400 + 20\n", ["line 1: floor len(x) >= 400 + 20"]),
        ("assert len(x) >= max(len(y), 5)\n", ["line 1: floor len(x) >= max(len(y), 5)"]),
        ("assert len(x) >= int(5)\n", ["line 1: floor len(x) >= int(5)"]),
        ("assert day >= date(2021, 3, 1)\n", ["line 1: floor day >= date(2021, 3, 1)"]),
        ("assert cash >= Decimal(1)\n", ["line 1: floor cash >= Decimal(1)"]),
        ("assert not len(x) < 5\n", ["line 1: floor len(x) < 5"]),
        ("assert len(x) >= 5, x\n", ["line 1: floor len(x) >= 5"]),
        ("assert (\n    len(x)\n    >= 5\n)\n", ["line 2: floor len(x) >= 5"]),
        ("assert len(x) >= 5 and ready\n", ["line 1: floor len(x) >= 5"]),
        ("assert all(len(g) >= 5 for g in groups)\n", ["line 1: floor len(g) >= 5"]),
        (
            "for d in found:\n    assert 5 <= d.size <= big\n",
            ["line 2: floor 5 <= d.size <= big"],
        ),
        ('assert cash >= Decimal("5")\n', ["line 1: floor cash >= Decimal('5')"]),
        ("assert gap >= Decimal('1e-20')\n", ["line 1: floor gap >= Decimal('1e-20')"]),
    ],
    ids=[
        "at-least",
        "more-than",
        "reversed-at-most",
        "reversed-less-than",
        "chained",
        "underscored",
        "negative",
        "fraction",
        "arithmetic",
        "inside-max",
        "cast",
        "date",
        "decimal",
        "ceiling-under-not",
        "with-a-message",
        "over-lines",
        "inside-and",
        "inside-a-generator",
        "chained-before-an-untraceable",
        "number-as-text",
        "exponent-as-text",
    ],
)
def test_a_literal_written_in_the_bound_is_a_floor(source: str, found: list[str]) -> None:
    assert findings(source) == found


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ("N = 5\n\ndef test_a():\n    assert len(x) >= N\n", ["line 4: floor len(x) >= N"]),
        ("def test_a():\n    n = 5\n    assert len(x) >= n\n", ["line 3: floor len(x) >= n"]),
        ("A = 5\nB = A\nassert len(x) >= B\n", ["line 3: floor len(x) >= B"]),
        ("N = 5\nassert len(x) >= max(len(y), N)\n", ["line 2: floor len(x) >= max(len(y), N)"]),
        ("low, high = 5, 9\nassert x >= low\n", ["line 2: floor x >= low"]),
        ("assert (n := 5) and len(x) >= n\n", ["line 1: floor len(x) >= n"]),
        (
            (
                "@pytest.mark.parametrize('floor', [5])\n"
                "def test_a(floor):\n    assert len(x) >= floor\n"
            ),
            ["line 3: floor len(x) >= floor"],
        ),
        (
            (
                "@pytest.mark.parametrize(('a', 'floor'), [(1, 5)])\n"
                "def test_a(a, floor):\n    assert len(x) >= floor\n"
            ),
            ["line 3: floor len(x) >= floor"],
        ),
        ("def check(x, floor=5):\n    assert len(x) >= floor\n", ["line 2: floor len(x) >= floor"]),
        ("for floor in (5, 6):\n    assert len(x) >= floor\n", ["line 2: floor len(x) >= floor"]),
        (
            "LIMITS = (5, 10, 20)\nassert len(x) >= LIMITS[2]\n",
            ["line 2: floor len(x) >= LIMITS[2]"],
        ),
        ("assert len(x) >= (5, 10)[i]\n", ["line 1: floor len(x) >= (5, 10)[i]"]),
        (
            "steps = list()\n\ndef test_a():\n    steps = 5\n    assert len(x) >= steps\n",
            ["line 5: floor len(x) >= steps"],
        ),
        (
            "N = 5\n\ndef test_a():\n    def inner():\n        assert len(x) >= N\n",
            ["line 5: floor len(x) >= N"],
        ),
        ("f = lambda: 5\nassert len(x) >= f()\n", ["line 2: floor len(x) >= f()"]),
        (
            "def least():\n    return 5\n\nf = least\nassert len(x) >= f()\n",
            ["line 5: floor len(x) >= f()"],
        ),
        (
            "def at_least(n):\n    return n\n\nassert len(x) >= at_least(5)\n",
            ["line 4: floor len(x) >= at_least(5)"],
        ),
        (
            "c = 0\nfor _ in list():\n    c += 2\nassert len(x) >= c\n",
            ["line 4: floor len(x) >= c"],
        ),
        ("n = sum(2 for _ in list())\nassert len(x) >= n\n", ["line 2: floor len(x) >= n"]),
        ("n = sum(1 for _ in list()) + 5\nassert len(x) >= n\n", ["line 2: floor len(x) >= n"]),
        ("n = sum(1 for _ in [5, 6])\nassert len(x) >= n\n", ["line 2: floor len(x) >= n"]),
        (
            "c = 5\nfor _ in list():\n    c += 1\nassert len(x) >= c\n",
            ["line 4: floor len(x) >= c"],
        ),
        ("c = 0\nd = c + 1\nassert len(x) >= d\n", ["line 3: floor len(x) >= d"]),
    ],
    ids=[
        "module-constant",
        "local-constant",
        "name-chain",
        "constant-inside-max",
        "unpacked",
        "walrus",
        "parametrized",
        "parametrized-tuple",
        "default",
        "loop-over-literals",
        "container-indexed",
        "written-container-indexed",
        "nearest-scope",
        "module-name-from-a-nested-function",
        "stored-lambda",
        "stored-function",
        "argument-through-a-parameter",
        "counted-by-two",
        "summed-twos",
        "count-plus-a-literal",
        "count-of-literals",
        "count-from-a-literal",
        "one-added-to-another-name",
    ],
)
def test_a_name_bound_to_a_literal_is_a_floor(source: str, found: list[str]) -> None:
    assert findings(source) == found


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ("from consts import N\nassert len(x) >= N\n", ["line 2: floor len(x) >= N"]),
        ("from chained import N\nassert len(x) >= N\n", ["line 2: floor len(x) >= N"]),
        ("import consts\nassert len(x) >= consts.N\n", ["line 2: floor len(x) >= consts.N"]),
        (
            "from pkg import consts\nassert len(x) >= consts.N\n",
            ["line 2: floor len(x) >= consts.N"],
        ),
        (
            "import pkg.consts\nassert len(x) >= pkg.consts.N\n",
            ["line 2: floor len(x) >= pkg.consts.N"],
        ),
        (
            "import pkg.consts as c\nassert len(x) >= c.N\n",
            ["line 2: floor len(x) >= c.N"],
        ),
        (
            "from helpers import minimum\nassert len(x) >= minimum()\n",
            ["line 2: floor len(x) >= minimum()"],
        ),
        (
            "import helpers\nassert len(x) >= helpers.minimum()\n",
            ["line 2: floor len(x) >= helpers.minimum()"],
        ),
        (
            "from helpers import minimum\nf = minimum\nassert len(x) >= f()\n",
            ["line 3: floor len(x) >= f()"],
        ),
        (
            "from helpers import echo\nassert len(x) >= echo(5)\n",
            ["line 2: floor len(x) >= echo(5)"],
        ),
    ],
    ids=[
        "imported-constant",
        "imported-through-another-module",
        "module-attribute",
        "submodule-attribute",
        "dotted-module",
        "aliased-module",
        "imported-function",
        "module-function",
        "stored-imported-function",
        "argument-into-our-helper",
    ],
)
def test_a_number_in_our_other_files_is_followed(source: str, found: list[str]) -> None:
    assert findings(source) == found


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ("USES_FLOOR = 12\n", ["line 1: floor constant USES_FLOOR = 12"]),
        ("files_floor = 3\n", ["line 1: floor constant files_floor = 3"]),
        ("FLOOR: int = 400 + 20\n", ["line 1: floor constant FLOOR = 400 + 20"]),
    ],
    ids=["upper-case", "lower-case", "annotated-arithmetic"],
)
def test_a_constant_named_for_a_floor_set_to_a_literal_is_a_floor(
    source: str, found: list[str]
) -> None:
    assert findings(source) == found


@pytest.mark.parametrize(
    ("source", "found"),
    [
        (
            "for n in found:\n    assert len(x) >= n\n",
            ["line 2: cannot trace n (a loop over values the test made) in len(x) >= n"],
        ),
        (
            "assert all(d.day <= today for d in found)\n",
            ["line 1: cannot trace d (a loop over values the test made) in d.day <= today"],
        ),
        (
            "def test_a(n):\n    assert len(x) >= n\n",
            ["line 2: cannot trace n (a fixture or helper parameter) in len(x) >= n"],
        ),
        (
            "@given(st.integers())\ndef test_a(n):\n    assert len(x) >= n\n",
            ["line 3: cannot trace n (a fixture or helper parameter) in len(x) >= n"],
        ),
        (
            "assert len(x) >= nowhere\n",
            ["line 1: cannot trace nowhere (never bound in this file) in len(x) >= nowhere"],
        ),
        (
            "assert len(x) >= nowhere()\n",
            ["line 1: cannot trace nowhere (never bound in this file) in len(x) >= nowhere()"],
        ),
        (
            "from consts import MISSING\nassert len(x) >= MISSING\n",
            ["line 2: cannot trace MISSING (not in our module consts) in len(x) >= MISSING"],
        ),
        (
            "from helpers import echo\nfor n in found:\n    assert len(x) >= echo(n)\n",
            ["line 3: cannot trace n (a loop over values the test made) in len(x) >= echo(n)"],
        ),
        (
            "n = len(list())\nfor n in found:\n    pass\nassert len(x) >= n\n",
            ["line 4: cannot trace n (a loop over values the test made) in len(x) >= n"],
        ),
        (
            "def test_a(least):\n    assert len(x) >= least()\n",
            ["line 2: cannot trace least (a fixture or helper parameter) in len(x) >= least()"],
        ),
    ],
    ids=[
        "loop",
        "comprehension",
        "fixture",
        "hypothesis",
        "unbound",
        "unbound-call",
        "missing-from-our-module",
        "loop-through-our-helper",
        "also-bound-by-a-loop",
        "fixture-holding-a-function",
    ],
)
def test_a_bound_the_reader_cannot_trace_is_refused(source: str, found: list[str]) -> None:
    assert findings(source) == found


@pytest.mark.parametrize(
    "source",
    [
        "assert len(x) > 0\n",
        "assert len(x) >= 0\n",
        "N = 0\nassert len(x) >= N\n",
        "x = list()\nassert len(x) <= 5\n",
        "x = list()\nassert len(x) < 5\n",
        "assert len(x) == 5\n",
        "y = list()\nassert len(x) >= len(y)\n",
        "y = list()\nn = len(y)\nassert len(x) >= n\n",
        "x = list()\nassert not len(x) > 5\n",
        "x = [1]\nif len(x) < 5:\n    pass\n",
        "from m import fn\ny = []\nassert len(x) >= len(fn(y))\n",
        "def low():\n    return 1\n\nassert x >= low\n",
        "FLOOR_REASON = 'measured'\n",
        "floors = [5]\n",
        "from pathlib import Path\np = Path().parents[2]\nassert count >= len(p.name)\n",
        "y = list()\nassert len(x) >= len(y[:2])\n",
        "y = list()\nfor i in found:\n    assert len(x) >= y[i]\n",
        "from m import N\nassert len(x) >= N\n",
        "from m import IDR, Money\nassert Money.zero(IDR) <= take_home\n",
        "import statistics\ny = list()\nassert len(x) >= statistics.median(y)\n",
        "from helpers import echo\ny = list()\nassert len(x) >= echo(len(y))\n",
        'assert name >= "abc"\n',
        "x = list()\nif len(x) > 5:\n    pytest.fail('too many')\n",
        (
            "def test_a():\n    steps = [5]\n\n"
            "def test_b():\n    steps = list()\n    assert len(x) >= len(steps)\n"
        ),
        (
            "def helper(source):\n    return source\n\n"
            "def test_a():\n    source = list()\n    assert len(x) >= len(source)\n"
        ),
        "from pathlib import Path\nROOT = Path(__file__).parent\nassert len(x) >= len(ROOT.name)\n",
        "x = list()\nassert len(x) in range(10)\n",
        "x = list()\nassert len(x) not in range(5, 10)\n",
        "x = list()\ny = list()\nassert max(x, y) == x\n",
        "y = list()\nobj = list()\nassert len(x) >= obj.count(y)\n",
        "def make():\n    return lambda: len(list())\n\nf = make()\nassert len(x) >= f()\n",
        (
            "from datetime import datetime\n\nclass World:\n    now = datetime(2026, 1, 5)\n\n"
            "x = list()\nassert len(x) >= datetime.now()\n"
        ),
        "x = list()\nn = sum(1 for _ in x)\nassert len(y) >= n\n",
        "x = list()\nc = 0\nfor _ in x:\n    c += 1\nassert len(y) >= c\n",
        "x = list()\nc = 0\nfor _ in x:\n    c = c + 1\nassert len(y) >= c\n",
        "n = sum([1 for _ in list()])\nassert len(y) >= n\n",
    ],
    ids=[
        "non-empty",
        "zero",
        "zero-constant",
        "ceiling",
        "ceiling-strict",
        "equality",
        "computed",
        "computed-name",
        "floor-under-not",
        "outside-an-assert",
        "imported-callee",
        "a-function",
        "floor-named-text",
        "floors-plural-list",
        "index-is-no-value",
        "slice-is-no-value",
        "index-name-is-no-value",
        "library-value",
        "library-namespace",
        "library-call",
        "computed-through-our-helper",
        "text-that-is-no-number",
        "ceiling-before-a-fail",
        "same-name-in-another-function",
        "parameter-name-in-another-function",
        "module-global",
        "range-from-zero",
        "not-in-a-range",
        "max-of-computed-values",
        "library-method-on-an-object",
        "stored-call-returning-a-computed-function",
        "library-method-sharing-a-name-with-our-attribute",
        "counted-by-sum",
        "counted-in-a-loop",
        "counted-by-adding-one",
        "counted-by-a-list",
    ],
)
def test_a_bound_with_no_typed_in_number_is_no_floor(source: str) -> None:
    assert findings(source) == []


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ("if len(x) < 5:\n    pytest.fail('few')\n", ["line 1: floor len(x) < 5"]),
        ("if len(x) < 5:\n    raise AssertionError(x)\n", ["line 1: floor len(x) < 5"]),
        (
            "self.assertGreaterEqual(len(x), 5)\n",
            ["line 1: floor self.assertGreaterEqual(len(x), 5)"],
        ),
        ("self.assertGreater(len(x), 5)\n", ["line 1: floor self.assertGreater(len(x), 5)"]),
        ("self.assertLess(5, len(x))\n", ["line 1: floor self.assertLess(5, len(x))"]),
        (
            "self.assertLessEqual(5, len(x))\n",
            ["line 1: floor self.assertLessEqual(5, len(x))"],
        ),
    ],
    ids=[
        "if-then-fail",
        "if-then-raise",
        "unittest-at-least",
        "unittest-more-than",
        "unittest-reversed-less",
        "unittest-reversed-at-most",
    ],
)
def test_a_check_written_outside_an_assert_is_read_too(source: str, found: list[str]) -> None:
    assert findings(source) == found


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ("assert x in range(5, 10)\n", ["line 1: floor x in range(5, 10)"]),
        ("assert x in range(5, 10, 2)\n", ["line 1: floor x in range(5, 10, 2)"]),
        ("assert max(x, 5) == x\n", ["line 1: floor max(x, 5) == x"]),
        ("assert x == max(x, 5)\n", ["line 1: floor x == max(x, 5)"]),
        ("assert min(x, 5) == 5\n", ["line 1: floor min(x, 5) == 5"]),
        (
            "def handlers():\n    return [lambda: 5]\n\nassert len(x) >= handlers()[0]()\n",
            ["line 4: floor len(x) >= handlers()[0]()"],
        ),
        (
            "def make():\n    return lambda: 5\n\nf = make()\nassert len(x) >= f()\n",
            ["line 5: floor len(x) >= f()"],
        ),
        ("fns = [lambda: 5]\nf = fns[0]\nassert len(x) >= f()\n", ["line 3: floor len(x) >= f()"]),
    ],
    ids=[
        "range",
        "range-with-a-step",
        "max-equals",
        "equals-max",
        "min-equals",
        "call-of-an-item",
        "call-of-a-stored-call-result",
        "call-of-a-stored-item",
    ],
)
def test_a_minimum_spelled_another_way_is_a_floor(source: str, found: list[str]) -> None:
    assert findings(source) == found


BOX = {"box": "planted.Box", "self": "planted.Box"}
REFUSED_TYPE = "a type the check cannot work out"


@pytest.mark.parametrize(
    ("source", "owners", "related", "found"),
    [
        (
            (
                "class Box:\n    def __init__(self):\n        self.least = 5\n\nbox = Box()\n"
                "assert len(x) >= box.least\n"
            ),
            BOX,
            {},
            ["line 6: floor len(x) >= box.least"],
        ),
        (
            (
                "@dataclass\nclass Box:\n    least: int = 5\n\n"
                "box = Box()\nassert len(x) >= box.least\n"
            ),
            BOX,
            {},
            ["line 6: floor len(x) >= box.least"],
        ),
        (
            "class Limits:\n    LEAST = 5\n\nassert len(x) >= Limits.LEAST\n",
            {"Limits": "planted.Limits"},
            {},
            ["line 4: floor len(x) >= Limits.LEAST"],
        ),
        (
            "from shapes import Limits\nassert len(x) >= Limits.LEAST\n",
            {"Limits": "shapes.Limits"},
            {},
            ["line 2: floor len(x) >= Limits.LEAST"],
        ),
        (
            "import shapes\nassert len(x) >= shapes.Limits.LEAST\n",
            {"shapes.Limits": "shapes.Limits"},
            {},
            ["line 2: floor len(x) >= shapes.Limits.LEAST"],
        ),
        (
            "class Limits:\n    LEAST = 5\n\nassert len(x) >= Limits().LEAST\n",
            {"Limits()": "planted.Limits"},
            {},
            ["line 4: floor len(x) >= Limits().LEAST"],
        ),
        (
            "class C:\n    def least(self):\n        return 5\n\nassert len(x) >= C().least()\n",
            {"C()": "planted.C"},
            {},
            ["line 5: floor len(x) >= C().least()"],
        ),
        (
            "from helpers import Limits\nlimits = Limits()\nassert len(x) >= limits.least()\n",
            {"limits": "helpers.Limits"},
            {},
            ["line 3: floor len(x) >= limits.least()"],
        ),
        (
            (
                "class Box:\n    def __init__(self):\n        self.check = lambda: 5\n\n"
                "box = Box()\n"
                "assert len(x) >= box.check()\n"
            ),
            BOX,
            {},
            ["line 6: floor len(x) >= box.check()"],
        ),
        (
            (
                "def five():\n    return 5\n\nclass Box:\n    def __init__(self):\n"
                "        self.check = five\n\nbox = Box()\nassert len(x) >= box.check()\n"
            ),
            BOX,
            {},
            ["line 9: floor len(x) >= box.check()"],
        ),
        (
            (
                "class Box:\n    def __init__(self, n):\n        self.least = n\n\n"
                "box = Box(list())\nassert len(x) >= box.least\n"
            ),
            BOX,
            {},
            ["line 6: cannot trace n (a fixture or helper parameter) in len(x) >= box.least"],
        ),
        (
            (
                "class Box:\n    def set_least(self, n):\n        self.least = n\n\n"
                "box = Box()\nbox.set_least(5)\nassert len(x) >= box.least\n"
            ),
            BOX,
            {},
            ["line 7: cannot trace n (a fixture or helper parameter) in len(x) >= box.least"],
        ),
        (
            (
                "class Box:\n    def __init__(self):\n        self.least = len(list())\n\n"
                "box = Box()\n"
                "assert len(x) >= box.least\n"
            ),
            BOX,
            {},
            [],
        ),
        (
            (
                "class Box:\n    def __init__(self):\n        self.check = lambda: len(list())\n\n"
                "box = Box()\nassert len(x) >= box.check()\n"
            ),
            BOX,
            {},
            [],
        ),
        (
            (
                "class Span:\n    def __init__(self, days):\n        self.days = days\n\n"
                "from datetime import date\nassert len(x) >= (date.today() - date.today()).days\n"
            ),
            {"self": "planted.Span"},
            {},
            [],
        ),
        (
            (
                "class Words:\n    def split(self):\n        return 5\n\n"
                "assert len(x) >= len('a b'.split())\n"
            ),
            {},
            {},
            [],
        ),
        ("limits = list()\nassert len(x) >= limits.least()\n", {}, {}, []),
        (
            (
                "class A:\n    least = 5\n\nclass B:\n    least = len(list())\n\nb = B()\n"
                "assert len(x) >= b.least\n"
            ),
            {"b": "planted.B"},
            {},
            [],
        ),
        (
            (
                "class A:\n    def least(self):\n        return 5\n\nclass B:\n"
                "    def least(self):\n        return len(list())\n\nb = B()\n"
                "assert len(x) >= b.least()\n"
            ),
            {"b": "planted.B"},
            {},
            [],
        ),
        (
            (
                "class Base:\n    least = len(list())\n\nclass Sub(Base):\n    least = 5\n\n"
                "def make() -> Base:\n    return Sub()\n\nb = make()\nassert len(x) >= b.least\n"
            ),
            {"b": "planted.Base"},
            {"planted.Base": frozenset({"planted.Base", "planted.Sub"})},
            ["line 11: floor len(x) >= b.least"],
        ),
        (
            (
                "class Shape(Protocol):\n    least: int\n\nclass Square:\n    least = 5\n\n"
                "def make() -> Shape:\n    return Square()\n\ns = make()\n"
                "assert len(x) >= s.least\n"
            ),
            {"s": "planted.Shape"},
            {"planted.Shape": None},
            ["line 11: floor len(x) >= s.least"],
        ),
        (
            "thing = list()\nassert len(x) >= thing.least\n",
            {"thing": UNKNOWN},
            {},
            [f"line 2: cannot trace thing ({REFUSED_TYPE}) in len(x) >= thing.least"],
        ),
        (
            "thing = list()\nassert len(x) >= thing.least()\n",
            {"thing": UNKNOWN},
            {},
            [f"line 2: cannot trace thing ({REFUSED_TYPE}) in len(x) >= thing.least()"],
        ),
        (
            (
                "class Box:\n    least = len(list())\n\nthing = list()\nthing.least = 5\n"
                "box = Box()\n"
                "assert len(x) >= box.least\n"
            ),
            {"thing": UNKNOWN, "box": "planted.Box"},
            {},
            ["line 7: floor len(x) >= box.least"],
        ),
        (
            (
                "class Box:\n    least = len(list())\n\nns = list()\nns.least = 5\nbox = Box()\n"
                "assert len(x) >= box.least\n"
            ),
            {"box": "planted.Box"},
            {},
            [],
        ),
        (
            (
                "class Box:\n    least = len(list())\n\nclass Mystery:\n    least = 5\n\n"
                "box = Box()\nassert len(x) >= box.least\n"
            ),
            {"box": "planted.Box", "class Mystery": UNKNOWN},
            {},
            ["line 8: floor len(x) >= box.least"],
        ),
        (
            (
                "class Box:\n    pass\n\nclass Mystery:\n    def least(self):\n        return 5\n\n"
                "box = Box()\nassert len(x) >= box.least()\n"
            ),
            {"box": "planted.Box", "class Mystery": UNKNOWN},
            {},
            ["line 9: floor len(x) >= box.least()"],
        ),
    ],
    ids=[
        "attribute-set-in-a-method",
        "dataclass-default",
        "class-constant",
        "imported-class-constant",
        "module-class-constant",
        "attribute-of-a-made-object",
        "method",
        "imported-class-method",
        "attribute-holding-a-lambda",
        "attribute-holding-a-function",
        "attribute-from-a-constructor-argument",
        "attribute-from-a-method-argument",
        "attribute-computed-in-a-constructor",
        "attribute-holding-a-computed-function",
        "library-object-sharing-an-attribute-name",
        "library-method-sharing-a-method-name",
        "list-method-sharing-a-method-name",
        "same-attribute-on-another-class-of-ours",
        "same-method-on-another-class-of-ours",
        "attribute-of-a-subclass",
        "member-of-a-protocol",
        "attribute-of-a-type-the-check-cannot-work-out",
        "method-of-a-type-the-check-cannot-work-out",
        "set-on-an-object-of-a-type-the-check-cannot-work-out",
        "set-on-a-library-object",
        "attribute-of-a-class-the-types-cannot-name",
        "method-of-a-class-the-types-cannot-name",
    ],
)
def test_an_attribute_or_method_is_judged_by_its_objects_type(
    source: str,
    owners: Mapping[str, str],
    related: Mapping[str, frozenset[str] | None],
    found: list[str],
) -> None:
    assert findings(source, Project(SOURCES, StandIn(owners, related))) == found


def test_the_reader_counts_every_assert_it_judged() -> None:
    source = "def test_a():\n    assert x\n    assert (\n        y\n    )\nassert z, 'msg'\n"
    assert read(source, "planted.py", OURS).asserts == 3


def test_a_file_that_does_not_parse_is_refused_by_name() -> None:
    with pytest.raises(UnreadableSourceError, match=r"^planted\.py: cannot parse it"):
        read("assert (\n", "planted.py", OURS)


def test_the_cross_check_counts_assert_keywords_without_comments_or_text() -> None:
    source = "# assert in a comment\nx = 'assert in text'\nassert x\nassert y  # assert\n"
    assert assert_tokens(source, "planted.py") == 2


def test_the_cross_check_refuses_a_file_it_cannot_read_by_name() -> None:
    with pytest.raises(UnreadableSourceError, match=r"^planted\.py: cannot read its words"):
        assert_tokens("x = '''\n", "planted.py")
