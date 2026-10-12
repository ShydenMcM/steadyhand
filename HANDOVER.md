# Handover: steadyhand

**Updated:** 2026-10-12 14:19 WIB (07:19 UTC). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: green, default branch; read its head with `git rev-parse origin/develop` (`bb0d827`, #305, at writing). Run 38216374131 passed every job, including deploy-dev with its attestation verified. Merge green PRs into `develop` without asking; never `main`.
- **`282-unit-tests-under-1s`**: pushed, no PR, head `5edf543`. It has not yet taken in develop.
- The local branches `302-measure-throwaway` and `302-freeze-gc` are merged or closed; delete them only after checking each tip against its PR head.

## Done this session: #302 closed (Done on the board)
- **Cause:** full garbage collections (generation 2), each landing on whichever test was running. Shown on CI by switching them off and on; the figures are on #302.
- **Fix, Shyden's choice:** `gc.collect()` + `gc.freeze()` in `tests/conftest.py`'s `pytest_collection_finish`, plus `tests/meta/test_gc_frozen.py`, which goes red without it. Merged as PR #305. On the laptop the suite now takes 38 s, down from 72 s.
- **Global rule, Shyden's choice:** every Python project does this. It is in `~/.claude/CLAUDE.md`, with evidence in `reference-engineering-standards.md`.
- **#292's list, corrected:**
  - the BBRI 2014 whole-history pin stays;
  - three tests came off: the BBRI 2017-2022 pin, `..._proves_one_factor_up_to_its_rights_issue` and `test_a_look_back_is_fetched_once_without_its_prices`;
  - golden years was added: 106-114 ms on py3.13 once frozen.

## Resume steps
1. Run `ListAgents`; no subagents were started.
2. Next is **#285** (8): the guards suite and the load limit. Read `~/.claude/global-rules/reference-guard-forms-and-floors.md` first. Move it to In Progress and branch from `origin/develop`.
3. Then #286, #290, #292, and #282's limit last.

## Clean-up queue (Shyden: "Cleanup first, every project"), all before #222
- **#282** In Progress, 13. Left to do:
  - merge develop in, then measure `test_cli_seed[BBRI]` on CI;
  - `test_journeys`, with #286;
  - then the 1 s limit, the CPU check and the guard in ONE push, after #302, #285, #286, #290 and #292. Add the CPU constant to `CPU_LIMITS` in `~/.claude/hooks/unit-limit-never-raised.py`.
- **#292** (8): 52 long real runs move to `integration`, plus the BBRI 2014 whole-history pin and golden years (#302).
  - A moved pin keeps its recording checked on every PR.
  - Moved CLI tests need a cold source.
- **#285** (8), **#286** (5, creates `integration`), **#290** (5, properties at 500), **#287** (3, Node 26), **#288** (3, mutations in CI), **#272** (5, Python floors).

## Raised with Shyden, not filed (outside this repo or his call)
- `hooks/test-isolation.py` cannot see a test run inside a script, and it wraps any command whose text contains "pytest".
- `hooks/push-onto-running-ci.py` fails closed when pushing from a worktree under `.superpowers/`.
- `hooks/disguised-waits.py` read `tail -1; gh project item-edit ... --field-id` as `tail -f` and refused it. That is a false positive, from a `-f` later on the same line.

## Progress (2026-10-12 07:19 UTC, `uv run --locked python .superpowers/sdd/estimates/progress.py`)
- **Measured:** EXT first release 4 of 28 stories closed. Whole board open: 33 tickets, 213 points (epic #214 unscored, 32 scored). Closed in the last 7 days: 10 tickets, 38 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-04, low confidence:** 32 open scored tickets at 1.43 a day is 23 days.
- **By effort: 213 points remaining. ETA 2026-11-21, low confidence:** 213 points at 5.4 a day is 40 days.
- **Assumed:** the last 7 days' pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review.
