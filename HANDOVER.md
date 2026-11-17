# Handover: steadyhand

## Morning list (Shyden)

Nothing needs you. FYI: picomatch GHSA-fc5q-39xc-vjpf is still unpatched (checked 2026-11-18 06:30 WIB: npm 4.0.7, first_patched_version None); the exception lasts to 2026-12-01 (#586).

**Updated:** 2026-11-18 06:45 WIB, before Shyden's laptop restart. Current state only. Older history: `git show dee262b:HANDOVER.md`.

**This session:** version census (skill `aligning-versions-across-projects`): steadyhand 6 packages behind. Filed **#589** (P3, 2 pts, In Progress); told ShyTalk, playwright-devices, repo-template, shyden.co.uk, shydesk, yawelo-idle sessions their own rows (shydesk filed shydesk#208; repo-template has repo-template#203). shyden.co.uk PR #1175 closed unmerged, but its develop already runs node 26.13.1.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device work.

**Rulings:** keep it simple, value test first (2026-10-30). Standing approval (2026-11-04): squash-merge into develop any PR green on every check on its head.

## Open with Shyden

- Nothing open.

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

- `develop` = 93aec9a (read with `git rev-parse origin/develop`).
- **#589 in flight:** worktree `../steadyhand-589`, branch `589/align-versions`, draft **PR #590**. Pushed: 626b42b (red phase: Node pin test now wants 26.13.1). **Committed locally, NOT pushed:** 1b0a59b (bumps @playwright/test 1.65.1, eslint 10.15.0, prettier 3.10.1, typescript-eslint 8.72.2, vite 8.3.8; lockfile regenerated; format:check, lint, typecheck, audit all exit 0 locally). Dockerfile still 26.13.0: not yet changed.
- CI run 44200621122 on 626b42b: `guards (py3.13)` FAILED as expected, but its log was unreadable while the run was still in progress: confirm the failure is `test_the_node_dockerfile_names_node_26_13_1` and nothing else.
- Handover PR #562 (this branch). Backups (keep 30 days): `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06), `377/wip-backup-2026-10-28` (to 2026-11-27), `365/exact-values-backup-2026-10-27` (to 2026-11-26) and `-10-28` (to 2026-11-27). Never replay from slip backups. Local `239/settings-history-lessons`: leave alone.

## Running

- Nothing local. No waiter, subagents, Colima, simulator or USB claims. Remote CI run 44200621122 may still be running.

## Next steps

1. **Every session start:** picomatch check (`~/.claude/global-rules/picomatch-audit-exception-check.md`).
2. **#589:** read guards log of run 44200621122 (`gh run view --job 134453440272 --log | grep -E 'FAILED|passed|failed'`); confirm only the pin test is red. Then in `../steadyhand-589`: `sed -i '' 's/^FROM node:26.13.0$/FROM node:26.13.1/' docker/node/Dockerfile`, commit (Refs #589), push both commits together, mark PR #590 ready. Merge when every check is green on the head SHA, browser totals equal on Chromium/Chrome/Edge. Re-run the census to prove 0 behind for steadyhand, comment the evidence on #589, close it, clean the worktree and branches.
3. Rest of board: #242/#243/#245 wait on Shyden's broker account; #579 waits on shyden-labs/playwright-devices#16/#17; #586 waits on upstream picomatch; #214 epic.
4. Refresh the progress page (below) at every close-out.

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe, v45 (2026-11-18 06:47 WIB). Source: `.superpowers/sdd/progress-page/steadyhand-road-to-release.html`. Refresh: `.superpowers/sdd/estimates/progress.py` and `stories.py`, then republish with date, time and "Changed since the last update".

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; read open `docs/handover-*` PRs before asking Shyden anything (memory `feedback-newest-handover-may-be-in-a-pr`).
2. #242/#243/#245 parked on the broker account. Merge rule: squash into develop when every check is green on the head SHA; read the browser suite's per-browser totals. `pr-verdict.sh` returns at once before CI registers: loop it (memory `reference-pr-verdict-no-runs-yet`).
3. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage. Read a gate's `exit=` line, and grep `Errors|Unhandled`.
4. Filing a ticket: project id `PVT_kwHOCQ_jzM4BkhEb`, Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.

## Notes

- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. A new worktree needs `npm ci` in `extension/` before its first push, in a separate call from the `worktree add`.
