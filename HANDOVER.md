# Handover: steadyhand

**Updated:** 2026-10-26 (UTC). Current state only. Older history: `git show ff266fc:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (7bdec64 when written, #415's squash). Merge green PRs into develop without asking; never `main`.
- **#382 closed** (comment 6405961756) and **#374 closed** (comment 6405962599). PR #415 was squash-merged as 7bdec64, and develop CI run 40252215004 is green on it (12 jobs, 121 steps).
- What #382 changed: every job runs on `ubuntu-26.04`; Python is exactly 3.13.15 (Shyden, 2026-10-26: "3.13.15 only"), pinned only in `.python-version`; uv runs every Python step; the manifest's `minimum_chrome_version` is 119. `tests/guards/test_versions.py` checks all of it.
- Required checks: the four `(py3.12)` checks came off `develop` and `main` on 2026-10-26, done through Claude in Chrome with Shyden's consent for that change only. Both lists were read back: develop has 12, main has 11, and `strict` is unchanged.
- **#407 open, held** for five full limits rounds at one-minute load above 20 (`.superpowers/sdd/407/measure.zsh`).

## Resume steps
1. `ListAgents`; `git rev-parse origin/develop`; read develop's CI by name.
2. Commit this handover as a one-commit docs PR into develop if not yet done, then read develop's CI on the new head.
3. Next: **#365** (5 points, blocks #272), then the queue below. Run #407's rounds whenever `sysctl -n vm.loadavg` reads above 20.
4. A PR changing a workflow other than ci.yml runs that workflow on `coverage/<branch>` at the PR head before the PR push (`scripts/workflow_runs.py`). Every new commit needs the runs again at its own SHA, so settle every edit first. Before the first push, run the text guards' readers over new test files from a script (memory `feedback-new-test-files-meet-the-text-guards`).
5. The laptop runs only unit, lint, format and types. Every PR changing a non-unit test file needs a mutation targeting it. Commit and merge messages go in a file written in its own call, with the full Gaps checked section. Gate template: `.superpowers/sdd/382/gate.sh` (one Python now).

## Waiting on Shyden
- #400: his settings click (strict off on `main`, then requiring `release-cut`).
- #308: `main` lacks `coverage` (comment 6380589582); his click.
- #394's guard refuses four vi members beyond the ruling's three; told 2026-10-23, no answer yet.
- #272: constant-name `setattr` read like `x.name = value`. #308's read-only key.
- Whether the floors check should narrow to the files floor guards read.
- Deleting `381/coverage-gate`, `367/scratch-ref-recorder`, stray `coverage/374/helper-coverage` and `coverage/374/last-seven-files`; discarding #391's superseded attempt in `../steadyhand-391`.

## Running
Nothing.

## Next on the clean-up queue (all before #222)
#365 (5, blocks #272), #366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #400 (3), #308 (2), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2); #407 (2) when load allows.

## Progress (2026-10-26, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 42 tickets, 224 points across 41 scored (epic #214 unscored). Closed 2026-10-19 to 2026-10-26: 13 tickets, 70 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-17, low confidence:** 41 open scored tickets at 1.86 a day is about 22 days.
- **By effort: 224 points remaining across 41 scored open tickets. ETA 2026-11-17, low confidence:** 10 points a day is about 22 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), the key (#308), #272's ruling, #400's and #308's settings clicks, machine load above 20 for #407.

## Notes
- Wi-Fi is unstable (Shyden, 2026-10-26): name the network as a possible cause of a failed fetch or push; still no retries.
