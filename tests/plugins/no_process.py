"""A unit test starts no process and opens no outside connection (#286).

Shyden's rules (every project): "A unit test never reaches a real service" and "Nor does a unit
test start a process" (2026-10-08, ruled in shyden.co.uk #629). ``tests/conftest.py`` installs
this plugin for a unit run only: the guards and the integration suite need real processes.

Each entry point is wrapped where every route to it passes: the ``Popen`` method behind
``subprocess.run`` and friends, the ``fork_exec`` both ``subprocess`` (bound at its import) and
``multiprocessing`` call, a process's ``start`` under every start method, each ``os`` call by its
own name, and a socket's ``connect`` and every name lookup. A wrapped call is refused by name
before anything starts, and a refusal the test swallowed still fails it.

Tests marked ``perf`` or ``live`` are other suites (CI's perf step, the yahoo-shape workflow),
which the unit run leaves out by its default ``-m``; they run unarmed when chosen by marker.
"""

import _posixsubprocess
import functools
import multiprocessing.process
import os
import socket
import subprocess
from collections.abc import Callable, Generator, Iterable
from typing import Any

import pytest

RULE = "a unit test starts no process and opens no outside connection"

ENTRY_POINTS: tuple[tuple[str, object, str], ...] = (
    ("subprocess.Popen", subprocess.Popen, "_execute_child"),
    ("subprocess._fork_exec", subprocess, "_fork_exec"),
    ("_posixsubprocess.fork_exec", _posixsubprocess, "fork_exec"),
    ("multiprocessing start", multiprocessing.process.BaseProcess, "start"),
    *(
        (f"os.{name}", os, name)
        for name in (
            "fork",
            "forkpty",
            "posix_spawn",
            "posix_spawnp",
            "system",
            "popen",
            "execv",
            "execve",
            "execl",
            "execle",
            "execlp",
            "execlpe",
            "execvp",
            "execvpe",
            "spawnv",
            "spawnve",
            "spawnvp",
            "spawnvpe",
            "spawnl",
            "spawnle",
            "spawnlp",
            "spawnlpe",
        )
    ),
    ("socket.connect", socket.socket, "connect"),
    ("socket.connect_ex", socket.socket, "connect_ex"),
    *(
        (f"socket.{name}", socket, name)
        for name in (
            "getaddrinfo",
            "gethostbyname",
            "gethostbyname_ex",
            "gethostbyaddr",
            "getnameinfo",
        )
    ),
)
"""Every way a test could start a process or reach out: (label, owner, attribute)."""

PERF_OR_LIVE = frozenset({"perf", "live"})

_armed = [False]
_refused: list[str] = []


class UnitRuleError(RuntimeError):
    """A unit test called a process or network entry point."""


def _refusing(label: str, original: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(original)
    def refusing(*args: object, **kwargs: object) -> object:
        if _armed[0]:
            _refused.append(label)
            msg = (
                f"{label} was called: {RULE} (#286). Call the code in-process with the process "
                "stood in, or move the real case to tests/integration and keep a stand-in of its "
                "logic here."
            )
            raise UnitRuleError(msg)
        return original(*args, **kwargs)

    refusing.__refuses__ = label  # type: ignore[attr-defined]
    return refusing


def install() -> None:
    """Wrap every entry point, once, and arm the refusal (collection is armed too)."""
    for label, owner, name in ENTRY_POINTS:
        current = getattr(owner, name)
        if getattr(current, "__refuses__", None) != label:
            setattr(owner, name, _refusing(label, current))
    _armed[0] = True


def armed_for(markers: Iterable[str]) -> bool:
    """Whether a test with these markers is held to the unit rule."""
    return not PERF_OR_LIVE.intersection(markers)


def take_refused() -> list[str]:
    """The refusals since the last call, which are then forgotten."""
    taken = list(_refused)
    _refused.clear()
    return taken


def fail_swallowed(report: pytest.TestReport, refused: list[str]) -> None:
    """Fail a passing *report* whose test was refused and carried on regardless."""
    if refused and report.passed:
        report.outcome = "failed"
        report.longrepr = (
            f"refused, and the test carried on as if nothing happened: {', '.join(refused)} "
            f"({RULE}, #286)"
        )


def refuse_collected(refused: list[str]) -> None:
    """Stop the run when importing a test module was refused and the import carried on."""
    if refused:
        msg = f"collection called {', '.join(refused)}: {RULE} (#286)"
        raise pytest.UsageError(msg)


def pytest_collection_finish() -> None:
    refuse_collected(take_refused())


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item: pytest.Item) -> Generator[None, object, object]:
    _armed[0] = armed_for(marker.name for marker in item.iter_markers())
    try:
        return (yield)
    finally:
        _armed[0] = True


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport() -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    fail_swallowed(report, take_refused())
    return report
