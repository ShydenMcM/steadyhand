# Handover: steadyhand

**Updated:** 2026-10-24 (UTC). Current state only. Older history: `git show ff266fc:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (77de77f when written, #411's squash; its CI run 40084356406). Merge green PRs into develop without asking; never `main`.
- **#391 closed**: PR #410 merged (fcadc24, develop CI 40081146834 green, 158 steps). Evidence: comment 6382409768.
- **#407 open, held** (Shyden 2026-10-24: "Hold for heavy load"): PR #411 merged (77de77f), the journey stand-in split into three phase tests. Heaviest 51.9 ms at load 4 to 8; it closes after five more full limits runs at one-minute load above 20 with the halt test at or under 70 ms (comment 6382861651). Tools: `.superpowers/sdd/407/measure.zsh` (set OLD to a develop-before-#411 worktree, or drop the alternation and judge the branch tests alone).
- **#374 open, waits on #382** (13 points): the coverage record holds only `.github/workflows/record-floors.yml` [1, 0], line 58. Shyden: "Measure it in #382". Evidence: comment 6381842167.
- `272/python-floors` paused until #374. `391/cut-thirty-days` in `../steadyhand-391`: its uncommitted attempt is now superseded by #410 (patch kept at `.superpowers/sdd/374/391-attempt-20261022.patch`). Keep `203/spec-amendment-wip`, `ext/s3b-guards`.

## Resume steps
1. `ListAgents`; `git rev-parse origin/develop`; read develop's CI on it by name (run 40084356406 on 77de77f was running when written).
2. Commit this handover as a one-commit docs PR if not yet done.
3. Next: **#405** (2 points): unit files over the 0.1 s LOAD limit. Measured so far (comments 6381614316, 6382341750, 6382468155): test_backtest 111.9-133.6 ms, test_cache 106.6-144.9, test_run_mutations 100.5-129.3, test_ci_fast_path 105.8-106.9, test_yahoo 101.0, test_paper_run 103.8 (3.13). Its estimate likely needs re-measuring: six files, not two.
4. #407's heavy-load rounds whenever `sysctl -n vm.loadavg` reads above 20 (memory `feedback-cpu-time-moves-with-load`).
5. **#382 must measure record-floors line 58**: on its scratch branch `coverage/<branch>`, dispatch record-floors twice at the PR's head, once normally and once with `-f ref=refs/heads/develop` (the refusal), so `scripts/workflow_runs.py` joins both; then the record drops to `{"files": {}}` and #374 closes with each AC's evidence.
6. Every PR changing a non-unit test file needs a mutation targeting it. In TOML literal strings `'...'` a `\n` stays a backslash and n: anchor to the line's end, and count each anchor before pushing.
7. Laptop runs only unit, lint, format, types. Gate template (Python only): `.superpowers/sdd/391/gate.sh` (set TREE, LOG and the lock name). Commit messages need the "Gaps checked:" section; a merge message goes in a file written in its own call.

## Waiting on Shyden
- #400: his settings click (strict off on `main`, then requiring `release-cut`).
- #308: `main` lacks `coverage` (comment 6380589582); his click.
- #394's guard refuses four vi members beyond the ruling's three; told 2026-10-23, no answer yet.
- #272: constant-name `setattr` read like `x.name = value`. #308's read-only key.
- Whether the floors check should narrow to the files floor guards read.
- Deleting `381/coverage-gate`, `367/scratch-ref-recorder`, stray `coverage/374/helper-coverage` and `coverage/374/last-seven-files`; discarding #391's superseded attempt in `../steadyhand-391`.

## Running
Develop CI waiter on 77de77f (run 40084356406, background, this session): DEAD after `/clear`; read the run by name instead.

## Next on the clean-up queue (all before #222)
#405 (2), #382 (5, also closes #374), #365 (5, blocks #272), #366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #400 (3), #308 (2), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2); #407 (2) when load allows.

## Progress (2026-10-24, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 45 tickets, 244 points across 44 scored (epic #214 unscored). Closed 2026-10-17 to 2026-10-24: 10 tickets, 49 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-24, low confidence:** 44 open scored tickets at 1.43 a day is about 31 days.
- **By effort: 244 points remaining across 44 scored open tickets. ETA 2026-11-28, low confidence:** 7.0 points a day is about 35 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), the key (#308), #272's ruling, #400's and #308's settings clicks, machine load above 20 for #407.
