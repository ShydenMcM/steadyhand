# Handover: steadyhand

**Updated:** 2026-10-12 11:10 WIB (04:10 UTC). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: green; read its head with `git rev-parse origin/develop` (`10a7ce7` at writing, #299). Default branch. Merge green PRs into `develop` without asking; never `main`.
- **`282-unit-tests-under-1s`**: pushed, no PR, head `5edf543`. It has not yet taken in develop (#299's faster restoring step).
- Nothing else open: `296-faster-restoring` and `296-measure-throwaway` are deleted, and both #296 worktrees are removed.

## Done this session: #296 closed (Done on the board)
- PR #299 merged as `10a7ce7`. develop's CI passed on it, including deploy-dev (zip built, attested, attestation verified).
- The AC 2 before/after table is posted on #296. The whole-suite CI probe ran on throwaway PR #298, now closed unmerged.
- **Four tests are still over 0.07 s in their worst CI run.** They are listed on #292 to move to `integration`:
  - the BBRI whole-history pin;
  - the BBRI 2017-01-31_2022-01-31 pin;
  - `test_bbri_s_whole_recording_proves_one_factor_up_to_its_rights_issue`;
  - `test_a_look_back_is_fetched_once_without_its_prices`.
- Only the first pin is near the line in every run. The other three are under 40 ms at their fastest and went over in a single run. The cause of that jump is not measured.
- `test_cli_seed[BBRI]` was not measured, because it lives on #282's branch. That is noted on #282: measure it on CI once the branch takes in develop.

## Resume steps
1. Run `ListAgents` (no subagents were started this session).
2. Next in the queue is **#285** (8): the guards suite and the load limit. Move it to In Progress and branch from `origin/develop`. Read the ticket's ACs and `~/.claude/global-rules/reference-guard-forms-and-floors.md` first.
3. Then #286, #290, #292, and #282's limit last.

## Clean-up queue (Shyden: "Cleanup first, every project"), all before #222
- **#282** In Progress, 13. Left to do:
  - merge develop in, then measure `test_cli_seed[BBRI]` on CI;
  - `test_journeys`, together with #286;
  - then the 1 s limit, the CPU check and the guard in ONE push, after #285, #286, #290 and #292. Add the CPU constant to `CPU_LIMITS` in `~/.claude/hooks/unit-limit-never-raised.py`.
- **#292** (8): 52 long real runs move to `integration`, plus #296's four.
  - A moved pin still needs its recording checked on every PR.
  - `test_every_recording_has_its_answers_pinned` keeps requiring a pin for each recording.
  - Since the seed, its moved CLI tests need a cold source.
- **#285** (8): the guards suite and the load limit. **#286** (5): no process or socket; it creates `integration`. **#290** (5): the properties suite at 500. **#287** (3): Node 26. **#288** (3): mutations in CI. **#272** (5): Python floors.

## Raised with Shyden, not filed (outside this repo or his call)
- `hooks/test-isolation.py` cannot see a test run inside a script, so the timing scripts take the lock themselves. It also wraps any command whose text merely contains "pytest", such as a Python heredoc that edits a comment; use the Edit tool for those.
- `hooks/push-onto-running-ci.py` fails closed when pushing from a worktree under `.superpowers/`. Pushing from the main checkout works.
- One-off CPU spikes look like garbage-collection pauses (unmeasured). A suite-wide `gc.freeze()` could be its own story: his call.

## Progress (2026-10-12 04:09 UTC, `uv run python .superpowers/sdd/estimates/progress.py`)
- **Measured:** EXT first release 4 of 28 stories, 21 of 184 points. Whole board open: 33 tickets, 213 points (epic #214 unscored). Closed in the last 7 days: 9 tickets, 35 points.
- **By tickets: 14% (4 of 28). ETA 2026-11-06, low confidence:** 32 open scored tickets at 1.29 a day is 25 days.
- **By effort: 11% (21 of 184). ETA 2026-11-24, low confidence:** 213 open points at 5.0 a day is 43 days.
- **Assumed:** the last 7 days' pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review.
