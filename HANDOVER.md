# Handover: steadyhand

## Shyden's answers (2026-11-24)

- **#595 (#579 AC2):** keep the local one-suite guard, narrowed: drop only its `.skip`/`.fixme` patterns (the shared checks fail a skipped status); keep `test.fail`, `test.slow` and the config/command filters, which the shared checks cannot see (read from 0.1.5 `check.js`; recorded on #595). First answered "test.fail only", re-asked after the read found two more gaps.

## Open with Shyden

- Dependabot #600 (vitest group) and #601 (npm minor/patch) are green (6/6/6, 0 skipped) but BEHIND develop after #599 merged; my `@dependabot rebase` comment was refused by the auto-mode classifier. Shyden: comment `@dependabot rebase` on each (or allow it), then they merge on green.

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

- `develop`: 05cf5af (read 2026-11-24 19:44 WIB), Dependabot #599 (setup-uv 10.4.0) squash-merged, CI green 6/6/6 on its head.
- #579 and #595 closed 2026-11-24 with evidence (probes #597, #598; run 45354973082: 6/6/6, 0 skipped). Their branches, worktrees and probe branches are removed.
- Handover PR #562 (this branch). Backups (keep 30 days): `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06), `377/wip-backup-2026-10-28` (to 2026-11-27), `365/exact-values-backup-2026-10-27` and `-10-28` (to 2026-11-26/27). Local `239/settings-history-lessons`: leave alone.

## Running

- Nothing running (2026-11-24 19:50 WIB close-out; weekly cleanup done, logged in reference-cleanup.md): no subagents, waiters, Colima, simulator or USB claims; nothing DEAD to re-run. One worktree (this one).
- Board 2026-11-24: EXT first release 24 of 27 stories, 21 points left; open #214 (epic), #242, #243, #245, all waiting on Shyden's broker account.

## Next steps

1. #242/#243/#245 wait on the broker account; #214 is the epic. Nothing workable until the account exists: check the board for new tickets by Priority (`board-next`) first.
2. Refresh the progress page (below) at every close-out.

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe, v57 (2026-11-24 19:44 WIB, Dependabot #599 merged). Source: `.superpowers/sdd/progress-page/steadyhand-road-to-release.html`. Refresh: `.superpowers/sdd/estimates/progress.py` and `stories.py`, then republish with date, time and "Changed since the last update".

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; read open `docs/handover-*` PRs before asking Shyden anything (memory `feedback-newest-handover-may-be-in-a-pr`).
2. #242/#243/#245 parked on the broker account. Merge rule: squash into develop when every check is green on the head SHA; read the browser suite's per-browser totals. `pr-verdict.sh` returns at once before CI registers: loop it (memory `reference-pr-verdict-no-runs-yet`).
3. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage. Read a gate's `exit=` line, and grep `Errors|Unhandled`.
4. Filing a ticket: project id `PVT_kwHOCQ_jzM4BkhEb`, Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.

## Notes

- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. A new worktree needs `npm ci` in `extension/` before its first push, in a separate call from the `worktree add`.
