"""No Hypothesis profile fails a test on wall-clock time alone (#30).

A per-example deadline measures the machine as well as the code, so a busy laptop gave a red
that the next run could not reproduce. Timing belongs in the performance tests, not in every
property test.
"""

import ast
from pathlib import Path

import pytest
from hypothesis import settings
from population import searched, tracked
from source_tree import UnreadableSourceError, parse

TESTS = Path(__file__).resolve().parents[1]
CONFTEST = TESTS / "conftest.py"
PROFILES = ("dev", "ci")

# Measured on 2026-10-03 (#178): 94 Python files under tests/ besides conftest.py. Lower it only by
# a deliberate edit when the suite shrinks.
FILES_FLOOR = 93


def deadline_keywords(source: str, name: str) -> list[int]:
    """Line numbers of every call in *source* that passes a ``deadline=`` keyword. *name* names
    the file in errors."""
    return [
        node.lineno
        for node in ast.walk(parse(source, name))
        if isinstance(node, ast.Call) and any(kw.arg == "deadline" for kw in node.keywords)
    ]


@pytest.mark.parametrize("name", PROFILES)
def test_every_profile_has_no_deadline(name: str) -> None:
    assert settings.get_profile(name).deadline is None, f"profile {name!r} keeps a deadline"


def test_the_detector_finds_a_deadline_in_a_decorator_and_in_a_function() -> None:
    source = (
        "@settings(deadline=500)\n"
        "def test_x(): ...\n"
        "def helper():\n"
        "    return settings(max_examples=5, deadline=None)\n"
        "settings(max_examples=5)\n"
    )
    assert deadline_keywords(source, "sample.py") == [1, 4]


def test_the_detector_names_the_file_it_cannot_parse() -> None:
    with pytest.raises(UnreadableSourceError, match=r"^broken\.py: "):
        deadline_keywords("def (:\n", "broken.py")


def test_the_detector_finds_the_profiles_in_conftest() -> None:
    # Known positive: without it, a detector that matched nothing would pass the next test.
    assert len(deadline_keywords(CONFTEST.read_text(), CONFTEST.name)) == len(PROFILES)


def test_no_test_sets_its_own_deadline() -> None:
    files = [p for p in sorted(TESTS.rglob("*.py")) if p != CONFTEST]
    # Independent of the walk: the test files as git lists them.
    assert files == [p for p in tracked(TESTS, ".py") if p != CONFTEST]
    assert len(files) >= FILES_FLOOR, f"read {len(files)} files under {TESTS}"
    offenders = {
        str(p.relative_to(TESTS)): lines
        for p in files
        if (lines := deadline_keywords(p.read_text(), str(p.relative_to(TESTS))))
    }
    assert searched(offenders, of=len(files), what="test files") == {}, (
        f"set the deadline in conftest.py profiles only: {offenders}"
    )
