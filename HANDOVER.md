# Handover: steadyhand

**Updated:** 2026-10-24 (UTC). Current state only. Older history: `git show ff266fc:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (f67c6f0 when written, #413's squash). Merge green PRs into develop without asking; never `main`.
- **#405 closed** (comment 6384633904): PR #413 squashed as f67c6f0, develop CI 40096743193 green (16 jobs, 158 steps). The load clock times compiling apart (Shyden's ruling, global); the coverage converter loads no amaro.
- **#407 open, held** for five full limits rounds at one-minute load above 20 (comment 6382861651; tools `.superpowers/sdd/407/measure.zsh`).
- **#374 open, waits on #382** (record-floors line 58; comment 6381842167).
- #405 AC1 posted (comment 6384344851): develop's heaviest load 102,909 us (a red run, all tests passing), the branch's 30,786; fully cold branch runs judge test_backtest at 5,188 / 5,734 us. Local gate (`.superpowers/sdd/405/gate.sh`): all green except floors-current, the extension floors to re-record.

## Resume steps
1. `ListAgents`; `git rev-parse origin/develop`; read develop's CI by name.
2. Commit this handover as a one-commit docs PR into develop if not yet done.
3. Read develop's CI on its new head by step.
4. Next: **#382** (5 points; also closes #374), then the queue below. #407's rounds whenever `sysctl -n vm.loadavg` reads above 20.
5. Every PR changing a non-unit test file needs a mutation targeting it; TOML basic strings `"..."` for `\n`. Commit and merge messages go in a file written in its own call, with the full Gaps checked section (Before, After, New passes).
6. Laptop runs only unit, lint, format and types; guards, integration and properties are CI's. Gate template: `.superpowers/sdd/405/gate.sh` (Python and extension; set TREE, LOG and the lock name). A unit file reads no clock (guards refuse `import time`).

## Global rule recorded this session
"Compiling is timed apart" (Shyden 2026-10-24, every project): `~/.claude/CLAUDE.md` load line and `global-rules/reference/reference-engineering-standards.md` ("COMPILING IS TIMED APART FROM A LOAD"). Other Python projects take it up in their own sessions; nothing filed outside steadyhand.

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
#382 (5, also closes #374), #365 (5, blocks #272), #366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #400 (3), #308 (2), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2); #407 (2) when load allows.

## Progress (2026-10-24, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 44 tickets, 242 points across 43 scored (epic #214 unscored). Closed 2026-10-17 to 2026-10-24: 11 tickets, 52 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-21, low confidence:** 43 open scored tickets at 1.57 a day is about 27 days.
- **By effort: 242 points remaining across 43 scored open tickets. ETA 2026-11-26, low confidence:** 7.4 points a day is about 33 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), the key (#308), #272's ruling, #400's and #308's settings clicks, machine load above 20 for #407.
