# Handover: steadyhand

## Shyden's answers (2026-11-27)

- **Broker account (01:4x WIB, before going AFK for over a day):** not ready. Keep idle checks only when woken (no clock-driven polling). #242/#243/#245 stay parked.

## Shyden's answers (2026-11-24)

- **#595 (#579 AC2):** keep the local one-suite guard, narrowed: drop only its `.skip`/`.fixme` patterns (the shared checks fail a skipped status); keep `test.fail`, `test.slow` and the config/command filters, which the shared checks cannot see (read from 0.1.5 `check.js`; recorded on #595). First answered "test.fail only", re-asked after the read found two more gaps.

## Open with Shyden

- Dependabot #600 and #601 squash-merged 2026-11-25 (da0bc298 at 06:40 WIB; f314f29c at ~06:50 WIB), each on a rebased head with every required check success and browsers 6/6/6, 0 skipped. Nothing open with Shyden. develop CI read green on both merge commits (ci: success).

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

## In flight: cleanup (2026-11-28 02:50 WIB, asked by repo-template: "cleanup is extremely important everywhere")

- #602 done: PR #604 squash-merged as 53017c3 (every required check green on e8f9607a); shut by hand with evidence per AC; branch removed. develop CI green on 53017c3.
- #603 (P0, 2 pt, In Progress): journeys left `profile` + `extension` in `test-results/`. Draft PR #605, branch `603/journey-output-cleanup`, worktree `../steadyhand-603`. Red on CI by name (run 46057143406: 5 journeys failed on chromium on the afterEach checks). Fix pushed (rm both in `withPanel`'s finally; head in `.superpowers/sdd/603-green-sha`). Green on 8796d997 (run 46057872748: every required check, 6/6/6 passed, 0 skipped); branch then updated from develop (merge, head c4441178 in `.superpowers/sdd/603-green-sha`): read green again on that head before merging. AC3 proven by probe PR #606 (run 46058104971: artifact 10 files, screens + error-context, no profile/extension); probe shut, branch and worktree removed; evidence on #603. Then merge #605 and shut #603 by hand with evidence.
- Strays removed: `probe506/`, old `dist/`. Other temp sites already clean (vitest mkdtemp + rm, TemporaryDirectory, mkstemp unlink, no containers).
- Waiters (DEAD at /clear): pr-verdict loop on 605; re-run `~/.claude/scripts/pr-verdict.sh <pr>` in a loop (it returns at once before CI registers).
- The commit security-review plugin got HTTP 401 (log `~/.claude/security/log.txt`): told Shyden.

## Branches and PRs

- `develop`: f314f29 (read 2026-11-25 14:06 WIB), after Dependabot #600 and #601; no open PR but this one.
- #579 and #595 closed 2026-11-24 with evidence (probes #597, #598; run 45354973082: 6/6/6, 0 skipped). Their branches, worktrees and probe branches are removed.
- Handover PR #562 (this branch). Backups (keep 30 days): `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06); `377/wip-backup-2026-10-28` and `365/exact-values-backup-2026-10-28` deleted 2026-11-28 after their 30 days. Local `239/settings-history-lessons`: leave alone.

## Running

- 2026-11-28 02:50 WIB: no subagents, Colima, simulator or USB claims. Worktrees: main (develop), `../steadyhand-603`, `../steadyhand-handover` (this branch).
- Board 2026-11-25 (read live): EXT first release 24 of 27 stories, 21 points left; open #214 (epic), #242, #243, #245, all waiting on Shyden's broker account. Every post-launch story open (#252, #253, #257, #258, #578) is also blocked through #242/#243, so nothing is workable. Checks at 14:06, 15:30, 21:31, 23:27 WIB (25 Nov) , 05:09 and 06:26 WIB (26 Nov; 06:26 after repo-template relayed "continue, no devices") (progress.py re-read, open issues and PRs listed, develop CI green on f314f29) found nothing new: nothing to build. 27 Nov 18:44 WIB: repo-template relayed "real devices connected via USB"; irrelevant (desktop Chrome extension, no mobile surface); board unchanged (24/27, 21 points). 28 Nov 01:47 WIB: night check, board unchanged (24/27, 21 points), develop CI green on f314f29.

## Next steps

1. #242/#243/#245 wait on the broker account; #214 is the epic. Nothing workable until the account exists: check the board for new tickets by Priority (`board-next`) first. Next backup expiry: `239/slip-backup-2026-11-06` from 2026-12-06.
2. Refresh the progress page (below) at every close-out.

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe, v73 (2026-11-28 02:39 WIB: test runs clean up after themselves). Source: `.superpowers/sdd/progress-page/steadyhand-road-to-release.html`. Refresh: `.superpowers/sdd/estimates/progress.py` and `stories.py`, then republish with date, time and "Changed since the last update".

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; read open `docs/handover-*` PRs before asking Shyden anything (memory `feedback-newest-handover-may-be-in-a-pr`).
2. #242/#243/#245 parked on the broker account. Merge rule: squash into develop when every check is green on the head SHA; read the browser suite's per-browser totals. `pr-verdict.sh` returns at once before CI registers: loop it (memory `reference-pr-verdict-no-runs-yet`).
3. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage. Read a gate's `exit=` line, and grep `Errors|Unhandled`.
4. Filing a ticket: project id `PVT_kwHOCQ_jzM4BkhEb`, Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.

## Notes

- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. A new worktree needs `npm ci` in `extension/` before its first push, in a separate call from the `worktree add`.
