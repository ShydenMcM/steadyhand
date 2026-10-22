# Handover: steadyhand

**Updated:** 2026-10-23 (UTC). Current state only. Older history: `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

**Coverage rulings (2026-10-21/22, global):** the last five paragraphs of `~/.claude/global-rules/reference/reference-engineering-standards.md`. Today's: the record is measured by the PR's coverage job and folded on the laptop ("CI prints, laptop folds"); `TYPE_CHECKING` blocks count as unrun and are fixed by why they were hidden ("Check why, then fix by cause": a heavy library gets our own `Protocol` shape types); Vitest's unmeasurable test/setup/config files go to #394 via Node's own V8 coverage; timed tests run twice ("Two runs, one judges time").

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (71d0b19 when written). Merge green PRs into `develop` without asking; never `main`.
- **`374/measure-every-suite`** (#374, In Progress, 13, **Blocked by #394**, link set): worktree `../steadyhand-374`, draft PR #389, base `develop`, **head 7698da2 pushed**, clean tree. CI run 39865166363: every job green but `coverage`, whose only refusals are the Vitest test files and `vitest.config.ts` (#394's subject; details on #374 and #394). The stray scratch `coverage/374/helper-coverage` is still to delete; `coverage/374/measure-every-suite` is the live scratch branch.
- `381/coverage-gate`: merged; delete local and remote once Shyden agrees. `272/python-floors` (#272) paused until #374 (`../steadyhand-272`, head e6426b2, never push; uncommitted `tests/guards/test_no_literal_floor.py`, copy in `.superpowers/sdd/272/`). `391/cut-thirty-days`: uncommitted attempt in `../steadyhand-391` (discarding is Shyden's call). Keep `203/spec-amendment-wip`, `ext/s3b-guards`.

## #374: every item built, committed locally (all mutations as predicted)
- 7c17c97 AC9 perf; a82f2fa AC9 live ("Same as workflows": `coverage_gate.MEASURED_ONLY_BY`); ae0d156 AC6 build + tool configs (found: V8 counts 0 statements in a bare `export default <expr>`; the gate now refuses a zero-statement istanbul file); 3c4daa5 floors scripts + load reporter (`tests/lib/program.ts` `asProgram`); d7c17a9 plugins' hook bodies called directly; 80a2e91 side panel (AC5). Shyden 2026-10-23 "Leave until S14a": `content-script.ts`, `service-worker.ts` (`export {};`) stay unmeasured; noted on #374 and #238.
- Runners in `.superpowers/sdd/374/`: `mutate_live.py`, `mutate_ac6.py`, `mutate_scripts.py`, `mutate_plugins.py`, `mutate_shell.py` (run under `source ~/.claude/scripts/test-lock.zsh light ...`); gaps lists in `ac9-live-gaps.md`.

## Resume steps
1. Run `ListAgents`; none were started.
2. **#394 next** (8): its own branch off `develop` (`git branch --show-current` before every push). Set its board Priority to #374's level if lower (a blocker takes the top of what waits on it), and Status In Progress once the branch exists. Design and gaps list first; its AC3 derives the 28 files from Vitest's include.
3. After #394 merges: merge `develop` into `374/measure-every-suite`, push that head to `coverage/374/measure-every-suite`, start yahoo-shape there, wait, push the branch, wait for CI, fold CI's printed record (`tests/coverage_record.json`) as a new commit, and repeat the scratch + yahoo-shape round for that head (every head of #389 needs one, since it changes yahoo-shape.yml).
4. Green on the head SHA: mark #389 ready, merge to develop, verify every AC on #374 (AC5's two placeholders noted, by the ruling), close by hand.
5. Then #391, #382; #272 resumes after #374.

## Waiting on Shyden
- #272: confirm a constant-name `setattr` is read like `x.name = value`. #308's read-only key.
- Deleting `381/coverage-gate`, `367/scratch-ref-recorder`, the stray scratch `coverage/374/helper-coverage` (mine, wrong name); discarding #391's attempt.

## Next on the clean-up queue (all before #222)
#394 (8, blocks #374), #374 (13, PR #389, waits on #394), #391 (2), #382 (5), #365 (5, blocks #272), #366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #308 (2, waits on the key), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2).

## Progress (2026-10-23, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 44 tickets, 247 points across 43 scored (epic #214 unscored). Closed 2026-10-16 to 2026-10-23: 7 tickets, 33 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-12-05, low confidence:** 43 open scored tickets at 1.0 a day is about 43 days.
- **By effort: 247 points remaining across 43 scored open tickets. ETA 2026-12-15, low confidence:** 4.7 points a day is about 52 days.
- **Assumed:** last week's pace holds (it fell from 7.3 points a day as #374 grew). **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), the key (#308), #272's ruling.
