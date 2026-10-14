# Handover: steadyhand

**Updated:** 2026-10-14 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: `23777d0` (#282's PR #325, squash): PR run 38506037431 green on all 14 required jobs at head `bdd2ff4`; develop's own run 38506385859 green on all 15 jobs, `deploy-dev` verified `steadyhand-extension-23777d0….zip`. Read the head with `git rev-parse origin/develop`. Required checks: 14. Merge green PRs into `develop` without asking; never `main`.
- No other branches or worktrees. Throwaway PR #324 (CI measurement) closed unmerged, branch deleted.

## #282: merged (PR #325), open, blocked by #288, as #292 is
- Split 2026-10-14: the enforcement went to **#323** (8). #282 is 5: the cuts. Every unit test is at or under 0.07 s of own CPU in its heaviest run: laptop three runs (load 9 to 18) and CI (#324, one run per Python), zero over; heaviest on CI 0.063 s. Unit 2,273, coverage 100% on 3.12 and 3.13.
- `catalogue()` loads once per process; three tests moved to integration with stand-ins (paper journey, 31 days with catch-up, old prices). AC 7: 9 of 9 mutations as predicted (`.superpowers/sdd/282/mut_282.py`, git-ignored). Open only for the moved tests' integration mutations, run by #288's workflow; `blocked_by: [288]`, linked; Todo.
- Tools kept in `.superpowers/sdd/unit-1s/`: `probe.py` (per-test CPU plugin), `worst_of_runs.py` (worst CPU across runs); `.superpowers/sdd/282/measure_ci.py` adds a throwaway CI probe step (add `|| true` per run: GitHub's `bash -e` stopped after the first run on #324).

## #292: merged, open, blocked by #288 (Shyden 2026-10-13: "keep open")
- 89 long real runs in `tests/integration/{idx,cli,golden}` with unit stand-ins over `tests/cli/short_world.py`. Open only for AC 3's integration half: 30 mutations in `.superpowers/sdd/292/` (git-ignored), run by #288's workflow.

## Done today (2026-10-14)
- **#319** closed: README "Dev builds" section (PR #321). Shyden re-ruled the dev-deploy rule **"Rule met, say how"** after measuring that `ci.yml`'s `deploy-dev` job already deploys each green develop push. Filed **#320** (2): README still describes a library and CLI.
- PR-on-red hook: all 14 required checks are `ci.yml` jobs; nothing to change here.

## Resume steps
1. Run `ListAgents`; no subagents were started.
2. If this file's docs PR (`docs-handover-282`) is still open, read its run by job name and merge it when green.
3. Next: **#323** (8, the unit-limit enforcement: top of the queue by the global 1 s rule; now unblocked). Then #288 (unblocks #282 and #292).

## Next on the clean-up queue (all before #222)
- **#323** (8, enforcement), **#287** (3, Node 26), **#288** (5, mutations in CI, with #282's and #292's), **#272** (5, Python floors), **#315** (2, board Priority, blocked by repo-template#6), **#317** (5, orphan check in the PR gate), **#320** (2, README for the extension direction).

## Raised with Shyden
- Three global hook false positives, for a dedicated `~/.claude` session (his choice, 2026-10-12): `~/.claude/hook-false-positives-2026-10-13.md`.

## Progress (2026-10-14, `uv run --locked python .superpowers/sdd/estimates/progress.py`)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points). Board open: 35 tickets, 207 points (epic #214 unscored). Closed 2026-10-07 to 2026-10-14: 6 tickets, 27 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-23, low confidence:** 34 open scored tickets at 0.86 a day is 40 days.
- **By effort: 207 points remaining across 34 scored open tickets. ETA 2026-12-07, low confidence:** 3.9 points a day is 54 days.
- **Assumed:** last week's pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315.
