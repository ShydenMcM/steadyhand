# Handover: steadyhand

**Updated:** 2026-10-12 06:50 WIB (2026-10-11 23:50 UTC). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop` = `932167c`, green. Default branch. Merge green PRs into `develop` without asking; never `main`.
- **`282-unit-tests-under-1s`**, pushed, no PR yet, head `bb5e507` (read with `git rev-parse origin/282-unit-tests-under-1s`). Three cuts, each green and mutation-verified (`.superpowers/sdd/282/evidence.md`):
  - `61d35f6`: the four `test_yahoo` waits pass a recording `sleep`.
  - `655ff5a`: deepcopy at three times the recursion limit, 2.78 s down to 0.04 s.
  - `bb5e507`: a recursing deepcopy fails in one line. Before, pytest spent 129 to 469 s drawing the `RecursionError` traceback, profiled.

## Clean-up queue (Shyden: "Cleanup first, every project"), all before #222
Order: #285 → #286 → #290 → #282's limit last. #282's cuts go on in parallel. #287 and #288 can land at any point.
- **#282** In Progress, 13 points: 1 s runner limit in a new uncovered CI step, CPU check, a guard against raised limits, cuts. **Cut list = 37 non-property, non-process tests over 0.5 s on CI** (`.superpowers/sdd/unit-1s/cut-list.txt`); 5 done, **32 left**, mostly CLI and golden tests.
- **#285** (8): whole-repo guards (`tests/meta`, four extension guards) into a `guards` suite; a file-load limit (`workspace.test.ts` loads in 1.12 s); floors recorded by a CI job.
- **#286** (5): unit tests start no process and open no socket; `test_ci_scope`, `test_lock_fast_path`, `test_journeys`, `test_paper_run:625` and `build.test.ts` are rewritten or moved to `integration`.
- **#290** (5): **Shyden 2026-10-12, "Move them, keep 500":** every `@given` test moves to a CI `properties` suite at 500 examples; unit keeps a stand-in per property. Hypothesis alone costs 0.17 to 0.20 s per 500 trivial examples.
- **#287** (3) Node 26. **#288** (3) mutations of non-unit suites in a CI workflow. **#272** (5) Python floors.

## Measured this session (tools in `.superpowers/sdd/unit-1s/`, git-ignored)
- `probe.py` (pytest) and `probe.setup.ts` (vitest) record per-test thread CPU and wall, process starts, sockets and file loads. Both proved live on planted tests. `analyse_probe.py`, `ci_compare.py` and `ci_lists.py` summarise; CI logs and data are in `ci/`.
- CI, from throwaway PR #289 (closed, branch deleted): per-test CPU runs a median 1.10x / 1.20x the laptop's, worst 2.1x; the two jobs ran on different CPUs (Intel, AMD EPYC). Sockets: 0. Process starts: 62 Python tests, 5 extension tests.

## Resume steps
1. Run `ListAgents`; no subagents were started this session.
2. **#282 plan for the 32 cuts.** Profile (`$TMPDIR/cuts.prof` is gone; re-run the 32 ids from `cut-list.txt` under cProfile): about 80% is data loading. Each test starts with an empty SQLite `BarCache` in its own folder (`tests/cli/cli_world.py:143`), so it re-reads the recorded Yahoo files and re-proves the factors (`yahoo.py:445` `_runs_for` → `factor.find_runs`). The likely cut is a cache built once per session and copied into each test (the cache also stores restorations, `cache.py:103`). **First list which of the 32 test the cold-fetch path itself; those keep it.** Plan by extraction, reviewed to zero.
3. Every cut needs predicted mutations, caught before and after (AC 7); keep the probe's numbers for AC 9.
4. Then #285, #286, #290, and last #282's limit, CPU check and guard (ONE push). Add the CPU limit's constant name to `CPU_LIMITS` in `~/.claude/hooks/unit-limit-never-raised.py`.
5. **Clean-up loop is due** (session-start nudge): after #282, run `/loop` over `~/.claude/global-rules/reference/reference-cleanup.md` for this project, then `~/.claude/scripts/cleanup-done.sh steadyhand`. Stale worktrees noted: two `prunable` entries under the scratchpad (`git worktree prune`).

## Progress (2026-10-11 23:45 UTC, from `.superpowers/sdd/estimates/progress.py`, run with `uv run --no-project --python 3.12 python`)
- **Measured:** EXTENSION first release 4 of 28 stories closed, 21 of 184 points. Whole board open: 30 tickets, 200 points (only the epic #214 is unscored). Closed in the last 7 days: 8 tickets, 30 points.
- **By tickets: 14% (4 of 28 EXT). ETA 2026-11-07, low confidence.** 30 open tickets ahead (the clean-up queue first) at 1.14 a day is 26 days.
- **By effort: 11% (21 of 184 EXT points). ETA 2026-11-28, low confidence.** 200 open points at 4.3 a day is 47 days.
- **Assumed:** that the last 7 days' pace (mostly guards and test work) holds for the TypeScript feature stories. **Outside waits:** a broker account (EXT S16a #242) and Chrome Web Store review (days).

## Standing notes
- `~/.claude/CLAUDE.md` is over its size ceiling (34,568 against 33,730 bytes) from earlier edits; nothing was added this session. Shyden's property-test ruling is in `reference-engineering-standards.md` (backup `.bak-property-tests-2026-10-12`).
- claude-mem could not save memories this session (provider allowance exhausted since 2026-10-10 22:21 UTC).
