# Handover: steadyhand

**Updated:** 2026-11-16 07:0x WIB. Resumed 06:30 WIB on "please continue" (relayed by repo-template-41). The weekly clean-up PR #576 (removes unused `scripts/run_tool.py`) was ticketed as **#577** (P4, 1 point) and squash-merged into develop as 98bb0b1 (every check green on head d9c3cac; `git grep -iE "run_tool|ToolError"` on develop finds nothing). Develop's run 43775335922 on 98bb0b1 was green on all 12 jobs; **#577 closed** with evidence per AC (Done, 1 point). Branch `cleanup/weekly-2026-11-15` already deleted on GitHub. Batch 6 picked offline at 06:5x WIB: `batch-6.json`, 10,005 chars as sent, everything left (0 remaining); at 15:00 read the ledger, re-run `lessons-json.py` + `pick-batch.py` only if drafts changed, then `readback.py`. Physical devices unavailable (Shyden via repo-template-41, 2026-11-16): park device work; steadyhand has none (desktop extension). Earlier (01:00 WIB): Shyden asleep: keep working, park every question here, no main merges or production. Batch 5 read back on the 2026-11-15 Google day (51 lines, every pair read), merged; 10 lessons built and pushed (4efc97c): **33 of 40 built**. 7 paragraphs in 5 lessons reworded after a wrong read-back, 2 of them twice; not read back yet. Google day 2026-11-15 used 15,977. The 2026-11-14 day was lost to a script defect, since fixed (see #251 comment 6898543556). Current state only. Older history: `git show 4c29764:HANDOVER.md`.

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
- `251/indonesian-lessons` (pushed, WIP, red on purpose; worktree `../steadyhand-251`, `npm ci` done): develop merged in (7dfcec2, panel.test.ts conflict kept both sides), then 3b1b496 builds 14 more read-back lessons: **33 of 40 built** (4efc97c; evidence on #251, comment 6898543556). Unit red only by the 17 missing imports in `lessons-id.ts` plus 1 s timeouts under load. Drafts in `.superpowers/sdd/251-indonesian/lessons-id/*.txt`; build a chosen set with `python3 -I build-some.py ../steadyhand-251 <lesson ...>`, then `npx prettier --write` the id folder; find what is ready with `python3 -I ready.py` in that folder.
- Backups (keep 30 days): `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06), `377/wip-backup-2026-10-28` (to 2026-11-27), `365/exact-values-backup-2026-10-27` (to 2026-11-26) and `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29). Never copy or replay from the slip backups. Local `239/settings-history-lessons` (c4bebaf): leave alone.

## #251 Indonesian: where the read-back stands

- Writer: Claude. Reader: Google Cloud Translation via `readback.py <lines.json> <out.tsv>` in `.superpowers/sdd/251-indonesian/` (shared ledger; the Google day turns at 15:00 WIB). Another project shares the ledger: on 2026-11-11 (Pacific) about 10,700 were used elsewhere; read the ledger before planning.
- 2026-11-12 morning: panel-254 (5 lines) read back and committed; batch 2 (the 9 fixed paragraphs of broker.reading, costs.trading, dividends.basics, idx.auto_reject, idx.sessions, income.calendar) read back, every pair read, merged with `merge-tsv.py`. "Kemerataan" read back as "Equity", so it is now "Kemerataan pembayaran" ("Payment evenness"), read back again.
- After a draft edit: `python3 lessons-json.py lessons-id.json` before `pick-batch.py`, or the change is not seen.
- **2026-11-13 Google day (Pacific), 15,786 of 16,000 used:** `advice-id.json` read back (29 lines); 4 fixed (`hari ini` meant the advice day, not today, in noOrders and stampDuty; projectionNothing; readAgainReason colon) and read back clean; merged into `advice-readback.tsv`. Lesson batch 4 (11 lessons, 65 paragraphs: income.goal/growth/projection/run_rate, orders.not_tradable, risk.drawdown/limits/returns, shares.basics/prices, start.explanations) read back, every pair read, merged into `lessons-readback.tsv`. 7 paragraphs then fixed in the drafts (income.growth#3, risk.returns#4, shares.basics#4, shares.prices#0/#4/#5, start.explanations#2) and NOT yet read back: pick-batch sees them as changed.
- **Queue for the next Google day (turns 15:00 WIB 2026-11-16):** `python3 -I lessons-json.py lessons-id.json`, then `python3 -I pick-batch.py 15900 batch-6.json` (everything left, about 9,700 as sent: strategies.dividend_growth, high_yield, low_volatility, momentum_rotation, total_return, tax.dividend, tax.exemption), `python3 -I readback.py batch-6.json batch-6.tsv`, read every pair against `../steadyhand-251/extension/packages/shell/lessons/<name>.md`, merge with `merge-tsv.py`, `python3 -I ready.py`, build with `build-some.py /Users/shyden/Developer/Repos/steadyhand-251 <lessons>` (absolute path), `npx prettier --write packages/shell/lessons/id`. When all 40 are in, the branch goes green: open the PR. Backups: `lessons-id.before-batch5-fixes-2026-11-16.tgz`, `lessons-readback.before-batch5.tsv`, the pre-fix scripts `*.before-*-2026-11-14.py`.
- **Build only drafts whose every paragraph is read back** (memory `feedback-build-only-read-back-drafts`).

## Running
- Nothing. The waiter for the 15:00 WIB Google day turn was stopped for the laptop shutdown: DEAD. Re-run: after 15:00 WIB 2026-11-16 (when `TZ=America/Los_Angeles date +%F` prints 2026-11-16), run the #251 queue above from `.superpowers/sdd/251-indonesian/`. Colima not held; no subagents.
- Branches: `251/indonesian-lessons` at 4efc97c, pushed, everything committed (worktree `../steadyhand-251`). This branch (`docs/handover-2026-11-11-restart`) carries this file.
- Parked questions for Shyden: none.

## Next steps

1. #251 read-back (queue above) once the Google day turns, 15:00 WIB 2026-11-16; read the ledger first (another project shares it). Then build the read-back drafts on `251/indonesian-lessons`.
2. First release: 24 of 27 stories; #242, #243, #245 (21 points) wait on Shyden's broker account. #252, #253, #257, #258 wait on the readers; #553 on #251.

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe ("steadyhand: the road to the first release"). Refresh steps: `.superpowers/sdd/estimates/progress.py` and `stories.py`, then republish with the date and time and a "Changed since the last update" list.

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; read open `docs/handover-*` PRs before asking Shyden anything (memory `feedback-newest-handover-may-be-in-a-pr`).
2. #242/#243/#245 parked on the broker account. Merge rule: squash into develop when every check is green on the head SHA; read the browser suite's per-browser totals. `pr-verdict.sh` returns at once before CI registers: loop it (memory `reference-pr-verdict-no-runs-yet`).
3. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage. Read a gate's `exit=` line, and grep `Errors|Unhandled`.
4. Filing a ticket: project id `PVT_kwHOCQ_jzM4BkhEb`, Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.

## Notes

- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. A new worktree needs `npm ci` in `extension/` before its first push, in a separate call from the `worktree add`.
