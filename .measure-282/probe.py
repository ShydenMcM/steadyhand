"""Measurement-only pytest plugin (2026-10-12): per test and per module load, written as JSON lines.

For each test: wall, own THREAD CPU (time.thread_time, the global rule's figure), every process
it starts and every socket it connects or resolves. For each test module: the wall and thread CPU
of importing and collecting it ("load"), which no per-test limit sees.
"""

import json
import multiprocessing.util
import os
import socket
import subprocess
import time

import pytest

OUT = os.environ["PROBE_OUT"]
_current = ["(session)"]
_events: dict[str, list[dict[str, object]]] = {}


def _note(kind: str, detail: object) -> None:
    _events.setdefault(_current[0], []).append({"kind": kind, "detail": repr(detail)[:200]})


def _wrap(owner: object, name: str, kind: str, pick=lambda a, k: a) -> None:  # type: ignore[no-untyped-def]
    original = getattr(owner, name, None)
    if original is None:
        return

    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
        _note(kind, pick(args, kwargs))
        return original(*args, **kwargs)

    setattr(owner, name, wrapper)


_wrap(subprocess.Popen, "_execute_child", "process", lambda a, k: a[1] if len(a) > 1 else k)
for _name in ("fork", "forkpty", "posix_spawn", "posix_spawnp", "system"):
    _wrap(os, _name, "process", lambda a, k, n=_name: (n, a[:1]))
_wrap(multiprocessing.util, "spawnv_passfds", "process", lambda a, k: a[:2])
_wrap(socket.socket, "connect", "socket", lambda a, k: (a[0].family, a[1:]))
_wrap(socket.socket, "connect_ex", "socket", lambda a, k: (a[0].family, a[1:]))
_wrap(socket, "getaddrinfo", "resolve", lambda a, k: a[:2])


def _write(record: dict[str, object]) -> None:
    with open(OUT, "a", encoding="utf-8") as out:
        out.write(json.dumps(record) + "\n")


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):  # type: ignore[no-untyped-def]
    if not isinstance(collector, pytest.Module):
        yield
        return
    key = f"load:{collector.nodeid}"
    previous, _current[0] = _current[0], key
    wall0, cpu0 = time.perf_counter(), time.thread_time()
    yield
    _write(
        {
            "load": collector.nodeid,
            "wall": time.perf_counter() - wall0,
            "cpu": time.thread_time() - cpu0,
            "events": _events.pop(key, []),
        }
    )
    _current[0] = previous


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):  # type: ignore[no-untyped-def]
    previous, _current[0] = _current[0], item.nodeid
    wall0, cpu0 = time.perf_counter(), time.thread_time()
    yield
    _write(
        {
            "id": item.nodeid,
            "wall": time.perf_counter() - wall0,
            "cpu": time.thread_time() - cpu0,
            "events": _events.pop(item.nodeid, []),
        }
    )
    _current[0] = previous


def pytest_sessionfinish(session, exitstatus):  # type: ignore[no-untyped-def]
    _write({"session": True, "exitstatus": int(exitstatus), "events": _events.pop("(session)", [])})
