# Handover: steadyhand

**Updated:** 2026-10-14 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: `8cbe2e4` (#319's PR #321, squash): PR run 38499345783 green on all 14 required jobs; develop's own run 38499583309 green on all 15 jobs, `deploy-dev` verified `steadyhand-extension-8cbe2e4….zip`. Read the head with `git rev-parse origin/develop`. Required checks: 14. Merge green PRs into `develop` without asking; never `main`.
- `282-unit-tests-under-1s`: pushed, no PR, head `5edf543`; it has not taken in develop (rebase it on `0f32209` first).

## #319: closed, PR #321 merged: README says how develop deploys to dev (Shyden 2026-10-14)
- The shyden.co.uk session relayed "no deploy workflow" and Shyden ruled the new dev-deploy rule Not applicable. Measured: `ci.yml`'s `deploy-dev` job already deploys each green develop push (builds the extension, attests and verifies the zip, keeps it 90 days, the repo's retention). Re-asked: **"Rule met, say how"**. The peer was told.
- PR #321 adds a "Dev builds" README section. AC 4 corrected on #319: README is off the docs-only fast path (the disclaimer guard reads it), so full CI.
- Filed in passing: **#320** (2): the README still describes a library and CLI, not the #214 extension.

## #292: merged, open, blocked by #288 (Shyden 2026-10-13: "keep open")
- 89 long real runs now in `tests/integration/{idx,cli,golden}`, unchanged; a unit stand-in of each over `tests/cli/short_world.py` (made-up 19 days, 2021-12-15 to 2022-01-11; pinned runs in `tests/fixtures/golden/made-up`; paper page tests use `saved_account`). Evidence on #292 (comment of 02:15 UTC).
- Open only for AC 3's integration half: 30 mutations in `.superpowers/sdd/292/mut_cli.py` and `mut_paper_golden.py` (git-ignored; `integration_red` names the moved tests), run by #288's workflow. #292 is Todo, `blocked_by: [288]`, linked.
- The 12 borderline CLI tests are #282's (Shyden 2026-10-13).

## PR-on-red hook (from shyden.co.uk, 2026-10-14): checked, nothing to do
- All 14 required checks on `develop` are `ci.yml` jobs (`strict: true`). `record-floors.yml` runs on a PR label and `yahoo-shape.yml` on dispatch; neither is required. The hook's `ci.yml` read covers this repo.

## Resume steps
1. Run `ListAgents`; no subagents were started.
2. If this file's docs PR (`docs-handover-319`) is still open, read its run by job name and merge it when green.
3. Next: **#282** (the global unit-limit rule puts it at the top of the queue; every decision in it is on the ticket). Rebase `282-unit-tests-under-1s` on `origin/develop` first. Then #288 (unblocks #292). No Priority field yet (#315 blocked), so the order is the queue's.

## Next on the clean-up queue (all before #222)
- **#282** (13: warm cache, CPU check, now also the 12 borderline), **#287** (3, Node 26), **#288** (5, mutations in CI, now with #292's 30), **#272** (5, Python floors), **#315** (2, board Priority, blocked by repo-template#6), **#317** (5, orphan check in the PR gate), **#320** (2, README for the extension direction).

## Raised with Shyden
- Three global hook false positives, for a dedicated `~/.claude` session (his choice, 2026-10-12): `~/.claude/hook-false-positives-2026-10-13.md`.

## Progress (2026-10-14, `uv run --locked python .superpowers/sdd/estimates/progress.py`)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points). Board open: 35 tickets, 208 points (epic #214 unscored). Closed 2026-10-07 to 2026-10-14: 5 tickets, 26 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-12-01, low confidence:** 34 open scored tickets at 0.71 a day is 48 days.
- **By effort: 208 points remaining across 34 scored open tickets. ETA 2026-12-09, low confidence:** 3.7 points a day is 56 days.
- **Assumed:** last week's pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315.
