"""The literal-floor reader (#272), planted with every form a typed-in floor takes.

Shyden's decision (2026-10-20, on #272): a Python literal floor is EVERY typed-in lower bound in an
assert, as in TypeScript, with no exemption, and a bound that uses a name the reader cannot trace
to a value in its file is refused, not read as safe. Each plant is written out by hand, so a form
the reader drops cannot drop out of this list with it (the global guard-forms catalogue, #446).
"""

import textwrap

import pytest
from literal_floors import UnreadableSourceError, assert_tokens, read


def findings(source: str) -> list[str]:
    return read(textwrap.dedent(source), "planted.py").findings


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
    ],
)
def test_a_name_bound_to_a_literal_is_a_floor(source: str, found: list[str]) -> None:
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
            "from m import N\nassert len(x) >= N\n",
            ["line 2: cannot trace N (an import) in len(x) >= N"],
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
            "from m import IDR, Money\nassert Money.zero(IDR) <= take_home\n",
            ["line 2: cannot trace IDR (an import) in Money.zero(IDR) <= take_home"],
        ),
        (
            "n = len(make())\nfor n in found:\n    pass\nassert len(x) >= n\n",
            ["line 4: cannot trace n (a loop over values the test made) in len(x) >= n"],
        ),
    ],
    ids=[
        "loop",
        "comprehension",
        "import",
        "fixture",
        "hypothesis",
        "unbound",
        "imported-argument",
        "also-bound-by-a-loop",
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
        "x = make()\nassert len(x) <= 5\n",
        "x = make()\nassert len(x) < 5\n",
        "assert len(x) == 5\n",
        "y = make()\nassert len(x) >= len(y)\n",
        "y = make()\nn = len(y)\nassert len(x) >= n\n",
        "x = make()\nassert not len(x) > 5\n",
        "x = [1]\nif len(x) < 5:\n    pass\n",
        "from m import fn\ny = []\nassert len(x) >= len(fn(y))\n",
        "def low():\n    return 1\n\nassert x >= low\n",
        "FLOOR_REASON = 'measured'\n",
        "floors = [5]\n",
        "p = Path().parents[2]\nassert count >= len(p.name)\n",
        "y = make()\nassert len(x) >= len(y[:2])\n",
        "y = make()\nfor i in found:\n    assert len(x) >= y[i]\n",
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
    ],
)
def test_a_bound_with_no_typed_in_number_is_no_floor(source: str) -> None:
    assert findings(source) == []


def test_the_reader_counts_every_assert_it_judged() -> None:
    source = "def test_a():\n    assert x\n    assert (\n        y\n    )\nassert z, 'msg'\n"
    assert read(source, "planted.py").asserts == 3


def test_a_file_that_does_not_parse_is_refused_by_name() -> None:
    with pytest.raises(UnreadableSourceError, match=r"^planted\.py: cannot parse it"):
        read("assert (\n", "planted.py")


def test_the_cross_check_counts_assert_keywords_without_comments_or_text() -> None:
    source = "# assert in a comment\nx = 'assert in text'\nassert x\nassert y  # assert\n"
    assert assert_tokens(source, "planted.py") == 2


def test_the_cross_check_refuses_a_file_it_cannot_read_by_name() -> None:
    with pytest.raises(UnreadableSourceError, match=r"^planted\.py: cannot read its words"):
        assert_tokens("x = '''\n", "planted.py")
