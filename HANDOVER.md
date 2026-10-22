# Handover: steadyhand

**Updated:** 2026-10-22 (UTC). Current state only. Older history: `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

**Coverage rulings (2026-10-21/22, global):** the last five paragraphs of `~/.claude/global-rules/reference/reference-engineering-standards.md`. Today's: the record is measured by the PR's coverage job and folded on the laptop ("CI prints, laptop folds"); `TYPE_CHECKING` blocks count as unrun and are fixed by why they were hidden ("Check why, then fix by cause": a heavy library gets our own `Protocol` shape types); Vitest's unmeasurable test/setup/config files go to #394 via Node's own V8 coverage; timed tests run twice ("Two runs, one judges time").

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (dd8f9a9 when written: #387 squash-merged). Merge green PRs into `develop` without asking; never `main`.
- **`374/helper-coverage`** (#374, In Progress, 13): worktree `../steadyhand-374`, draft PR #389, **local head 5211f50 not pushed** (read `git rev-parse HEAD` there). It already holds develop: `31f5bc5` merged #381's last head, `92d122d` recorded develop's squash with `-s ours` (trees equal, af7ee6b). PR #389's base is still `381/coverage-gate`: retarget it to `develop` at the push.
- `381/coverage-gate`: merged; delete local and remote once Shyden agrees (tip e49c98d IS the merged head).
- `272/python-floors` (#272, paused until #374): worktree `../steadyhand-272`, local head e6426b2; never push this branch again. Uncommitted on purpose: `tests/guards/test_no_literal_floor.py` (copy in `.superpowers/sdd/272/`).
- `391/cut-thirty-days` (#391): worktree `../steadyhand-391` holds an uncommitted attempt that does not cut the CPU (findings on #391); discarding it is Shyden's call.
- To delete when Shyden agrees: `367/scratch-ref-recorder` (#369), `381/coverage-gate`. Keep `203/spec-amendment-wip`, `ext/s3b-guards`.

## #381 (merged as dd8f9a9, still OPEN)
`coverage` is in `required_status_checks.contexts` (16, strict, read back). Last AC5 item: the docs-only fast path still reports `coverage`. **This handover PR is that proof**: read its `coverage` check by name; if it reports success, close #381 by hand (comment naming the PR). If it does not report, the docs-only path is broken: fix before anything else.

## #374 state (gate `.superpowers/sdd/374/gate.sh`, mutations `mutations/374.toml`)
- Done before today: integration suite measured, properties measured twice and joined, reports expected by name, Protocol `...` bodies are docstrings, Yahoo download stood in, stand-ins and recorders run. CI green on 2fb8220: 99.25% statements, 98.76% arms.
- **Done today (5211f50, AC8):** no `TYPE_CHECKING` left. `scripts/workflow_coverage.py` and `workflow_runs.py`: runtime imports. `steadyhand_idx/yahoo.py` + `tests/idx/test_yahoo.py`: pandas replaced by `YahooFrame`/`YahooSplits`/`YahooRecord`/`YahooIndex`/`YahooColumns`/`YahooStamp` (pandas costs 1.555 s CPU at load). `cli.py`: `Writable` replaces `_typeshed.SupportsWrite`. mypy, ruff clean; 681 affected unit tests pass; a planted Protocol member turned mypy red at all 7 call sites.
- **Next (AC9, design first):** perf runs twice. The 6 time checks are inline asserts in `tests/perf/*.py`. Needs: one helper judging time; a measured run (`-m perf --cov`, its own report, added to the coverage job's `--reports`) that judges no time; the judged run refusing coverage, and the untimed mode refusing to run without coverage (no way to dodge the verdict). Same for `test_yahoo_live` in `yahoo-shape.yml`. Write the before-list of gaps, plant each, then build.
- Then: TS files Vitest can measure (AC6: `build.ts`, `eslint.config.js`, `playwright.config.ts` loaded in-process), the shell (16 lines), plugins' untraced-only paths (unit_limits, load_clock: a measurement limit to put to Shyden), run the full gate, push, retarget #389, fold CI's record.

## Resume steps
1. Run `ListAgents`; none were started.
2. Read this PR's checks by name (AC5 proof above); close #381 if `coverage` reported.
3. #374 AC9 design, then the rest of #374 as listed.
4. Then #394 (8, blocked by #381 until closed), #391, #382; #272 resumes after #374.

## Waiting on Shyden
- #272: confirm a constant-name `setattr` is read like `x.name = value`. #308's read-only key.
- Deleting `381/coverage-gate`, `367/scratch-ref-recorder`; discarding #391's attempt.

## Next on the clean-up queue (all before #222)
#374 (13, draft PR #389), #394 (8), #391 (2), #382 (5), #365 (5, blocks #272), #366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #308 (2, waits on the key), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2).

## Progress (2026-10-22, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 45 tickets, 260 points across 44 scored (epic #214 unscored). Closed 2026-10-16 to 2026-10-22: 9 tickets, 38 points. #394 (8) filed today.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-25, low confidence:** 44 open scored tickets at 1.29 a day is about 34 days.
- **By effort: 260 points remaining across 44 scored open tickets. ETA 2026-12-09, low confidence:** 5.4 points a day is about 48 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), the key (#308), #272's ruling.
