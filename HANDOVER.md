# Handover: steadyhand

**Updated:** 2026-10-15 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: `f3b20dc` (#323's PR #327, squash; read with `git rev-parse origin/develop`). Develop's run 38699155092 green on all 15 jobs; `deploy-dev` attested and kept `steadyhand-extension-f3b20dc….zip`. Required checks: 14. Merge green PRs into `develop` without asking; never `main`.
- No other branches or worktrees: `323-unit-limits-enforced` merged, deleted remotely by GitHub, worktree and local branch removed (tip was the merged PR head).

## Done today (2026-10-15)
- **#323 closed** (PR #327): every unit test held to 1 s of wall and 0.1 s of own thread CPU in both runners, judged without coverage; two guards refuse any raised, set or hidden limit (21/21 mutations, 8/8 floor mutants as predicted); perf and live steps 2 minutes each. AC 3 amended (Shyden, "Literal now, #272 converts"): #272 now also converts the guard's five Python literal floors (166/165/93/799/157). Measured: heaviest own CPU on CI 66.7 ms (3.12), 57.5 ms (3.13), 13.0 ms (extension); posted on #323 and #282.
- CI found four defects that the laptop gate missed; all fixed in the PR. Memory `feedback-gate-runs-unit-with-and-without-cov` records the main lesson: run the unit suite plain AND under `--cov` before any push.
- Swagger rule (global, relayed by the shyden-co-uk session): steadyhand serves no API. Shyden: the extension's internal `chrome.runtime` messaging does not count. No stories filed; the peer was told.
- Session tools, git-ignored, in `.superpowers/sdd/323/`: `mut_323.py`, `mut_323_floors.py`, `tools/amend_chain.py` (chain rebuild for this layout), evidence in `evidence-task3.md`.

## Resume steps
1. Run `ListAgents`; no subagents were started.
2. If this file's docs PR (`docs-handover-323`) is still open, read its run by job name and merge it when green.
3. Next: **#288** (5, mutations in CI). It unblocks #282 and #292, which wait only on their integration-half mutations (`.superpowers/sdd/282/`, `.superpowers/sdd/292/`). Then #287 (Node 26).

## Next on the clean-up queue (all before #222)
- **#288** (5, mutations in CI, with #282's and #292's), **#287** (3, Node 26), **#272** (5, Python floors, including #323's five), **#315** (2, board Priority, blocked by repo-template#6), **#317** (5, orphan check in the PR gate), **#320** (2, README for the extension direction).

## Raised with Shyden
- Three global hook false positives, for a dedicated `~/.claude` session (his choice, 2026-10-12): `~/.claude/hook-false-positives-2026-10-13.md`.
- The test-lock hook treats a `python3 -` edit script that names a `.test.ts` path as a heavy test run (on 2026-10-15 one queued behind ShyTalk's jest run); edits went through the Edit tool instead.

## Progress (2026-10-15, `uv run --locked python .superpowers/sdd/estimates/progress.py`)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points). Board open: 34 tickets, 199 points (epic #214 unscored). Closed 2026-10-08 to 2026-10-15: 7 tickets, 35 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-17, low confidence:** 33 open scored tickets at 1.0 a day is 33 days.
- **By effort: 199 points remaining across 33 scored open tickets. ETA 2026-11-24, low confidence:** 5.0 points a day is 40 days.
- **Assumed:** last week's pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315.
