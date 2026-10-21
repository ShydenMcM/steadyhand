# Handover: steadyhand

**Updated:** 2026-10-22 (UTC). Current state only. Older history: `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

**Coverage rulings (2026-10-21/22, global):** last three paragraphs of `~/.claude/global-rules/reference/reference-engineering-standards.md` (code = .py/.ts/.js + workflows; skipped lines unrun; workflow lines traced; per-file untested counts EQUAL to measured).

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (4e282cc when written). Merge green PRs into `develop` without asking; never `main`.
- **`381/coverage-gate`** (#381, In Progress, 13): worktree `../steadyhand-381`, **draft PR #387**, head = the record fold (read `git rev-parse HEAD` there). **Not to merge before Shyden rules on where the record is measured** (question below).
- `272/python-floors` (#272, paused until #381 and #374): worktree `../steadyhand-272`, local head e6426b2; never push this branch again. Uncommitted on purpose there: `tests/guards/test_no_literal_floor.py` (copy `.superpowers/sdd/272/test_no_literal_floor-20261020a.py`).
- To delete when Shyden agrees: `367/scratch-ref-recorder` (#369), `272/python-floors` once its new branch lands. Kept: `203/spec-amendment-wip`, `ext/s3b-guards`.

## #381 state (draft PR #387, green; design `.superpowers/sdd/381/design.md`)
- `scripts/coverage_gate.py` in the coverage job's last step (reader && gate on one line): every suite's report joined, the record (`tests/coverage_record.json`) EQUAL to measured, a PR's record held to develop's, changed lines run, ignore hints refused; prints CI's measured record on a difference (folded by the laptop).

## Resume steps
1. Run `ListAgents`; none were started.
2. PR #387 is green on the record fold: it passed on 20fb25d (measured == record, the first CI read of wobble: none).
3. Ask Shyden (AskUserQuestion) the parked questions below; then finish #381 per his answer, mark the PR ready, merge when green, read the job back as required (`required_status_checks.contexts`, add `coverage`).
4. Then **#374** (13), then #272 resumes. Global "No holes": `Gaps checked:` in every commit.

## #374 state (draft PR #389, stacked on #387; worktree `../steadyhand-374`, gate `.superpowers/sdd/374/gate.sh`, mutations `mutations/374.toml`)
- Built: integration suite measured (child programs via the subprocess patch; the planted unit-limits child untraced), properties measured twice and joined once with each run (wobble = a verdict differing between joins; none seen), reports expected by name (`--reports`), Protocol `...` bodies are their docstrings (`exclude_also` gone), the Yahoo download tested with yfinance stood in (pragma gone), every stand-in's members and tripwires run, the recorders' entry points run and the CLI seed rebuilt byte for byte (integration).
- CI green on 2fb8220 (the last fold): 99.25% statements, 98.76% arms; record 19 files, 192 statements, 39 arms, 31 unmeasured TS/JS. Also run tonight: each guard's failing branch on a plant, the recorders' entry points, every stand-in's members.
- Left: TYPE_CHECKING blocks (question 2), perf (question 4), test_yahoo_live (runs only in yahoo-shape: same question as perf), TS test/setup/config files (question 3), plugins' untraced-only paths (unit_limits, load_clock: they run only without coverage, a measurement limit to put to Shyden), the shell (16 lines).

## Waiting on Shyden (parked questions; ask with AskUserQuestion, recommendations first)
1. **Where the record is measured** (#381): today CI prints its measured record on a difference and the laptop folds it (one extra PR run per count change, working on #387 and #389). His ruling named the record-floors scratch-ref run, which cannot measure ci.yml's own lines. Recommend: keep "CI prints, laptop folds".
2. **Skipped kinds he was not shown**: "Count them as unrun" also counts `if TYPE_CHECKING:` imports (14 lines, 7 files: they never run, so they must become runtime imports). Recommend: count them, rewrite as runtime imports.
3. **Vitest cannot measure test files, setup files or its own config** (hard-coded, "cannot be overridden"): 18 test files + 3 setup files + vitest.config.ts. Recommend: a new story measuring them with Node's raw V8 coverage (NODE_V8_COVERAGE) converted to istanbul (est. 5-8, unmeasured).
4. **Perf suite under coverage**: its time checks would time the tracer. Recommend: a measured run that judges no time (the limited run judges it), as the unit job does.
5. #272: confirm a constant-name `setattr` is read like `x.name = value`. #308's read-only key.

## Next on the clean-up queue (all before #222)
#381 (13, draft PR #387), #374 (13, draft PR #389), #391 (2, a unit test's CPU under load), #382 (5), #365 (5, blocks #272), #366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #308 (2, waits on the key), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2).

## Progress (2026-10-22, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points), none in 7 days. Board open: 44 tickets, 252 points across 43 scored (epic #214 unscored). Closed 2026-10-16 to 2026-10-22: 9 tickets, 38 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-24, low confidence:** 43 open scored tickets at 1.29 a day is about 33 days.
- **By effort: 252 points remaining across 43 scored open tickets. ETA 2026-12-08, low confidence:** 5.4 points a day is about 46 days.
- **Assumed:** last week's pace holds. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 (#315), Shyden's key (#308), his rulings on the parked questions.
