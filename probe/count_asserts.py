"""#568 probe: record every assert statement that passes, per test, as pytest reports it."""

import collections
import json
import os
from pathlib import Path

import pytest

pytest.register_assert_rewrite("cli_world", "script_imports", "stood_in_commands")

_PASSED: dict[str, list[list[object]]] = collections.defaultdict(list)


def pytest_assertion_pass(item: pytest.Item, lineno: int, orig: str) -> None:
    _PASSED[item.nodeid].append([item.path.name, lineno, orig])


def pytest_sessionfinish() -> None:
    with Path(os.environ["ASSERT_COUNT_OUT"]).open("w", encoding="utf-8") as out:
        json.dump(_PASSED, out, indent=1, sort_keys=True)
