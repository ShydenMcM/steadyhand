# Handover: steadyhand

**Updated:** 2026-10-13 09:16 WIB (02:16 UTC). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: `0f32209` (#292's PR #316, squash): run 38335919831 green on every job, deploy-dev verified the zip's attestation. Read the head with `git rev-parse origin/develop`. Required checks: 14. Merge green PRs into `develop` without asking; never `main`.
- `282-unit-tests-under-1s`: pushed, no PR, head `5edf543`; it has not taken in develop (rebase it on `0f32209` first).

## #292: merged, open, blocked by #288 (Shyden 2026-10-13: "keep open")
- 89 long real runs now in `tests/integration/{idx,cli,golden}`, unchanged; a unit stand-in of each over `tests/cli/short_world.py` (made-up 19 days, 2021-12-15 to 2022-01-11; pinned runs in `tests/fixtures/golden/made-up`; paper page tests use `saved_account`). Evidence on #292 (comment of 02:15 UTC).
- Open only for AC 3's integration half: 30 mutations in `.superpowers/sdd/292/mut_cli.py` and `mut_paper_golden.py` (git-ignored; `integration_red` names the moved tests), run by #288's workflow. #292 is Todo, `blocked_by: [288]`, linked.
- The 12 borderline CLI tests are #282's (Shyden 2026-10-13).

## Resume steps
1. Run `ListAgents`; no subagents were started.
2. If this file's docs PR (`docs-handover-292`) is still open, read its run and merge it when green.
3. Next ticket from the queue below: #288 unblocks #292; #282 is the biggest. No Priority field yet (#315 blocked), so the order is the queue's.

## Next on the clean-up queue (all before #222)
- **#282** (13: warm cache, CPU check, now also the 12 borderline), **#287** (3, Node 26), **#288** (5, mutations in CI, now with #292's 30), **#272** (5, Python floors), **#315** (2, board Priority, blocked by repo-template#6), **#317** (5, orphan check in the PR gate).

## Raised with Shyden
- Three global hook false positives, for a dedicated `~/.claude` session (his choice, 2026-10-12): `~/.claude/hook-false-positives-2026-10-13.md`.

## Progress (2026-10-13 02:16 UTC, `uv run --locked python .superpowers/sdd/estimates/progress.py`)
- **Measured:** EXT first release 4 of 28 stories closed. Board open: 33 tickets, 205 points (epic #214 unscored). Closed since 2026-10-06: 9 tickets, 42 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-07, low confidence:** 32 open scored tickets at 1.29 a day is 25 days.
- **By effort: 205 points remaining across 32 scored open tickets. ETA 2026-11-16, low confidence:** 6.0 points a day is 34 days.
- **Assumed:** last week's pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315.
