"""Measurement-only pytest plugin for #302 (throwaway, never merged): where one-off CPU jumps come from.

For each test, as one JSON line: wall, own THREAD CPU (time.thread_time, the global rule's figure),
the garbage collections that ran inside it (count and thread CPU per generation), and the modules
first imported inside it. For each test module, the same for importing and collecting it ("load").

PROBE_GC_FREEZE=1 runs gc.collect() then gc.freeze() once collection has finished: the controlled
run that switches the candidate off.
"""

import gc
import json
import os
import sys
import time

import pytest

OUT = os.environ["PROBE_OUT"]
FREEZE = os.environ.get("PROBE_GC_FREEZE") == "1"
_started: list[float] = []
_collections: dict[int, list[float]] = {0: [0, 0.0], 1: [0, 0.0], 2: [0, 0.0]}


def _on_gc(phase: str, info: dict[str, int]) -> None:
    if phase == "start":
        _started.append(time.thread_time())
    elif _started:
        spent = _collections[info["generation"]]
        spent[0] += 1
        spent[1] += time.thread_time() - _started.pop()


gc.callbacks.append(_on_gc)


def _gc_snapshot() -> dict[int, tuple[float, float]]:
    return {generation: (count, cpu) for generation, (count, cpu) in _collections.items()}


def _measure(record: dict[str, object]):  # type: ignore[no-untyped-def]
    modules0, gc0 = set(sys.modules), _gc_snapshot()
    wall0, cpu0 = time.perf_counter(), time.thread_time()
    yield
    cpu, wall = time.thread_time() - cpu0, time.perf_counter() - wall0
    gc1 = _gc_snapshot()
    record.update(
        wall=wall,
        cpu=cpu,
        gc={g: [gc1[g][0] - gc0[g][0], round(gc1[g][1] - gc0[g][1], 6)] for g in gc1 if gc1[g][0] != gc0[g][0]},
        imported=sorted(set(sys.modules) - modules0)[:20],
    )
    with open(OUT, "a", encoding="utf-8") as out:
        out.write(json.dumps(record) + "\n")


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):  # type: ignore[no-untyped-def]
    if not isinstance(collector, pytest.Module):
        yield
        return
    yield from _measure({"load": collector.nodeid})


def pytest_collection_finish(session):  # type: ignore[no-untyped-def]
    if FREEZE:
        gc.collect()
        gc.freeze()
    with open(OUT, "a", encoding="utf-8") as out:
        out.write(json.dumps({"collected": True, "freeze": FREEZE, "tracked": len(gc.get_objects()), "frozen": gc.get_freeze_count(), "threshold": gc.get_threshold()}) + "\n")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):  # type: ignore[no-untyped-def]
    yield from _measure({"id": item.nodeid})


def pytest_sessionfinish(session, exitstatus):  # type: ignore[no-untyped-def]
    with open(OUT, "a", encoding="utf-8") as out:
        out.write(json.dumps({"session": True, "exitstatus": int(exitstatus), "gc": _collections}) + "\n")
