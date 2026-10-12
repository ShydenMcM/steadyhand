# Handover: steadyhand

**Updated:** 2026-10-12 09:25 WIB (02:25 UTC). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: green; read its head with `git rev-parse origin/develop`. Default branch. Merge green PRs into `develop` without asking; never `main`.
- **`282-unit-tests-under-1s`**: pushed, no PR yet. Head `5edf543` (check it with `git rev-parse origin/282-unit-tests-under-1s`); develop is merged in. Five cuts so far, each green and mutation-verified (`.superpowers/sdd/282/evidence.md`):
  1. the yahoo waits (`61d35f6`);
  2. two deepcopy cuts (`655ff5a`, `bb5e507`);
  3. **the warm-cache seed** (`1b91387`): `scripts/record_cli_seed.py` writes `tests/fixtures/cache/cli-seed.sql`, `recorded_source` copies it into a folder with no cache, and `tests/cli/test_cli_seed.py` checks each of the 45 codes against a fresh fill;
  4. **the long-ledger cut** (`5edf543`): 0.50 s to 0.02 s.

## Decided by Shyden (2026-10-12): speed up BBRI's proof, filed as #296
- BBRI's whole-history restoration proof (`factor.find_runs`, which calls `nearest` 19,108 times) is the shared cost behind the four `test_yahoo` cuts, the two `test_cache` cuts and `test_cli_seed[BBRI]`. CI runs these tests at 0.095 to 0.228 s.
- The choice was to move those real runs to `integration`, or to make the proof faster. Shyden: *"Speed up the proof"*. **#296** (Estimate 5, on the board, read back) has 5 ACs:
  1. exactly the same runs on every recording, pinned as literals from `5edf543` before the change;
  2. each test at or under 0.07 s on the laptop and on CI;
  3. no caching and no narrowing;
  4. mutations caught before and after;
  5. coverage and mypy clean.

## Clean-up queue (Shyden: "Cleanup first, every project"), all before #222
Order: #296 (it unblocks #282's last cuts), then #285, #286, #290, #292, and #282's limit last. #282's cuts go on in parallel. #287 and #288 can go at any point.
- **#282** In Progress, 13 points. AC 5 was reworded today: the seed is kept in git, not built per session (built in the session it costs 0.12 s of CPU, charged to the first test). Evidence is posted on #282. Left to do:
  - the yahoo and cache cuts, through #296;
  - `test_journeys` (it starts a process, so it goes with #286);
  - then the 1 s limit, the CPU check and the guard, all in ONE push, after #285, #286, #290 and #292. The CPU constant also goes into `CPU_LIMITS` in `~/.claude/hooks/unit-limit-never-raised.py`.
- **#292** (8 points): 52 long real runs move to `integration`. **Since the seed, no CLI test runs a whole command through a real first download** (noted on #292). Its moved tests need a cold source (`seeded=False`, or a cold factory) and a check that the fill really ran. It is worth landing soon after #286.
- The rest of the queue: **#285** (8) guards suite and load limit; **#286** (5) no process or socket, and it creates `integration`; **#290** (5) properties suite at 500; **#287** (3) Node 26; **#288** (3) mutations in CI; **#272** (5) Python floors.

## Measured this session
- Probe after the seed, laptop, no coverage, every test recorded (`.superpowers/sdd/282/probe-after.jsonl`):
  - tests over 0.07 s fell from 139 to **91**, and CLI tests from 77 to **32**;
  - total test CPU fell from 67.3 s to 55.0 s;
  - 70 CLI tests were cut. AC 7 holds for all 70: W2 (65 tests) and W5 to W9 (5 tests) are red before and after.
- Covered gate on `1b91387`: 2,429 passed, 100% branch coverage, mypy clean.
- One prediction was wrong (W1): the look-back's actions fetch also stores BBRI's restoration, so no CLI test caught a `_fill` that drops it, even before the cut.

## Resume steps
1. Run `ListAgents` (no subagents were started this session).
2. The before-tree worktree `.superpowers/sdd/282/before` (at `1641188`) can be removed: `git worktree remove .superpowers/sdd/282/before`.
3. **Start #296**: move it to In Progress and branch from `origin/develop`. First pin every recording's `find_runs` output as literals from `5edf543` (AC 1), then profile (`.superpowers/sdd/282/prof_bbri.py`, run with `PYTHONPATH=scripts:tests/cli`), cut, and measure.

## Progress (2026-10-12 02:25 UTC, `.superpowers/sdd/estimates/progress.py`; nothing closed since 00:47; #296 filed)
- **Measured:** EXT first release 4 of 28 stories, 21 of 184 points. Whole board open: 34 tickets, 218 points (#296 added) (epic #214 unscored). Closed in the last 7 days: 8 tickets, 30 points.
- **By tickets: 14% (4 of 28). ETA 2026-11-10, low confidence:** 33 open tickets at 1.14 a day is 29 days.
- **By effort: 11% (21 of 184). ETA 2026-12-02, low confidence:** 218 open points at 4.3 a day is 51 days.
- **Assumed:** the last 7 days' pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review.

## Standing notes
- claude-mem cannot save memories (provider allowance exhausted, since 2026-10-12 00:47 UTC).
