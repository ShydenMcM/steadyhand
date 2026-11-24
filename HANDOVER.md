# Handover: steadyhand

## Shyden's answers (2026-11-24)

- **#595 (#579 AC2):** keep the local one-suite guard, narrowed: drop only its `.skip`/`.fixme` patterns (the shared checks fail a skipped status); keep `test.fail`, `test.slow` and the config/command filters, which the shared checks cannot see (read from 0.1.5 `check.js`; recorded on #595). First answered "test.fail only", re-asked after the read found two more gaps.

## Open with Shyden

- Nothing.

## Shyden's answers (2026-11-14)

- #339 and #345 shut as not planned (their repo-template designs were cancelled 2026-10-30; the extension logs nothing; the Python paper account stays the frozen reference).

## Shyden's answers (2026-11-13)

- **#256 (18:2x WIB):** the exemption report shows on the Tax tab, below the claims list (recorded on #256). Shyden is AFK, possibly for days: keep working by Priority; keep this file current for compaction.
- #544, #546 (and #548, same handling): AC3 (the Indonesian lesson) moved to #251 as its AC7, AC8, AC9; the three tickets shut with evidence on each. No questions open.

- Repeated journeys: keep the 5 browser journeys (only their opening repeats); re-prove the earlier merge with runner counts (done, #568). Proof is always measured by the runner, never asked about (CLAUDE.md 2026-11-13).
- Delete the unused `testpypi` environment (done).

## Shyden's answers (2026-11-10)

- **#255 design (2026-11-12, recorded on #255):** exemption switch is a Settings checkbox, off by default; a new Tax tab holds the dividends-received form, the purchases form and the claims list; the deadline counts from the tax year the dividend was received, not the ex-date.
- **#255 (2026-11-11):** route (a): the user enters each dividend received (date, stock, gross) in a form beside the purchases form (recorded on #255). Spec §9.2 can be drafted.
- **Clean-up (2026-11-11):** remote branches `308/release-checklist` and `docs/handover-2026-10-29d` deleted.

- **#542:** no test rewrite; CI judges, the local unit gate runs only on a quiet machine. Closed not planned.
- **#254:** spec §9.1 approved: optional Settings field "Monthly amount you add, in rupiah" (blank = 0); the projection shows under Income goal on the Advice tab.
- **#255/#256:** the user enters each purchase that reinvests a dividend (a form in the panel).

## Branches and PRs

- `develop`: read with `git rev-parse origin/develop` (eb8979b on 2026-11-22).
- **#579 In Progress, attempt 3**: branch `579/shared-playwright-devices-3`, worktree `../steadyhand-579c`, from develop 81cd465. Tests commit 0bf59fe (unit red seen locally: the range test, the config test, 5 integration-CI pins; the other reds were 1 s timeouts under load). Pushed as draft PR #596; CI run 45051675866 read every new test red by name, and nothing else (coverage only downstream). Code commit bea543f (unit suites green: 4360 extension, 124 Python repo; static checks clean), pushed to PR #596. Its CI run 45052602463 failed the browser suite on Chromium, 5 of 6 journeys: `launchPersistentContext: "deviceScaleFactor" option is not supported with null "viewport"` (the shared projects carry Playwright's desktop descriptors; the journeys open a real window). Fixed test first: `tests/tool-configs.test.ts` expects each project kept to its name and channel (seen red), then `playwright.config.ts` maps each shared project to `{ ...project, use: channel ? { channel } : {} }` (tsc, eslint clean; local unit failures were 1 s timeouts in untouched shell/core files under load). Fix commit 45a2a73: PR #596 fully green (run 45055246806; 6/6/6 tests per browser; evidence on #579). Probe PR #597 done and closed (run 45055941975): the shared checks caught the skip, the dropped test and the untagged group test, and let a failing `test.fail()` through; recorded on #595 and #579; branch and worktree removed. PR #596 stays a draft until #595 is ruled (AC2's guard deletion). Probe branch `579/probe-one-suite-3` (worktree `../steadyhand-579-probe3`) built on bea543f with the plants: push it as a draft PR if not yet pushed, read each one-suite problem line, then close it and delete branch and worktree. Tests: `extension/tests/workspace.test.ts` (exact pins except playwright-devices, which must be `>=x.y.z`), `extension/tests/tool-configs.test.ts`, `extension/tests/browser/journey.spec.ts`, `tests/guards/test_supply_chain.py` (`@playwright/test` peer ceiling), `tests/repo/test_integration_ci.py`; package.json/lock hold 0.1.5 exact as the compile stub. Next: read every new test red by name on the draft PR's CI run, then write the code fresh (steps in Next steps; never copy from the closed attempts), then the probe.
- Attempts 1 and 2 closed 2026-11-22 as TDD slips: PR #591 (+ probe #592), ci.yml changed before `tests/repo/test_integration_ci.py`; PR #593, the `>=` range before `workspace.test.ts`'s exact-pin test. Branches deleted; never replay from them.
- Handover PR #562 (this branch). Backups (keep 30 days): `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06), `377/wip-backup-2026-10-28` (to 2026-11-27), `365/exact-values-backup-2026-10-27` and `-10-28` (to 2026-11-26/27). Local `239/settings-history-lessons`: leave alone.

## Running

- 2026-11-24 15:15 WIB: CI on PR #596 (d8343e8) and probe #598 running. Local waiter dies with this session: DEAD; re-run `~/.claude/scripts/pr-verdict.sh 596` and `598` (loop until runs settle). No subagents, Colima, simulator or USB claims. Worktree `../steadyhand-579c` (branch `579/shared-playwright-devices-3`, clean).
- Board 2026-11-24: EXT first release 24 of 27 stories, 21 points left; open #214, #242, #243, #245, #579, #595.

## Next steps

1. #586 closed (PR #594 merged, 81cd465).
2. **#579 (#595 ruled 2026-11-24):** tests commit 128336c red on CI exactly as planned (run 45354338718, four new `one-suite.test.ts` cases). Code commit d8343e8 (skip/fixme patterns removed) pushed to PR #596. Probe PR #598 (branch `579/probe-skips-4`, worktree `../steadyhand-579-probe4`) plants `test.fixme`, `test.describe.skip`, a chromium-only `test.skip`: read the "The same tests on every browser" step for a `skipped` line per plant, record on #595/#579, close #598, delete branch and worktree. Then PR #596 ready, merge on green head, close #595 and #579 with evidence, clean the 579c worktree and branch.
3. Rest of board: #242/#243/#245 wait on Shyden's broker account; #214 epic.
4. Refresh the progress page (below) at every close-out.

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe, v55 (2026-11-24 15:45 WIB, #579 code pushed, probe #598 on CI). Source: `.superpowers/sdd/progress-page/steadyhand-road-to-release.html`. Refresh: `.superpowers/sdd/estimates/progress.py` and `stories.py`, then republish with date, time and "Changed since the last update".

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; read open `docs/handover-*` PRs before asking Shyden anything (memory `feedback-newest-handover-may-be-in-a-pr`).
2. #242/#243/#245 parked on the broker account. Merge rule: squash into develop when every check is green on the head SHA; read the browser suite's per-browser totals. `pr-verdict.sh` returns at once before CI registers: loop it (memory `reference-pr-verdict-no-runs-yet`).
3. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage. Read a gate's `exit=` line, and grep `Errors|Unhandled`.
4. Filing a ticket: project id `PVT_kwHOCQ_jzM4BkhEb`, Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.

## Notes

- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. A new worktree needs `npm ci` in `extension/` before its first push, in a separate call from the `worktree add`.
