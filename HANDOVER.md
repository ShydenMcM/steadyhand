# Handover: steadyhand

**Updated:** 2026-10-20 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (`746c0e1` when written, #330). Merge green PRs into `develop` without asking; never `main`. No pull request was open when written but this handover's.
- `docs-handover-2026-10-20e`: this file, worktree `../steadyhand-handover`, one docs commit. #357 and #360 (earlier handovers) are closed unmerged.
- Local branches kept by choice: `203/spec-amendment-wip`, `ext/s3b-guards` (#222 WIP). These can go once each tip is checked against its merged or closed PR head: `287/node-26` (#358), `docs-handover-2026-10-20b`/`c`/`d` (#356, #357, #360), `349/dependabot-groups` (#352), `350/typescript-major` (#355).

## Done this session (2026-10-20)
- **Dependabot:** #335, #332, #331, #330 merged, each green on its tested head (`--match-head-commit`). None open.
- **#287 closed (Node 26), PR #358 merged (`2b3614e`).** `.nvmrc` `26`; all six setup-node steps read it (`node-version-file`). The develop push run logged `Resolved .nvmrc as 26`, `node: v26.12.0`, push-only `deploy-dev` included. `engines` `^24.16.0 || >=26.3.0` (24 for Dependabot's npm updater); `@types/node` 26.6.5. Guards: `test_supply_chain.py`, `test_extension_ci.py`, `tests/repo/test_mutations_ci.py`, `extension/tests/workspace.test.ts`. `mutations/287.toml` 11 of 11. CPU 26 vs 24 within noise. Three extension floors grew by the new test (recorded by CI, fetched).
- **#359 filed** (issue forms: story.yml per repo-template#20, guard, open-board sweep), Estimate 3, Todo.

## Resume steps
1. Run `ListAgents`. No subagents were started.
2. Merge this handover PR when green (docs fast path), then `git worktree remove ../steadyhand-handover`.
3. Next: **#272** (5, Python floors, including #323's five). Read its ACs again on develop first.
4. When Shyden has made #308's key: build the daily workflow (environment allowing `main` only, `--ref main` dispatch, a pin test, a planted mismatch that opens an issue).

## Waiting on Shyden
- **#308's read-only key** (branch-protection read).

## Next on the clean-up queue (all before #222)
- **#272** (5), **#348** (5, P1, SonarCloud blocking, waits on repo-template#27), **#308** (2, waits on the key), **#315** (2, board Priority, blocked by repo-template#6), **#317** (5, orphan check in the PR gate), **#320** (2, README for the extension direction), **#337** (3, blocker links), **#336** (5, logs suite, before #245), **#341** (2, login name out of the paper audit), **#359** (3, issue forms). #339 and #345 are post-release.

## Lessons this session
- A floor guard in another language's suite counts what a change adds: grep `extension/tests` as well as `tests/` before predicting which guards a change touches (the engines pin and three floors were missed until CI).
- A mutation anchor that quotes an action pin breaks when Dependabot bumps the pin: recount anchors after every merge of develop.

## Raised with Shyden
- Global hook false positives, for a dedicated `~/.claude` session: `~/.claude/hook-false-positives-2026-10-13.md`. Item 3 (`disguised-waits.py` matching `-f` across commands) recurred 2026-10-20: `tail -c 100; ... --field-id` refused as `tail -f`.

## Progress (2026-10-20, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` tickets left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points), none in the last 7 days. Board open: 35 tickets, 197 points across 34 scored (epic #214 unscored). Closed 2026-10-13 to 2026-10-20: 8 tickets, 35 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-19, low confidence:** 34 open scored tickets at 1.14 a day is about 30 days.
- **By effort: 197 points remaining across 34 scored open tickets. ETA 2026-11-29, low confidence:** 5.0 points a day is about 40 days.
- **Assumed:** this week's pace (clean-up, CI and test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315, repo-template#27 for #348, Shyden's key for #308.
