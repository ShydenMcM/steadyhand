# Handover: steadyhand

**Updated:** 2026-10-20 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (`3ebd1af` when written, #331). Merge green PRs into `develop` without asking; never `main`.
- `287/node-26`: PR #358, head `07789fa` when written (read `gh pr view 358 --json headRefOid`). Its first push failed only on three extension floors that the new test grew. Recorded by CI, fetched in `83ec8e2`, develop merged in, re-pushed; CI was running.
- `docs-handover-2026-10-20d`: this file, worktree `../steadyhand-handover`, one docs commit. PR #357 (the previous handover) is superseded: close it unmerged.
- Local branches kept by choice: `203/spec-amendment-wip`, `ext/s3b-guards` (#222 WIP). `docs-handover-2026-10-20b`/`c`, `349/dependabot-groups`, `350/typescript-major` can go once each tip is checked against its merged or closed PR head.

## Done this session (2026-10-20)
- **Dependabot:** #335, #332, #331 merged, each green on its tested head (`--match-head-commit`). #330 asked to rebase.
- **#287 (Node 26), PR #358:** `.nvmrc` `26`. All six setup-node steps (ci.yml x4, mutations.yml, record-floors.yml; the ticket said two, corrected on #287) read it with `node-version-file`. `engines` is `^24.16.0 || >=26.3.0` (24 for Dependabot's npm updater). `@types/node` 26.6.5. Guards: `test_supply_chain.py` (nvmrc pin, steps counted two ways = 6, types major = nvmrc), `test_extension_ci.py`, `tests/repo/test_mutations_ci.py`, `extension/tests/workspace.test.ts` (engines in manifest + lock). `mutations/287.toml`: 11 of 11 as predicted on `1cc4540`; anchors then moved to setup-node v7.1.0. Unit mutations U1-U4 red as predicted (laptop). CPU 26 vs 24: +1.8% min, +2.9% worst, heaviest 11 ms; `npm ci` clean on both. Board: #287 In Progress.
- **#359 filed** (issue forms: story.yml per repo-template#20, guard, open-board sweep), Estimate 3, Todo. Clears the old "ticket-filing procedure" item.

## Resume steps
1. Run `ListAgents`. No subagents were started.
2. **#358:** read every required check on the head with `~/.claude/scripts/pr-verdict.sh 358`, then `wait-run.sh` if still running. Merge when green (squash, `--match-head-commit` from a file). Then set #287 Done after reading its ACs against the merge, and close it by hand with a comment.
3. **#330:** merge when all 15 required checks are green on its rebased head. If #358 merged first, `@dependabot rebase` it again.
4. Merge this handover PR (docs fast path); close #357 unmerged; `git worktree remove ../steadyhand-handover`.
5. Next on the queue: **#272** (5, Python floors).
6. When Shyden has made #308's key: build the daily workflow (environment allowing `main` only, `--ref main` dispatch, a pin test, a planted mismatch that opens an issue).

## Waiting on Shyden
- **#308's read-only key** (branch-protection read).

## Next on the clean-up queue (all before #222)
- **#272** (5, Python floors, including #323's five), **#348** (5, P1, SonarCloud blocking, waits on repo-template#27), **#308** (2, waits on the key), **#315** (2, board Priority, blocked by repo-template#6), **#317** (5, orphan check in the PR gate), **#320** (2, README for the extension direction), **#337** (3, blocker links), **#336** (5, logs suite, before #245), **#341** (2, login name out of the paper audit), **#359** (3, issue forms). #339 and #345 are post-release.

## Lessons this session
- A floor guard in another language's suite counts what a change adds: grep `extension/tests` as well as `tests/` before predicting which guards a change touches (the engines pin and three floors were missed until CI).
- A mutation anchor that quotes an action pin breaks when Dependabot bumps the pin: recount anchors after every merge of develop.

## Raised with Shyden
- Global hook false positives, for a dedicated `~/.claude` session: `~/.claude/hook-false-positives-2026-10-13.md`.

## Progress (2026-10-20, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` tickets left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points), none in the last 7 days. Board open: 36 tickets, 200 points across 35 scored (epic #214 unscored). Closed 2026-10-13 to 2026-10-20: 7 tickets, 32 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-24, low confidence:** 35 open scored tickets at 1.0 a day is about 35 days.
- **By effort: 200 points remaining across 35 scored open tickets. ETA 2026-12-03, low confidence:** 4.6 points a day is about 44 days.
- **Assumed:** this week's pace (clean-up, CI and test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315, repo-template#27 for #348, Shyden's key for #308.
