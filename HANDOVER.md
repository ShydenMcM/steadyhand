# Handover: steadyhand

**Updated:** 2026-11-17 20:10 WIB. #251 batch 7 read back (3 lines, every pair read, merged; 0 lesson paragraphs left unread), built and pushed as 6454cdc; **PR #580** open into develop. Its CI: every required check green except `extension-guards`: "no extension file mocks a module" timed out at 5230 ms (develop: 3011 ms). Measured cause: the runner was ~1.7x slow on all 12 guards timed in both runs; the guards sit at 45-60% of the 5 s limit. Filed **#581** (P0, 3 points, Todo; #251 now blocked by it on GitHub); AC1 profile posted on #581. Progress page v42 published 20:05 WIB. Local unit run of 6454cdc at load 33: 13 timeouts in rules/panel tests (not quiet; #542 ruling, CI judges). Current state only. Older history: `git show a40c835:HANDOVER.md`.

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
- **#251 scope:** Indonesian ships with core's notes, refusals and strategy reasons in English; translating them is #553 (P4, 8 points, blocked by #251).
- **#251 AC4 (23:2x WIB):** "no manual reviews, just complete it": no fluent human reader; the Google read-back of every line is the review (recorded on #251).
- **#254:** spec §9.1 approved: optional Settings field "Monthly amount you add, in rupiah" (blank = 0); the projection shows under Income goal on the Advice tab.
- **#255/#256:** the user enters each purchase that reinvests a dividend (a form in the panel).

## Branches and PRs

- **#256 shut** 2026-11-13 ~23:2x WIB: PR #575 squash-merged into develop as 159c8cd (every required check green on 996ca7b; browser 6/6 on Chromium, Chrome, Edge; CI run 43462803816). Evidence per AC on #256; worktree and branch removed. Session logs: `.superpowers/sdd/256/`.
- **#573 closed** 2026-11-13 18:1x WIB: PR #574 squash-merged into develop as 872d53a (every required check green on head 715d3e1). Red-first re-measured (old line: 1 failed, 143 passed; new: 144 passed; logs in `.superpowers/sdd/573/`); evidence per AC on #573. Worktree `../steadyhand-544` and branch removed (local and remote).

- `develop`: read with `git rev-parse origin/develop`.
- Merged 2026-11-13: #571 (#570 P0, extension integration builds once, proven by strace and per-test assertion counts; 083ccf8). #568 P0 is done: runner counts on CI (probe PR #569, shut unmerged; run 43383498799) prove that the earlier journey merge kept every check. Shyden ruled: keep the 5 browser journeys (shared opening only). `testpypi` environment deleted on his choice (dev-deploy rule); `dev` already allows all branches.
- Also merged 2026-11-13: #565 (#255 core claims, parity harness, `tax.exemption` lesson; 1954940), #567 (#566 P0 soupsieve CVE, closed with evidence), #564 (Dependabot).
- Merged 2026-11-13 14:5x WIB: **#572** (squash 4a8e0bd): the #255 Settings switch and Tax tab. CI run 43388166515 all green, browser 6/6 on Chromium, Chrome, Edge. **#255 closed** with every AC checked (comment on #255). Worktree `../steadyhand-255b` and branch removed. Dropped on purpose: "unticking while on Tax opens Advice" (unreachable: the checkbox is on Settings).
- `251/indonesian-lessons` at 6454cdc, pushed, PR #580 (merge state BEHIND develop; worktree `../steadyhand-251`).
- Backups (keep 30 days): `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06), `377/wip-backup-2026-10-28` (to 2026-11-27), `365/exact-values-backup-2026-10-27` (to 2026-11-26) and `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29). Never copy or replay from the slip backups. Local `239/settings-history-lessons` (c4bebaf): leave alone.

## #251 Indonesian: where the read-back stands

- Writer: Claude. Reader: Google Cloud Translation via `readback.py <lines.json> <out.tsv>` in `.superpowers/sdd/251-indonesian/` (shared ledger; the Google day turns at 15:00 WIB). Another project shares the ledger: on 2026-11-11 (Pacific) about 10,700 were used elsewhere; read the ledger before planning.
- 2026-11-12 morning: panel-254 (5 lines) read back and committed; batch 2 (the 9 fixed paragraphs of broker.reading, costs.trading, dividends.basics, idx.auto_reject, idx.sessions, income.calendar) read back, every pair read, merged with `merge-tsv.py`. "Kemerataan" read back as "Equity", so it is now "Kemerataan pembayaran" ("Payment evenness"), read back again.
- After a draft edit: `python3 lessons-json.py lessons-id.json` before `pick-batch.py`, or the change is not seen.
- **2026-11-13 Google day (Pacific), 15,786 of 16,000 used:** `advice-id.json` read back (29 lines); 4 fixed (`hari ini` meant the advice day, not today, in noOrders and stampDuty; projectionNothing; readAgainReason colon) and read back clean; merged into `advice-readback.tsv`. Lesson batch 4 (11 lessons, 65 paragraphs: income.goal/growth/projection/run_rate, orders.not_tradable, risk.drawdown/limits/returns, shares.basics/prices, start.explanations) read back, every pair read, merged into `lessons-readback.tsv`. 7 paragraphs then fixed in the drafts (income.growth#3, risk.returns#4, shares.basics#4, shares.prices#0/#4/#5, start.explanations#2) and NOT yet read back: pick-batch sees them as changed.
- **Done 2026-11-17:** batch 7 read back (ledger 2026-11-17: 3491 after it), merged into `lessons-readback.tsv` (backup `lessons-readback.backup-2026-11-17-1950.tsv`), built, committed 6454cdc. #251 AC check done in session: AC2/AC3/AC5 evidenced on PR #543; AC7-9 read-backs say the same as the English; AC4 replaced by Google read-back (Shyden 2026-11-11). AC6 waits on #580's CI after #581.
- **Build only drafts whose every paragraph is read back** (memory `feedback-build-only-read-back-drafts`).

## Running
- Nothing. No simulator, Colima or USB claims held (steadyhand never needs them). No waiter, no subagents. The artifact live-watch on the progress page dies with the session (harmless).
- Branches: `251/indonesian-lessons` at 6454cdc (PR #580, worktree `../steadyhand-251`). This branch (`docs/handover-2026-11-11-restart`) carries this file.
- Parked questions for Shyden: none.

## Next steps

1. **#581 (P0)**: fresh branch `581/guards-parse-once` off develop. Fix found and trialled (AC1 comment on #581; script `.superpowers/sdd/581/profile.mts`): `parse` in `extension/tests/lib/source.ts` runs `ts.transpileModule` (an emit, ~78% of readSource) only for syntax errors; parse once with `createSourceFile` and take `program.getSyntacticDiagnostics` from a one-file program (noLib, noResolve) = 307 vs 1268 ms over 179 files, same codes on 5 broken inputs. Test first (red), keep per-guard test counts equal, CI log must show the slowest guard <= 2,000 ms (AC3).
2. Then merge develop into `251/indonesian-lessons`, push, read #580's verdict (loop `pr-verdict.sh` until nothing is in_progress/queued/MISSING), squash-merge if every check is green, close #251 with per-AC evidence by hand, clean its worktree and branches.
3. First release: 24 of 27 stories; #242, #243, #245 (21 points) wait on Shyden's broker account. #252, #253, #257, #258, #578 (Stockbit) wait on the readers; #553 on #251. Later features: 5 of 12 closed, 56 points open.
4. When shyden.co.uk PR #1175 (Node 26.13.1) merges, align steadyhand's Node pin (skill `aligning-versions-across-projects`).

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe ("steadyhand: the road to the first release"), v42. Source: `.superpowers/sdd/progress-page/steadyhand-road-to-release.html` (publish from there). Refresh steps: `.superpowers/sdd/estimates/progress.py` and `stories.py`, then republish with the date and time and a "Changed since the last update" list.

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; read open `docs/handover-*` PRs before asking Shyden anything (memory `feedback-newest-handover-may-be-in-a-pr`).
2. #242/#243/#245 parked on the broker account. Merge rule: squash into develop when every check is green on the head SHA; read the browser suite's per-browser totals. `pr-verdict.sh` returns at once before CI registers: loop it (memory `reference-pr-verdict-no-runs-yet`).
3. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage. Read a gate's `exit=` line, and grep `Errors|Unhandled`.
4. Filing a ticket: project id `PVT_kwHOCQ_jzM4BkhEb`, Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.

## Notes

- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. A new worktree needs `npm ci` in `extension/` before its first push, in a separate call from the `worktree add`.
