# Handover: steadyhand

**Updated:** 2026-10-23 (UTC). Current state only. Older history: `git show ff266fc:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (135fc3a when written, CI run 39937439249 all green, deploy-dev included). Merge green PRs into develop without asking; never `main`.
- **#394 is DONE**: PR #399 squash-merged (135fc3a), issue closed with every AC's evidence, board Done. Worktree `../steadyhand-394` (branch `394/node-v8-coverage`, tip c5fa558 = the merged PR head) can be removed.
- **`374/measure-every-suite`** (#374, 13 points, now unblocked): worktree `../steadyhand-374`, draft PR #389, head 7698da2. What it meets on merging develop: comment 6362572182 on #374 (build.ts folds away; no vi.mock/hoisted/doMock and four more, guard-refused; test/setup/config files enter at 0 untested; 8 files still unmeasured, all #374's). Rework detail: comment 6358790956.
- `272/python-floors` paused until #374. `391/cut-thirty-days`: uncommitted attempt in `../steadyhand-391`. Keep `203/spec-amendment-wip`, `ext/s3b-guards`.

## Resume steps
1. `ListAgents`; `git rev-parse origin/develop`.
2. Next ticket by the queue: #374. In `../steadyhand-374`: merge `origin/develop` (conflicts: build.ts take develop's; record-floors.test.ts and tool-configs.test.ts lose vi.mock), re-record floors via record-floors.yml on a scratch ref, run a local gate (copy `.superpowers/sdd/394/gate.sh` for 374), push, read CI by name.
3. Laptop runs only unit, lint, format, types. A live CI plant must trip only its target check (memory `feedback-live-plants-move-no-floor`).

## Waiting on Shyden
- #394's guard refuses four vi members beyond the ruling's three (unmock, doUnmock, importActual, importMock: Vitest's own rewrite trigger). Told 2026-10-23; no answer yet.
- #400 (filed for repo-template#86): confirm the ruling that `main` drops strict for a release-cut check; measured strict: true, develop..main empty; the setting is his click.
- #272: constant-name `setattr` read like `x.name = value`. #308's read-only key.
- Deleting `381/coverage-gate`, `367/scratch-ref-recorder`, stray `coverage/374/helper-coverage`; discarding #391's attempt.

## Nothing running
No background job, monitor, container or CI run of this session.

## Next on the clean-up queue (all before #222)
#374 (13, PR #389), #391 (2), #382 (5), #365 (5, blocks #272), #366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #400 (3, waits on Shyden), #308 (2), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2).

## Progress (2026-10-23, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 44 tickets, 242 points across 43 scored (epic #214 unscored). Closed 2026-10-16 to 2026-10-23: 8 tickets, 46 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-30, low confidence:** 43 open scored tickets at 1.14 a day is about 38 days.
- **By effort: 242 points remaining across 43 scored open tickets. ETA 2026-11-29, low confidence:** 6.6 points a day is about 37 days.
- **Assumed:** last week's pace holds (it includes #394's 13). **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), the key (#308), #272's ruling, #400's ruling.
