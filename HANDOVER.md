# Handover: steadyhand

**Updated:** 2026-10-19 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (`87b729f` when written, PR #347). Merge green PRs into `develop` without asking; never `main`.
- `docs-handover-cleanup-2026-10-20`: this file, one docs commit, PR into `develop`.
- Local branches kept by choice: `203/spec-amendment-wip` (also on GitHub, no PR; Shyden chose to keep it 2026-10-20), `ext/s3b-guards` (#222 WIP, 1 commit).

## Done this session (2026-10-20, clean-up pass)
- **Clean-up done and recorded** (`cleanup-done.sh steadyhand`; pass log in `~/.claude/global-rules/reference/reference-cleanup.md`). Shyden chose "Delete all" and "Delete 3, keep 203": 13 local branches removed (10 at a merged or closed PR head, plus 3 unlanded WIP of closed tickets), 44 closed-ticket scratch items and `.measure-302` (`.superpowers/sdd` 2.66 GB to 1.84 GB). One memory archived (`feedback-integration-is-cis`, wholly the laptop-runs-unit-only rule). Board census: 161 items, 0 mismatches, 0 In Progress, 0 off the board.
- **Filed #349** (P0, 2): Dependabot split `vitest` from `@vitest/coverage-v8` although the `vitest` group (since #267) names both, so #329 and #333 fail `npm ci` with ERESOLVE. Cause not yet known (AC 1).
- **Filed #350** (P0, 2): #334 moves TypeScript to 7.0.2, but `typescript-eslint` 8.71.1 accepts only `>=4.8.4 <6.1.0`. Hold the major in `dependabot.yml` (like `@types/node`, #270) or move both together.
- The ticket filer `file_ticket.sh` went with a closed-ticket scratch dir. `.superpowers/sdd/292/board_add.py <issue> <points>` adds the board item, sets Estimate and reads back. Priority goes in the issue body until #315.

## Resume steps
1. Run `ListAgents`. No subagents were started.
2. Merge this handover PR when green (docs fast path).
3. Next: **#349 and #350** (P0 defects, 2 each). #349's cause may need Shyden to open the Dependabot log page (the App cannot read it).
4. Then **#287** (3, Node 26; worked example yawelo-idle #501 / PR #507), then the queue below.
5. The four green Dependabot PRs (#330, #331, #332, #335) predate #342's required mutations check: each needs a rebase onto `develop` (`@dependabot rebase`), then merge when every required check is green on its head.
6. When Shyden has made #308's key: build the daily workflow (environment allowing `main` only, `--ref main` dispatch, a pin test, a planted mismatch that opens an issue).

## Waiting on Shyden / to do
- **#308's read-only key** (branch-protection read).
- Ticket-filing procedure (global, 2026-10-16, `reference-identity-and-agile.md` lines 41-42): steadyhand has no `.github/ISSUE_TEMPLATE`. File a story (search first) to bring the form and the open board up to yawelo-idle's `story.yml` and repo-template#20.

## Next on the clean-up queue (all before #222)
- **#349** (2, P0), **#350** (2, P0), **#287** (3, Node 26), **#272** (5, Python floors, including #323's five), **#348** (5, P1, SonarCloud blocking, waits on repo-template#27), **#308** (2, waits on the key), **#315** (2, board Priority, blocked by repo-template#6), **#317** (5, orphan check in the PR gate), **#320** (2, README for the extension direction), **#337** (3, blocker links), **#336** (5, logs suite, before #245), **#341** (2, login name out of the paper audit). #339 (extension log) and #345 (paper audit trail) are post-release.

## Raised with Shyden
- Three global hook false positives, for a dedicated `~/.claude` session (his choice, 2026-10-12): `~/.claude/hook-false-positives-2026-10-13.md`.

## Progress (2026-10-20, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` tickets left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points), none closed in the last 7 days. Board open: 37 tickets, 201 points across 36 scored (epic #214 unscored). Closed 2026-10-13 to 2026-10-20: 5 tickets, 27 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-12-09, low confidence:** 36 open scored tickets at 0.71 a day is about 50 days.
- **By effort: 201 points remaining across 36 scored open tickets. ETA 2026-12-11, low confidence:** 3.9 points a day is about 52 days.
- **Assumed:** this week's pace (clean-up queue, CI and test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315, repo-template#27 for #348, Shyden's key for #308.
