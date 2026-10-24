"""A unit test starts no process and opens no outside connection (#286).

The entry points and the plants are written out here by hand, never read from the plugin's own
list: a plant generated from that list could not see it drop one (the guard-forms catalogue, #446).
A plant only runs once every entry point is seen wrapped, so a run with a wrapper taken out fails
before anything could really start a process.
"""

import _posixsubprocess
import multiprocessing
import multiprocessing.process
import os
import re
import socket
import subprocess
import urllib.request
from collections.abc import Callable, Sequence
from types import SimpleNamespace

import no_process
import pytest
from no_process import UnitRuleError, armed_for, take_refused

ENTRY_POINTS: list[tuple[str, object, str]] = [
    ("subprocess.Popen", subprocess.Popen, "_execute_child"),
    ("subprocess._fork_exec", subprocess, "_fork_exec"),
    ("_posixsubprocess.fork_exec", _posixsubprocess, "fork_exec"),
    ("multiprocessing start", multiprocessing.process.BaseProcess, "start"),
    ("os.fork", os, "fork"),
    ("os.forkpty", os, "forkpty"),
    ("os.posix_spawn", os, "posix_spawn"),
    ("os.posix_spawnp", os, "posix_spawnp"),
    ("os.system", os, "system"),
    ("os.popen", os, "popen"),
    ("os.execv", os, "execv"),
    ("os.execve", os, "execve"),
    ("os.execl", os, "execl"),
    ("os.execle", os, "execle"),
    ("os.execlp", os, "execlp"),
    ("os.execlpe", os, "execlpe"),
    ("os.execvp", os, "execvp"),
    ("os.execvpe", os, "execvpe"),
    ("os.spawnv", os, "spawnv"),
    ("os.spawnve", os, "spawnve"),
    ("os.spawnvp", os, "spawnvp"),
    ("os.spawnvpe", os, "spawnvpe"),
    ("os.spawnl", os, "spawnl"),
    ("os.spawnle", os, "spawnle"),
    ("os.spawnlp", os, "spawnlp"),
    ("os.spawnlpe", os, "spawnlpe"),
    ("socket.connect", socket.socket, "connect"),
    ("socket.connect_ex", socket.socket, "connect_ex"),
    ("socket.getaddrinfo", socket, "getaddrinfo"),
    ("socket.gethostbyname", socket, "gethostbyname"),
    ("socket.gethostbyname_ex", socket, "gethostbyname_ex"),
    ("socket.gethostbyaddr", socket, "gethostbyaddr"),
    ("socket.getnameinfo", socket, "getnameinfo"),
]


@pytest.mark.parametrize(
    ("label", "owner", "name"), ENTRY_POINTS, ids=[label for label, _, _ in ENTRY_POINTS]
)
def test_this_unit_run_refuses_each_entry_point(label: str, owner: object, name: str) -> None:
    assert getattr(getattr(owner, name), "__refuses__", None) == label


def test_the_plugin_is_registered_in_this_unit_run(request: pytest.FixtureRequest) -> None:
    assert request.config.pluginmanager.get_plugin("no-process") is no_process


def unready(armed: list[bool], entry_points: Sequence[tuple[str, object, str]]) -> list[str]:
    """Why no plant may run: the refusal unarmed, or an entry point no longer wrapped."""
    problems = [] if armed == [True] else ["the refusal is not armed, so no plant runs"]
    unwrapped = [
        label
        for label, owner, name in entry_points
        if getattr(getattr(owner, name), "__refuses__", None) != label
    ]
    if unwrapped:
        problems.append(f"not wrapped, so no plant runs: {', '.join(unwrapped)}")
    return problems


@pytest.fixture
def every_entry_point_wrapped() -> None:
    """Fail before a plant runs unless every entry point is wrapped, so that taking a wrapper
    out, or leaving it unarmed (a mutation), can never let a plant start a real process or reach
    the network."""
    problems = unready(no_process._armed, ENTRY_POINTS)
    assert problems == [], problems


def test_an_unarmed_refusal_lets_no_plant_run() -> None:
    assert unready([False], []) == ["the refusal is not armed, so no plant runs"]


def test_an_entry_point_left_unwrapped_lets_no_plant_run() -> None:
    bare = SimpleNamespace(run=lambda: None)
    assert unready([True], [("bare.run", bare, "run")]) == [
        "not wrapped, so no plant runs: bare.run"
    ]


def test_a_disarmed_wrapper_calls_through_to_the_original() -> None:
    """Outside a unit test's own body (collection, teardown) the wrapper must not refuse."""
    wrapped = no_process._refusing("plain", lambda value: value * 2)
    no_process._armed[0] = False
    try:
        assert wrapped(21) == 42
    finally:
        no_process._armed[0] = True


def connect() -> None:
    with socket.socket() as sock:
        sock.connect(("127.0.0.1", 9))


def connect_ex() -> None:
    with socket.socket() as sock:
        sock.connect_ex(("127.0.0.1", 9))


def spawn_a_process() -> None:
    multiprocessing.get_context("spawn").Process(target=print).start()


def fork_a_process() -> None:
    multiprocessing.get_context("fork").Process(target=print).start()


TRUE = "/usr/bin/true"

PLANTS: list[tuple[str, str, Callable[[], object]]] = [
    ("subprocess-run", "subprocess.Popen", lambda: subprocess.run([TRUE], check=False)),
    ("subprocess-check-output", "subprocess.Popen", lambda: subprocess.check_output([TRUE])),
    ("subprocess-popen", "subprocess.Popen", lambda: subprocess.Popen([TRUE])),
    ("subprocess-fork-exec", "subprocess._fork_exec", lambda: subprocess._fork_exec()),  # type: ignore[attr-defined]  # noqa: PLW0108 - read at call time
    ("posixsubprocess", "_posixsubprocess.fork_exec", lambda: _posixsubprocess.fork_exec()),  # type: ignore[call-arg]  # noqa: PLW0108 - read at call time
    ("multiprocessing-spawn", "multiprocessing start", spawn_a_process),
    ("multiprocessing-fork", "multiprocessing start", fork_a_process),
    ("fork", "os.fork", os.fork),
    ("forkpty", "os.forkpty", os.forkpty),
    ("posix-spawn", "os.posix_spawn", lambda: os.posix_spawn(TRUE, [TRUE], {})),
    ("posix-spawnp", "os.posix_spawnp", lambda: os.posix_spawnp("true", ["true"], {})),
    ("system", "os.system", lambda: os.system(TRUE)),
    ("popen", "os.popen", lambda: os.popen(TRUE)),
    ("execv", "os.execv", lambda: os.execv(TRUE, [TRUE])),
    ("execve", "os.execve", lambda: os.execve(TRUE, [TRUE], {})),
    ("execl", "os.execl", lambda: os.execl(TRUE, TRUE)),
    ("execle", "os.execle", lambda: os.execle(TRUE, TRUE, {})),
    ("execlp", "os.execlp", lambda: os.execlp("true", "true")),
    ("execlpe", "os.execlpe", lambda: os.execlpe("true", "true", {})),
    ("execvp", "os.execvp", lambda: os.execvp("true", ["true"])),
    ("execvpe", "os.execvpe", lambda: os.execvpe("true", ["true"], {})),
    ("spawnv", "os.spawnv", lambda: os.spawnv(os.P_WAIT, TRUE, [TRUE])),
    ("spawnve", "os.spawnve", lambda: os.spawnve(os.P_WAIT, TRUE, [TRUE], {})),
    ("spawnvp", "os.spawnvp", lambda: os.spawnvp(os.P_WAIT, "true", ["true"])),
    ("spawnvpe", "os.spawnvpe", lambda: os.spawnvpe(os.P_WAIT, "true", ["true"], {})),
    ("spawnl", "os.spawnl", lambda: os.spawnl(os.P_WAIT, TRUE, TRUE)),
    ("spawnle", "os.spawnle", lambda: os.spawnle(os.P_WAIT, TRUE, TRUE, {})),
    ("spawnlp", "os.spawnlp", lambda: os.spawnlp(os.P_WAIT, "true", "true")),
    ("spawnlpe", "os.spawnlpe", lambda: os.spawnlpe(os.P_WAIT, "true", "true", {})),
    ("connect", "socket.connect", connect),
    ("connect-ex", "socket.connect_ex", connect_ex),
    ("getaddrinfo", "socket.getaddrinfo", lambda: socket.getaddrinfo("example.com", 80)),
    ("create-connection", "socket.getaddrinfo", lambda: socket.create_connection(("x.test", 80))),
    ("urlopen", "socket.getaddrinfo", lambda: urllib.request.urlopen("http://x.test/")),
    ("gethostbyname", "socket.gethostbyname", lambda: socket.gethostbyname("example.com")),
    ("gethostbyname-ex", "socket.gethostbyname_ex", lambda: socket.gethostbyname_ex("x.test")),
    ("gethostbyaddr", "socket.gethostbyaddr", lambda: socket.gethostbyaddr("127.0.0.1")),
    ("getnameinfo", "socket.getnameinfo", lambda: socket.getnameinfo(("127.0.0.1", 80), 0)),
]


@pytest.mark.usefixtures("every_entry_point_wrapped")
@pytest.mark.parametrize(
    ("label", "plant"),
    [(label, plant) for _, label, plant in PLANTS],
    ids=[i for i, _, _ in PLANTS],
)
def test_a_planted_call_is_refused_by_name(label: str, plant: Callable[[], object]) -> None:
    with pytest.raises(UnitRuleError, match=f"^{re.escape(label)} was called: "):
        plant()
    assert take_refused() == [label]


@pytest.mark.usefixtures("every_entry_point_wrapped")
def test_the_refusal_says_what_to_do_instead() -> None:
    with pytest.raises(UnitRuleError) as refused:
        os.system(TRUE)
    take_refused()
    assert str(refused.value) == (
        "os.system was called: a unit test starts no process and opens no outside connection "
        "(#286). Call the code in-process with the process stood in, or move the real case to "
        "tests/integration and keep a stand-in of its logic here."
    )


@pytest.mark.parametrize(
    ("markers", "armed"),
    [
        pytest.param([], True, id="no-marker"),
        pytest.param(["parametrize"], True, id="parametrized"),
        pytest.param(["last"], True, id="last"),
        pytest.param(["perf"], False, id="perf"),
        pytest.param(["live"], False, id="live"),
        pytest.param(["parametrize", "perf"], False, id="perf-among-others"),
    ],
)
def test_a_perf_or_live_test_is_another_suite_and_runs_unarmed(
    markers: list[str], *, armed: bool
) -> None:
    assert armed_for(markers) is armed


def report(outcome: str) -> SimpleNamespace:
    return SimpleNamespace(outcome=outcome, longrepr=None, passed=outcome == "passed")


def test_a_refusal_the_test_swallowed_still_fails_it_by_name() -> None:
    swallowed = report("passed")
    no_process.fail_swallowed(swallowed, ["os.fork", "socket.connect"])  # type: ignore[arg-type]
    assert (swallowed.outcome, swallowed.longrepr) == (
        "failed",
        (
            "refused, and the test carried on as if nothing happened: os.fork, socket.connect "
            "(a unit test starts no process and opens no outside connection, #286)"
        ),
    )


@pytest.mark.parametrize("outcome", ["failed", "skipped"])
def test_a_test_that_did_not_pass_keeps_its_own_report(outcome: str) -> None:
    kept = report(outcome)
    no_process.fail_swallowed(kept, ["os.fork"])  # type: ignore[arg-type]
    assert (kept.outcome, kept.longrepr) == (outcome, None)


def test_collection_that_called_nothing_carries_on() -> None:
    no_process.refuse_collected([])


def test_a_refusal_during_collection_stops_the_run_by_name() -> None:
    with pytest.raises(pytest.UsageError, match=r"^collection called os\.fork, os\.system: "):
        no_process.refuse_collected(["os.fork", "os.system"])


def test_installing_arms_the_refusal_for_collection() -> None:
    no_process._armed[0] = False  # install puts it back, or this test fails
    no_process.install()
    assert no_process._armed == [True]


def marked(*names: str) -> SimpleNamespace:
    return SimpleNamespace(iter_markers=lambda: [SimpleNamespace(name=name) for name in names])


@pytest.mark.parametrize(
    ("markers", "armed"),
    [pytest.param((), True, id="unit"), pytest.param(("perf",), False, id="perf")],
)
def test_the_protocol_hook_arms_by_marker_and_rearms_after(
    markers: tuple[str, ...], *, armed: bool
) -> None:
    hook = no_process.pytest_runtest_protocol(marked(*markers))  # type: ignore[arg-type]
    next(hook)
    during = list(no_process._armed)
    with pytest.raises(StopIteration):
        hook.send(None)
    assert (during, no_process._armed) == ([armed], [True])


def test_the_report_hook_fails_a_test_that_swallowed_a_refusal() -> None:
    no_process._refused.append("os.fork")  # as a refused call leaves it
    hook = no_process.pytest_runtest_makereport()
    next(hook)
    swallowed = report("passed")
    with pytest.raises(StopIteration) as finished:
        hook.send(swallowed)  # type: ignore[arg-type]
    assert finished.value.value is swallowed
    assert swallowed.outcome == "failed"
    assert take_refused() == []
