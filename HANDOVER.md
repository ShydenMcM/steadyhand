# Handover: steadyhand

**Updated:** 2026-11-13 14:26 WIB. Current state only. Older history: `git show 4c29764:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here.

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

## Open with Shyden

- Nothing open.

## Shyden's answers (2026-11-13)

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

- `develop`: read with `git rev-parse origin/develop`.
- Merged 2026-11-13: #571 (#570 P0, extension integration builds once, proven by strace and per-test assertion counts; 083ccf8). #568 P0 is done: runner counts on CI (probe PR #569, shut unmerged; run 43383498799) prove that the earlier journey merge kept every check. Shyden ruled: keep the 5 browser journeys (shared opening only). `testpypi` environment deleted on his choice (dev-deploy rule); `dev` already allows all branches.
- Also merged 2026-11-13: #565 (#255 core claims, parity harness, `tax.exemption` lesson; 1954940), #567 (#566 P0 soupsieve CVE, closed with evidence), #564 (Dependabot).
- `255/tax-tab` in worktree `../steadyhand-255b` (local only, never pushed; head read with `git -C ../steadyhand-255b rev-parse HEAD`): stacked on #565's pre-squash tip, so before its PR merge `origin/develop` in (memory `reference-stacked-branch-after-squash`). Done, each test run red first: `shell/src/exemption.ts` (switch, kept entries, `typedEntry` with day/future/early/stock/amount refusals, `wibDay`), `shell/src/tax-view.ts` (claims lines, English like the Advice lines), STOCK_CODE/WHOLE_RUPIAH moved to settings.ts, `sentence` exported from advice-view.ts. Mutation passes done for both.
- `251/indonesian-lessons` (pushed, WIP, red on purpose): 9 of 37 built, now **38** with `tax.exemption` (tell #251). Drafts in `.superpowers/sdd/251-indonesian/lessons-id/*.txt`.
- Backups (keep 30 days): `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06), `377/wip-backup-2026-10-28` (to 2026-11-27), `365/exact-values-backup-2026-10-27` (to 2026-11-26) and `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29). Never copy or replay from the slip backups. Local `239/settings-history-lessons` (c4bebaf): leave alone.

## #251 Indonesian: where the read-back stands

- Writer: Claude. Reader: Google Cloud Translation via `readback.py <lines.json> <out.tsv>` in `.superpowers/sdd/251-indonesian/` (shared ledger; the Google day turns at 15:00 WIB). Another project shares the ledger: on 2026-11-11 (Pacific) about 10,700 were used elsewhere; read the ledger before planning.
- 2026-11-12 morning: panel-254 (5 lines) read back and committed; batch 2 (the 9 fixed paragraphs of broker.reading, costs.trading, dividends.basics, idx.auto_reject, idx.sessions, income.calendar) read back, every pair read, merged with `merge-tsv.py`. "Kemerataan" read back as "Equity", so it is now "Kemerataan pembayaran" ("Payment evenness"), read back again.
- After a draft edit: `python3 lessons-json.py lessons-id.json` before `pick-batch.py`, or the change is not seen.
- Queue for the next Google day: `advice-id.json` (952), then `pick-batch.py` (22 lessons left, about 28,000: two days).
- **Build only drafts whose every paragraph is read back** (memory `feedback-build-only-read-back-drafts`).

## Running

- Nothing local. Colima not held. No background waiters.

## Next steps

1. #255 panel, in `../steadyhand-255b`, tests first in `shell/test/panel.test.ts` (stand-in `StandIn` needs `checked = false`; `PanelDocument` needs an `"input"` overload with `checked: boolean`): Settings checkbox `exemption` ("I claim the dividend reinvestment exemption", saved on change, `EXEMPTION.claimed`); fifth tab `tab-tax`, hidden while off (unticking while on Tax opens Advice); Tax pane: dividend form (`dividend-day/-stock/-gross`, `add-dividend`), purchase form (`purchase-day/-stock/-amount`, `add-purchase`), each entry listed with a Remove button, then `taxView(claimsReport(market, dividends, purchases, wibDay(clock())))` lines; `typedEntry(..., today, market.verifiedFrom)`; forget test gains "switch and entries cleared". Clock in tests is 2025-06-17 WIB; deadline for a 2025 dividend is 2026-03-31 (`reinvest_by_month` 3). New words in English and Indonesian (Google read-back before commit), and the browser journey gets the Tax assertions (CI).
2. After 15:00 WIB: the #251 read-back queue (advice-id.json 952, then pick-batch.py); read the ledger first.

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe ("steadyhand: the road to the first release"). Refresh steps: `.superpowers/sdd/estimates/progress.py` and `stories.py`, then republish with the date and time and a "Changed since the last update" list.

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; read open `docs/handover-*` PRs before asking Shyden anything (memory `feedback-newest-handover-may-be-in-a-pr`).
2. #242/#243/#245 parked on the broker account. Merge rule: squash into develop when every check is green on the head SHA; read the browser suite's per-browser totals. `pr-verdict.sh` returns at once before CI registers: loop it (memory `reference-pr-verdict-no-runs-yet`).
3. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage. Read a gate's `exit=` line, and grep `Errors|Unhandled`.
4. Filing a ticket: project id `PVT_kwHOCQ_jzM4BkhEb`, Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.

## Notes

- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. A new worktree needs `npm ci` in `extension/` before its first push, in a separate call from the `worktree add`.
