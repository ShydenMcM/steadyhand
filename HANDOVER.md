# Handover: steadyhand

**Updated:** 2026-10-12 10:49 WIB (03:49 UTC). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: green; read its head with `git rev-parse origin/develop`. Default branch. Merge green PRs into `develop` without asking; never `main`.
- **`296-faster-restoring`**: **PR #299**, head `1658039` (check `git rev-parse origin/296-faster-restoring`). Local gate green on that head: 2,427 passed, 100% branch, ruff, format, mypy. Its CI was running at handover.
- **`296-measure-throwaway`**: draft **PR #298**, never merge. It probes the whole unit suite on CI, three runs on the new code and three on the old (`c855a1f`'s `factor.py`, `yahoo.py`, `types.py` swapped in), alternated in one job. Close it unmerged once read; delete its branch then.
- **`282-unit-tests-under-1s`**: pushed, no PR, head `5edf543`.

## #296 (In Progress, 5): done, waiting on CI
Session files: `.superpowers/sdd/296/` (git-ignored); evidence in `evidence.md`.
- AC 1: `tests/idx/test_yahoo_answers.py` pins all 14 Yahoo recordings (runs, refusals, bars, actions) from `c855a1f`. The pins restore a year at a time on cut histories (Shyden: speed the pins up first).
- AC 3: `DayGrid` is looked up once per row; `candidates` tries only tick multiples (checked against a rupiah-by-rupiah search); `restore_prices`; rows are judged whole in one call; `Bar` builds no error text when valid. No caching.
- AC 4: #160's 15 `factor.py` mutants were PREDICTED on both trees, with nothing caught before lost after. 13 new mutants: 11 PREDICTED; N3 red in 6; N9 survived, so a tolerance test was added and now catches it.
- AC 2 so far (alternated, min..max ms of own CPU):
  - targets-only CI: BBRI whole pin 99..108 → 51..68; golden years 76..107 → 49..68;
  - laptop: BBRI whole pin 110..150 → 47..55; golden years 87..138 → 44..61.
  - Every target test is under 70 ms in its worst run on both. The rule judges the whole-suite context, which roughly doubled these tests before, hence PR #298.

## Resume steps
1. Run `ListAgents`. The waiter `wait-run.sh` on run 38201143974 (#299), then on 38201171089 (#298), died with the session; re-run them:
   `~/.claude/scripts/wait-run.sh $PWD <run-id> .superpowers/sdd/296/pr.sha` (for #298, `throwaway.sha`).
2. #298: `gh run view <id> --log | grep PROBE > .superpowers/sdd/296/ci-298c-probe.log`. Then point `ci_summary.py`'s input at that file and run it.
   - Any target test over 0.07 s in its worst run: list it on #292 with its figures (AC 2).
   - Post the before/after table on #296.
   - Close #298 unmerged.
3. #299: merge when CI is green on its head (steps by name, SHA = `headRefOid`), then verify the develop deploy. Close #296 by hand once verified, reading its state first.
4. `test_cli_seed[BBRI]` (on #282's branch only) is still unmeasured: measure it after #282 merges develop.
5. Then the queue: #285, #286, #290, #292, and #282's limit last.

## Clean-up queue (Shyden: "Cleanup first, every project"), all before #222
- **#282** In Progress, 13: left to do are `test_journeys` (with #286), then the 1 s limit, the CPU check and the guard in ONE push, after #285, #286, #290 and #292; add the CPU constant to `CPU_LIMITS` in `~/.claude/hooks/unit-limit-never-raised.py`.
- **#292** (8): 52 long real runs move to `integration`, plus whatever #296 lists.
- **#285** (8) guards suite and load limit; **#286** (5) no process or socket, creates `integration`; **#290** (5) properties suite at 500; **#287** (3) Node 26; **#288** (3) mutations in CI; **#272** (5) Python floors.

## Raised with Shyden, not filed (outside this repo or his call)
- `hooks/test-isolation.py` cannot see a test run inside a script. The #296 timing scripts now take the lock themselves, and the Python runners refuse to start without `TEST_LOCK_HELD`.
- `hooks/push-onto-running-ci.py` fails closed when pushing from a worktree under `.superpowers/` (its `gh run list` exits 1 there). Pushing from the main checkout works.
- One-off CPU spikes (21 → 72 ms) look like garbage-collection pauses. A suite-wide `gc.freeze()` could be its own story: his call.

## Progress (2026-10-12 03:48 UTC, `uv run python .superpowers/sdd/estimates/progress.py`)
- **Measured:** EXT first release 4 of 28 stories, 21 of 184 points. Whole board open: 34 tickets, 218 points (epic #214 unscored). Closed in the last 7 days: 8 tickets, 30 points.
- **By tickets: 14% (4 of 28). ETA 2026-11-10, low confidence:** 33 open tickets at 1.14 a day is 29 days.
- **By effort: 11% (21 of 184). ETA 2026-12-02, low confidence:** 218 open points at 4.3 a day is 51 days.
- **Assumed:** the last 7 days' pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review.
