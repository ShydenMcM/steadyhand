"""Two ``paper run --catch-up`` processes started together run each day exactly once (M5 spec
§9.1), each a real process racing the other for the store's lock (moved out of unit by #286).

No join has a timeout of its own: the integration step's limit bounds a hang (#286 AC3). The unit
suite keeps the logic's stand-in, in-process: a run that finds days another run saved meanwhile
leaves them to it (``tests/cli/test_paper_run.py``,
``test_days_another_run_saves_meanwhile_are_left_to_it``)."""

import multiprocessing
from pathlib import Path

from cli_world import at, opened, paper, paper_process, run_on, tables, trading_days
from record_golden import START


def test_two_runs_started_together_run_each_day_exactly_once(tmp_path: Path) -> None:
    together = paper(tmp_path / "together")
    alone = paper(tmp_path / "alone")
    for cli in (together, alone):
        run_on(cli, START)
    target = at(trading_days()[8])
    assert run_on(alone, trading_days()[8]).code == 0
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    processes = [
        context.Process(target=paper_process, args=(str(together.home), target.isoformat(), start))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join()
    assert [process.exitcode for process in processes] == [0, 0]
    assert tables(together) == tables(alone)
    with opened(together) as store:
        assert store.days() == trading_days()[:9]
        assert len(store.runs()) == 3
