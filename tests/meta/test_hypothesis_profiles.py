"""No Hypothesis profile fails a test on wall-clock time alone (#30).

A per-example deadline measures the machine as well as the code, so a busy laptop gave a red
that the next run could not reproduce. Timing belongs in the performance tests, not in every
property test.
"""

import ast
from pathlib import Path

from hypothesis import settings

TESTS = Path(__file__).resolve().parents[1]
CONFTEST = TESTS / "conftest.py"
PROFILES = ("dev", "ci")


def deadline_keywords(source: str) -> list[int]:
    """Line numbers of every call in *source* that passes a ``deadline=`` keyword."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and any(kw.arg == "deadline" for kw in node.keywords)
    ]


def test_every_profile_has_no_deadline() -> None:
    for name in PROFILES:
        assert settings.get_profile(name).deadline is None, f"profile {name!r} keeps a deadline"


def test_the_detector_finds_the_profiles_in_conftest() -> None:
    # Known positive: without it, a detector that matched nothing would pass the next test.
    assert len(deadline_keywords(CONFTEST.read_text())) == len(PROFILES)


def test_no_test_sets_its_own_deadline() -> None:
    files = [p for p in sorted(TESTS.rglob("*.py")) if p != CONFTEST]
    assert len(files) >= 10, f"only {len(files)} test files found under {TESTS}"
    offenders = {
        str(p.relative_to(TESTS)): lines
        for p in files
        if (lines := deadline_keywords(p.read_text()))
    }
    assert offenders == {}, f"set the deadline in conftest.py profiles only: {offenders}"
