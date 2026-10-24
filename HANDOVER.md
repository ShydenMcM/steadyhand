# Handover: steadyhand

**Updated:** 2026-10-24 (UTC). Current state only. Older history: `git show ff266fc:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (045dbaa when written; ci run 40068765575 all 158 steps green, deploy-dev included). Merge green PRs into develop without asking; never `main`.
- **#403 DONE** (filelock CVEs, P0): PR #404 squash-merged, closed with each AC's evidence, board Done; branch and worktree removed.
- **#374 open** (13 points): PR #389 merged (a628d3b); the 7 files still untested are listed line by line in comment 6380578176. Worktree `../steadyhand-374` (branch `374/measure-every-suite`, tip cf82714 = the merged head; remote deleted) can be removed.
- #394 DONE (worktree `../steadyhand-394` removable). `272/python-floors` paused until #374. `391/cut-thirty-days`: uncommitted attempt in `../steadyhand-391`. Keep `203/spec-amendment-wip`, `ext/s3b-guards`.

## Resume steps
1. `ListAgents`; `git rev-parse origin/develop`.
2. #374's last 7 files on a new branch from develop (comment 6380578176): give each untested Python arm its other path in a test, or remove it if dead. The workflow lines (yahoo-shape 11, record-floors 1) need locating first, then a ruling from Shyden on failure-only steps. Gate: copy `.superpowers/sdd/374/gate.sh` (it runs `check floors-current`).
3. After any extension change, re-record the floors before pushing (`floors-current.zsh` refuses otherwise; it judges only the branch's own commits). Laptop runs only unit, lint, format, types.

## Waiting on Shyden
- #400: ACs follow the template, AC3 pins `release-cut` to app 15368 (rule of 2026-10-24). His: strict off on `main`, then requiring the status.
- #308: `main` lacks `coverage` (comment 6380589582); his click. Every required check is pinned to app 15368.
- #394's guard refuses four vi members beyond the ruling's three; told 2026-10-23, no answer yet.
- #272: constant-name `setattr` read like `x.name = value`. #308's read-only key.
- Whether the floors check should narrow to the files floor guards read (now: any extension change needs a record).
- Deleting `381/coverage-gate`, `367/scratch-ref-recorder`, stray `coverage/374/helper-coverage`; discarding #391's attempt.

## Running
Nothing: no background job, monitor or CI run of this session.

## Next on the clean-up queue (all before #222)
#374 (13, last 7 files), #391 (2), #405 (2, load headroom), #382 (5), #365 (5, blocks #272), #366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #400 (3, waits on Shyden), #308 (2), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2).

## Progress (2026-10-24, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 45 tickets, 244 points across 44 scored (epic #214 unscored). Closed 2026-10-17 to 2026-10-24: 9 tickets, 47 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-27, low confidence:** 44 open scored tickets at 1.29 a day is about 34 days.
- **By effort: 244 points remaining across 44 scored open tickets. ETA 2026-11-30, low confidence:** 6.7 points a day is about 37 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), the key (#308), #272's ruling, #400's and #308's settings clicks.
