# Handover: steadyhand

## Morning list (Shyden)

Nothing needs you this morning. No PR waits on you, no release is cut, and nothing waits on a sudo prompt or upload.
1. FYI only (0 min): picomatch GHSA-fc5q-39xc-vjpf is excepted in CI until 2026-12-01 by your ruling (#586). If no fix ships by then, CI goes red on purpose and you'll be asked what to do.

**Updated:** 2026-11-18 02:57 WIB (overnight session, run on the peer relay "keep working all night"). Current state only. Older history: `git show 5cd0c07:HANDOVER.md`.

**Done tonight:**
- **#581 (P0) closed:** the guards parse once (no emit). Slowest single guard on CI 1,842 ms (was 3,011). PR #585, squash c965536.
- **#586 (P0) filed, exception landed in the same PR #585:** `npm run audit -- "$(date -u +%F)"` (`extension/audit.ts`). PR #587 was closed in favour of #585, because each fix needed the other to go green. #586 stays **open (Todo)** for AC4: remove the exception when picomatch ships a fix.
- **#584 closed:** English only. PR #588, squash 93aec9a. Browser suite: 6/6 on Chromium, Chrome and Edge.
- Memory: `feedback-tooling-takes-the-date-from-its-caller`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here.

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

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

- `develop` = 93aec9a (read with `git rev-parse origin/develop`). No feature branches or worktrees open; no open PRs except handover PR #562 (this branch).
- Backups (keep 30 days): `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06), `377/wip-backup-2026-10-28` (to 2026-11-27), `365/exact-values-backup-2026-10-27` (to 2026-11-26) and `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29). Never copy or replay from the slip backups. Local `239/settings-history-lessons` (c4bebaf): leave alone.

## Running

- Nothing. No waiter, no subagents, no Colima, simulator or USB claims (steadyhand needs none).

## Next steps

1. **Every session start:** run the picomatch check (`~/.claude/global-rules/picomatch-audit-exception-check.md`). If a patched version exists: update the lockfile, delete the entry in `extension/audit.ts` `EXCEPTIONS` and its tests (tests first: the "matches nothing" test goes red when the fix lands), prove audit clean on CI, close #586.
2. Open board (6 tickets, 26 points): #242, #243, #245 wait on Shyden's broker account; #579 waits on shyden-labs/playwright-devices#16 and #17; #586 waits on upstream picomatch; #214 is the epic (Estimate 0 on purpose). Nothing is workable until one of those clears: check them first.
3. When shyden.co.uk PR #1175 (Node 26.13.1) merges, align steadyhand's Node pin (skill `aligning-versions-across-projects`).
4. Local unit runs time out at 1 s under heavy machine load (load 120-170 tonight from other sessions); per #542 CI judges. Focused file runs passed.

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe ("steadyhand: the road to the first release"), v44 (2026-11-18 02:57 WIB). Source: `.superpowers/sdd/progress-page/steadyhand-road-to-release.html` (publish from there). Refresh steps: `.superpowers/sdd/estimates/progress.py` and `stories.py`, then republish with the date and time and a "Changed since the last update" list.

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; read open `docs/handover-*` PRs before asking Shyden anything (memory `feedback-newest-handover-may-be-in-a-pr`).
2. #242/#243/#245 parked on the broker account. Merge rule: squash into develop when every check is green on the head SHA; read the browser suite's per-browser totals. `pr-verdict.sh` returns at once before CI registers: loop it (memory `reference-pr-verdict-no-runs-yet`).
3. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage. Read a gate's `exit=` line, and grep `Errors|Unhandled`.
4. Filing a ticket: project id `PVT_kwHOCQ_jzM4BkhEb`, Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.

## Notes

- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. A new worktree needs `npm ci` in `extension/` before its first push, in a separate call from the `worktree add`.
