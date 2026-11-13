# Handover: steadyhand

**Updated:** 2026-11-13 15:41 WIB. Current state only. Older history: `git show 4c29764:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here.

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

## Open with Shyden

- Nothing open.

## Shyden's answers (2026-11-13)

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

- **PR #574** (`573/dividend-lesson-exemption`, worktree `../steadyhand-544`, head 715d3e1, read 15:32 WIB) for **#573** (P0, 1 pt, In Progress, filed today): tax.dividend said the exemption is untracked; now points to the next lesson. Test seen red first; unit 144/144. CI was running at 15:32. Indonesian draft `lessons-id/tax.dividend.txt` already changed to match (not read back: #251 AC8).

- `develop`: read with `git rev-parse origin/develop`.
- Merged 2026-11-13: #571 (#570 P0, extension integration builds once, proven by strace and per-test assertion counts; 083ccf8). #568 P0 is done: runner counts on CI (probe PR #569, shut unmerged; run 43383498799) prove that the earlier journey merge kept every check. Shyden ruled: keep the 5 browser journeys (shared opening only). `testpypi` environment deleted on his choice (dev-deploy rule); `dev` already allows all branches.
- Also merged 2026-11-13: #565 (#255 core claims, parity harness, `tax.exemption` lesson; 1954940), #567 (#566 P0 soupsieve CVE, closed with evidence), #564 (Dependabot).
- Merged 2026-11-13 14:5x WIB: **#572** (squash 4a8e0bd): the #255 Settings switch and Tax tab. CI run 43388166515 all green, browser 6/6 on Chromium, Chrome, Edge. **#255 closed** with every AC checked (comment on #255). Worktree `../steadyhand-255b` and branch removed. Dropped on purpose: "unticking while on Tax opens Advice" (unreachable: the checkbox is on Settings).
- `251/indonesian-lessons` (pushed, WIP, red on purpose): 9 of 37 built, now **38** with `tax.exemption` (tell #251). Drafts in `.superpowers/sdd/251-indonesian/lessons-id/*.txt`.
- Backups (keep 30 days): `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06), `377/wip-backup-2026-10-28` (to 2026-11-27), `365/exact-values-backup-2026-10-27` (to 2026-11-26) and `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29). Never copy or replay from the slip backups. Local `239/settings-history-lessons` (c4bebaf): leave alone.

## #251 Indonesian: where the read-back stands

- Writer: Claude. Reader: Google Cloud Translation via `readback.py <lines.json> <out.tsv>` in `.superpowers/sdd/251-indonesian/` (shared ledger; the Google day turns at 15:00 WIB). Another project shares the ledger: on 2026-11-11 (Pacific) about 10,700 were used elsewhere; read the ledger before planning.
- 2026-11-12 morning: panel-254 (5 lines) read back and committed; batch 2 (the 9 fixed paragraphs of broker.reading, costs.trading, dividends.basics, idx.auto_reject, idx.sessions, income.calendar) read back, every pair read, merged with `merge-tsv.py`. "Kemerataan" read back as "Equity", so it is now "Kemerataan pembayaran" ("Payment evenness"), read back again.
- After a draft edit: `python3 lessons-json.py lessons-id.json` before `pick-batch.py`, or the change is not seen.
- Queue for the next Google day: `advice-id.json` (952), then `pick-batch.py` (22 lessons left, about 28,000: two days).
- **Build only drafts whose every paragraph is read back** (memory `feedback-build-only-read-back-drafts`).

## Running
- Nothing local. The PR #574 waiter was stopped (DEAD); re-run: `~/.claude/scripts/pr-verdict.sh 574` (returns at once while CI runs: loop it with a ceiling). Colima not held.

## Next steps

1. PR #574: read the verdict; if every check is green on its head, squash-merge into develop (standing approval), then shut #573 by hand with each AC's evidence, remove `../steadyhand-544` and the branch.
2. `board-next` (repo-template `node scripts/board-next.ts PVT_kwHOCQ_jzM4BkhEb steadyhand`) for the next ticket. Everything left in the first release waits on the broker account, so expect a post-launch pick (#256 likely).
3. #251 read-back queue (the Google day turned at 15:00 WIB; 2026-11-13 Pacific day used 0): `advice-id.json` (29 lines, 952 chars) first, then `pick-batch.py`. Now includes the tax.dividend change (AC8).

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe ("steadyhand: the road to the first release"). Refresh steps: `.superpowers/sdd/estimates/progress.py` and `stories.py`, then republish with the date and time and a "Changed since the last update" list.

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; read open `docs/handover-*` PRs before asking Shyden anything (memory `feedback-newest-handover-may-be-in-a-pr`).
2. #242/#243/#245 parked on the broker account. Merge rule: squash into develop when every check is green on the head SHA; read the browser suite's per-browser totals. `pr-verdict.sh` returns at once before CI registers: loop it (memory `reference-pr-verdict-no-runs-yet`).
3. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage. Read a gate's `exit=` line, and grep `Errors|Unhandled`.
4. Filing a ticket: project id `PVT_kwHOCQ_jzM4BkhEb`, Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.

## Notes

- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. A new worktree needs `npm ci` in `extension/` before its first push, in a separate call from the `worktree add`.
