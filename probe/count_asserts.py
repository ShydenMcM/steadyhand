"""#568 probe: record every assert statement that passes, per test, as pytest reports it."""

import collections
import json
import os
import sys
from pathlib import Path

import pytest

pytest.register_assert_rewrite("cli_world", "script_imports", "stood_in_commands")

_PASSED: dict[str, list[list[object]]] = collections.defaultdict(list)
_OUTCOMES: dict[str, str] = {}
_RUNNING: list[pytest.Item] = []
_RAISES = pytest.raises


class _CountedRaises:
    """A `pytest.raises` block, counted when the exception it expects is raised."""

    def __init__(self, inner: object, where: tuple[str, int]) -> None:
        self.inner = inner
        self.where = where

    def __enter__(self) -> object:
        return self.inner.__enter__()  # type: ignore[attr-defined]

    def __exit__(self, *raised: object) -> bool:
        caught = self.inner.__exit__(*raised)  # type: ignore[attr-defined]
        if caught and _RUNNING:
            file, line = self.where
            _PASSED[_RUNNING[-1].nodeid].append([file, line, "pytest.raises"])
        return caught


def _raises(*args: object, **kwargs: object) -> object:
    caller = sys._getframe(1)  # where the block is, as pytest names asserts
    where = (os.path.basename(caller.f_code.co_filename), caller.f_lineno)  # noqa: PTH119
    inner = _RAISES(*args, **kwargs)  # type: ignore[call-overload]
    if len(args) > 1 and _RUNNING:  # the call form has already run and caught
        _PASSED[_RUNNING[-1].nodeid].append([where[0], where[1], "pytest.raises"])
        return inner
    return _CountedRaises(inner, where)


pytest.raises = _raises  # type: ignore[assignment]


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> object:
    _RUNNING.append(item)
    try:
        return (yield)
    finally:
        _RUNNING.pop()


def pytest_assertion_pass(item: pytest.Item, lineno: int, orig: str) -> None:
    _PASSED[item.nodeid].append([item.path.name, lineno, orig])


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when == "call" or report.outcome != "passed":
        _OUTCOMES[report.nodeid] = report.outcome


def pytest_sessionfinish() -> None:
    with Path(os.environ["ASSERT_COUNT_OUT"]).open("w", encoding="utf-8") as out:
        json.dump({"asserts": _PASSED, "outcomes": _OUTCOMES}, out, indent=1, sort_keys=True)
