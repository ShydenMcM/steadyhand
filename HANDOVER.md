# Handover: steadyhand

**Updated:** 2026-10-22 (UTC). Current state only. Older history: `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Coverage rulings of 2026-10-22 (global; full text: last two paragraphs of `~/.claude/global-rules/reference/reference-engineering-standards.md`)
- Code = every `.py`, `.ts`, `.js` (tests, configs) AND workflow files. Skipped lines (`pragma: no cover`, `exclude_also`) count as unrun.
- Workflow lines are measured from a run on the same commit, shell traced; never-on-PR code runs on the PR's commit (deploy-dev rehearsal; hand-started workflows on a scratch branch `coverage/<branch>`).
- The ratchet is per-file UNTESTED counts (statements, branch arms), record EQUAL to measured, recorded in the record-floors run.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (e555f4e when written, #384 merged). Merge green PRs into `develop` without asking; never `main`.
- `272/python-floors` (#272, paused until #381 and #374): worktree `../steadyhand-272`, local head e6426b2; never push this branch again (new branch name, normal push). Uncommitted on purpose there: `tests/guards/test_no_literal_floor.py` (copy `.superpowers/sdd/272/test_no_literal_floor-20261020a.py`).
- To delete when Shyden agrees: `367/scratch-ref-recorder` (#369), `272/python-floors` once its new branch lands. Kept: `203/spec-amendment-wip`, `ext/s3b-guards`.

## Workflow coverage, as built in #384 (design `.superpowers/sdd/384/design.md`)
- Every workflow sets the tracing shell; every job's last step uploads its traces; ci.yml's `coverage` job (needs all, `!cancelled()`) reads its own run (`--own-traces`) and, on a PR, `scripts/workflow_runs.py` reads each changed hand-started workflow from its runs on `coverage/<branch>` at the PR head.
- **A PR that changes yahoo-shape, record-floors or mutations** must first push its head to `refs/heads/coverage/<branch>` (and `refs/floors/<branch>` for record-floors), start each there (`gh workflow run <file> --ref coverage/<branch>`, record-floors `-f ref=refs/floors/<branch>`, mutations `-f file=mutations/<n>.toml`), wait (`.superpowers/sdd/384/cycle.sh` shows the shape), then push the PR branch by hand. Every new head repeats it.
- Measured unrun today: `record-floors.yml:58` (refusal arm), `yahoo-shape.yml:65-76` (failure-only issue step); ci.yml 625/625.
- Limits: line granularity; a heredoc fed to bash/python3 is one unit.

## Resume steps
1. Run `ListAgents`; none were started.
2. If this file's PR is open: merge it when green (docs fast path).
3. **#381** (13, next): the gate, in ci.yml's `coverage` job. ACs on its body: Python unit (both Pythons) and the extension's unit and guards write machine-readable reports; one record of per-file untested counts (statements, branch arms) plus the unmeasured tracked code files, EQUAL to measured, recorded in the record-floors scratch-ref run; changed-line check against `origin/develop` over Python, TypeScript and the workflow reports (#384's coverage.py-shaped JSON); all Python under `tests/` and `scripts/` added to coverage; `fail_under = 100` replaced by the record; v8/c8/istanbul ignore hints refused; wobble measured before the first record. Plan it, review to zero, build test first. Then **#374** (13), then #272 resumes.
4. Global "No holes": `Gaps checked:` in every commit (hook-enforced).

## Waiting on Shyden
- #308's read-only key (branch-protection read).
- #272: confirm my reading that a `setattr` with a constant name is read like `x.name = value` ("Fail closed" covered the non-constant form).

## Next on the clean-up queue (all before #222)
#381 (13, now), #374 (13), #382 (5), #365 (5, blocks #272), #366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #308 (2, waits on the key), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2).

## Progress (2026-10-22, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points), none in 7 days. Board open: 43 tickets, 250 points across 42 scored (epic #214 unscored). Closed 2026-10-16 to 2026-10-22: 9 tickets, 38 points (#384 among them).
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-24, low confidence:** 42 open scored tickets at 1.29 a day is about 33 days.
- **By effort: 250 points remaining across 42 scored open tickets. ETA 2026-12-07, low confidence:** 5.4 points a day is about 46 days.
- **Assumed:** last week's pace holds through coverage work. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 (#315), repo-template#27 (#348), Shyden's key (#308).
