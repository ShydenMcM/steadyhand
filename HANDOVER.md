# Handover: steadyhand

**Updated:** 2026-10-24 (UTC). Current state only. Older history: `git show ff266fc:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (c617765 when written, #408's squash; its CI run 40077051826, deploy-dev included). Merge green PRs into develop without asking; never `main`.
- **#374 open, waits on #382** (13 points): PR #408 merged (c617765): the coverage record holds only `.github/workflows/record-floors.yml` [1, 0], line 58 (its refusal of a non-scratch ref). Shyden 2026-10-24: "Measure it in #382". Evidence: comment 6381842167.
- Shyden 2026-10-24 also ruled yahoo-shape's failure-only issue step removed ("Remove the step"): done in #408.
- `272/python-floors` paused until #374. `391/cut-thirty-days`: uncommitted attempt in `../steadyhand-391` (patch `.superpowers/sdd/374/391-attempt-20261022.patch`). Keep `203/spec-amendment-wip`, `ext/s3b-guards`.

## Resume steps
1. `ListAgents`; `git rev-parse origin/develop`; read develop's CI on it by name.
2. Next: #391 (2 points, test_thirty_days_to_run_proceed under 70 ms of own CPU), then #407 (2, the journey test). Both need the heaviest run over at least five full limits runs including one under load, trees alternated (memory `feedback-cpu-time-moves-with-load`).
3. **#382 must measure record-floors line 58**: on its scratch branch `coverage/<branch>`, dispatch record-floors twice at the PR's head, once normally and once with `-f ref=refs/heads/develop` (the refusal), so `scripts/workflow_runs.py` joins both; then the record drops to `{"files": {}}` and #374 closes with each AC's evidence.
4. Every PR changing a non-unit test file needs a mutation targeting it (the mutations plan refuses otherwise). In TOML literal strings `'...'` a `\n` stays a backslash and n: anchor to the line's end, and count each anchor in its file before pushing.
5. Laptop runs only unit, lint, format, types. Gate template: `.superpowers/sdd/374b/gate.sh` (set TREE and LOG for the new worktree).

## Filed this session
- #407 (2 points, Todo): `test_a_paper_traders_journey` 103 ms own CPU under load; cut under 70 ms.
- #405 comment 6381614316: three more files over the 0.1 s load limit under load (test_cache, test_run_mutations, test_ci_fast_path).

## Waiting on Shyden
- #400: his settings click (strict off on `main`, then requiring `release-cut`).
- #308: `main` lacks `coverage` (comment 6380589582); his click.
- #394's guard refuses four vi members beyond the ruling's three; told 2026-10-23, no answer yet.
- #272: constant-name `setattr` read like `x.name = value`. #308's read-only key.
- Whether the floors check should narrow to the files floor guards read.
- Deleting `381/coverage-gate`, `367/scratch-ref-recorder`, stray `coverage/374/helper-coverage` and `coverage/374/last-seven-files`; discarding #391's attempt.

## Running
Nothing of this session after its develop CI waiter (run 40077051826).

## Next on the clean-up queue (all before #222)
#391 (2), #407 (2), #405 (2), #382 (5, also measures record-floors line 58 and so closes #374), #365 (5, blocks #272), #366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #400 (3), #308 (2), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2).

## Progress (2026-10-24, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 46 tickets, 246 points across 45 scored (epic #214 unscored). Closed 2026-10-17 to 2026-10-24: 9 tickets, 47 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-28, low confidence:** 45 open scored tickets at 1.29 a day is about 35 days.
- **By effort: 246 points remaining across 45 scored open tickets. ETA 2026-11-30, low confidence:** 6.7 points a day is about 37 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), the key (#308), #272's ruling, #400's and #308's settings clicks.
