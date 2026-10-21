# Handover: steadyhand

**Updated:** 2026-10-22 (UTC). Current state only. Older history: `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Coverage rulings of 2026-10-22 (global; full text: last two paragraphs of `~/.claude/global-rules/reference/reference-engineering-standards.md`)
- Code = every `.py`, `.ts`, `.js` (tests, configs) AND workflow files. Skipped lines (`pragma: no cover`, `exclude_also`) count as unrun.
- Workflow lines are measured from a run on the same commit, shell traced; never-on-PR code runs on the PR's commit (deploy-dev rehearsal; hand-started workflows on a scratch branch `coverage/<branch>`).
- The ratchet is per-file UNTESTED counts (statements, branch arms), record EQUAL to measured, recorded in the record-floors run.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (4e282cc when written). Merge green PRs into `develop` without asking; never `main`.
- **`381/coverage-gate`** (#381, In Progress, 13): worktree `../steadyhand-381`, **draft PR #387**, head = the record fold (read `git rev-parse HEAD` there). **Not to merge before Shyden rules on where the record is measured** (question below).
- `272/python-floors` (#272, paused until #381 and #374): worktree `../steadyhand-272`, local head e6426b2; never push this branch again. Uncommitted on purpose there: `tests/guards/test_no_literal_floor.py` (copy `.superpowers/sdd/272/test_no_literal_floor-20261020a.py`).
- To delete when Shyden agrees: `367/scratch-ref-recorder` (#369), `272/python-floors` once its new branch lands. Kept: `203/spec-amendment-wip`, `ext/s3b-guards`.

## #381 state (design `.superpowers/sdd/381/design.md`; local gate `.superpowers/sdd/381/gate.sh`, mutations `mutate.py`)
- Built: `scripts/coverage_gate.py` (joins Python unit + guards on both Pythons, extension unit + guards, workflow reports; record EQUAL to measured; PR record held to develop's: no rise, no newly unmeasured, renames kept; changed lines run; ignore hints refused; prints the measured record on a difference), `scripts/run_tool.py`, every tracked Python file measured, `fail_under` gone, reports kept by each job, the gate in the coverage job's last step (reader && gate on one line).
- Record (`tests/coverage_record.json`) folded from CI's own print on c426800: 87 files, 1717 untested statements, 98 arms, 31 unmeasured TS/JS (#374). Whole project 92.86% statements, 96.87% arms.
- Wobble: none in 3 local unit runs per Python, none in 3 extension unit runs; the fold's run is the first CI read.
- Found on CI and fixed: vitest's implicit-else arm has empty start/end; TYPE_CHECKING imports and the Python guards suite unmeasured; a record re-made to match a worse measurement would have passed (now held to develop's).

## Resume steps
1. Run `ListAgents`; none were started.
2. PR #387 is green on the record fold: it passed on 20fb25d (measured == record, the first CI read of wobble: none).
3. Ask Shyden (AskUserQuestion) the parked questions below; then finish #381 per his answer, mark the PR ready, merge when green, read the job back as required (`required_status_checks.contexts`, add `coverage`).
4. Then **#374** (13), then #272 resumes. Global "No holes": `Gaps checked:` in every commit.

## Waiting on Shyden (parked questions)
- **Where the record is measured** (#381): today the gate prints CI's measured record on a difference and the laptop folds it (one extra PR run per count change); his ruling named "the same CI record run as the floors" (record-floors on a scratch ref), which cannot measure ci.yml's own lines. Options and costs in `.superpowers/sdd/381/design.md`.
- **Skipped kinds he was not shown**: "Count them as unrun" also counts `if TYPE_CHECKING:` blocks (14 lines, 7 files) and one-line Protocol stubs and properties (13 lines), beside the 52 bare `...` lines and 24 pragma lines he was shown. Confirm, or rule otherwise.
- #272: confirm my reading that a `setattr` with a constant name is read like `x.name = value`.
- #308's read-only key.

## Next on the clean-up queue (all before #222)
#381 (13, draft PR #387), #374 (13), #382 (5), #365 (5, blocks #272), #366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #308 (2, waits on the key), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2).

## Progress (2026-10-22, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points), none in 7 days. Board open: 43 tickets, 250 points across 42 scored (epic #214 unscored). Closed 2026-10-16 to 2026-10-22: 9 tickets, 38 points (#384 among them).
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-24, low confidence:** 42 open scored tickets at 1.29 a day is about 33 days.
- **By effort: 250 points remaining across 42 scored open tickets. ETA 2026-12-07, low confidence:** 5.4 points a day is about 46 days.
- **Assumed:** last week's pace holds through coverage work. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 (#315), repo-template#27 (#348), Shyden's key (#308).
