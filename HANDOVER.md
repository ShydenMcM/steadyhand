# Handover: steadyhand

**Updated:** 2026-11-11 07:29 WIB (before Shyden's laptop restart for an OS update). Current state only. Older history: `git show 4c29764:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here.

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

## Open with Shyden

1. **Close PRs #541 and #555** (old handovers): Shyden asked (2026-11-11) for this to be done in his Chrome with Claude in Chrome; not done before the restart. Do it first after the restart.

## Shyden's answers (2026-11-10)

- **#255 (2026-11-11):** route (a): the user enters each dividend received (date, stock, gross) in a form beside the purchases form (recorded on #255). Spec §9.2 can be drafted.
- **Clean-up (2026-11-11):** remote branches `308/release-checklist` and `docs/handover-2026-10-29d` deleted.

- **#542:** no test rewrite; CI judges, the local unit gate runs only on a quiet machine. Closed not planned.
- **#251 scope:** Indonesian ships with core's notes, refusals and strategy reasons in English; translating them is #553 (P4, 8 points, blocked by #251).
- **#251 AC4 (23:2x WIB):** "no manual reviews, just complete it": no fluent human reader; the Google read-back of every line is the review (recorded on #251).
- **#254:** spec §9.1 approved: optional Settings field "Monthly amount you add, in rupiah" (blank = 0); the projection shows under Income goal on the Advice tab.
- **#255/#256:** the user enters each purchase that reinvests a dividend (a form in the panel).

## Branches and PRs

- `develop`: read with `git rev-parse origin/develop`. Merged tonight: #558 (Node 26.13.0 and its pin test, 7a58046), #552 (spec §9.1, 81a9881), #559 (Dependabot: @playwright/test 1.65.0, vite 8.3.6; 6 browser tests on each of three browsers; 0f305a7), #554 (#254 part 1: core's `incomeGrowth` and `project`, and the `income.growth` and `income.projection` lessons the lesson-coverage guard asked for; ff3cf37).
- **PR #560** `254/projection-panel` (worktree `../steadyhand-254`, on develop): commit 30b700a projects the goal under Income goal on the Advice tab (model + view, tests first, mutants caught) and keeps `monthly-contribution` in the record. **Uncommitted on top:** the Settings field (label, input, Save amount, saved/cleared/refused words, tests green); it waits for its 5 Indonesian words' read-back (`.superpowers/sdd/251-indonesian/panel-254.json`, 205 characters). Backup patches: `.superpowers/sdd/254/settings-field-uncommitted.patch` and `-2026-11-11.patch` (9,641 bytes, taken before the restart). Commit the field once read back, push (stash nothing then), merge #560 when green. Do not merge #560 before the field lands: its lesson names the Settings field.
- `251/indonesian-lessons` (pushed, WIP, red on purpose until all 37 lessons exist): 9 of 37 built. Drafts in `.superpowers/sdd/251-indonesian/lessons-id/*.txt` (39 now: income.growth and income.projection added tonight).
- Backups (keep 30 days): `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06), `377/wip-backup-2026-10-28` (to 2026-11-27), `365/exact-values-backup-2026-10-27` (to 2026-11-26) and `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29). Never copy or replay from the slip backups. Local `239/settings-history-lessons` (c4bebaf): leave alone. Branch tips saved before tonight's clean-up: `.superpowers/sdd/branch-tips-2026-11-10.txt`.

## #251 Indonesian: where the read-back stands

- Writer: Claude. Reader: Google Cloud Translation via `.superpowers/sdd/251-indonesian/readback.py <lines.json> <out.tsv>` (shared ledger, never past 16,000 a Google day; the day turns at 15:00 WIB). 2026-11-10 Google day: 15,845 used.
- Tonight: 11 more lessons read back (`batch-1.tsv`, merged into `lessons-readback.tsv`; side-by-side `side-1.txt`). Fixed after reading every pair: run-rate is now "run-rate" (Google read "laju berjalan" as "walking speed"), dividends.basics "before this day" (read back as "before today"), auto_reject "exactly on the limit", sessions "advice waits", calendar evenness, broker.reading, costs.trading, not_tradable. Those fixes (about 4,800 characters) need reading back again.
- `pick-batch.py <budget> <out.json>` picks the unread or changed paragraphs, whole lessons only. Then `side.py <tsv>` lines each read-back up with its English paragraph.
- Queue for the next Google day, in order: the fixes' re-read (about 4,800), `panel-254.json` (205), `advice-id.json` (the Advice tab's 29 lines as slot templates, 952), then the 17 unread lessons and the two new income lessons (about 23,000; two days).
- **Build only drafts whose every paragraph is read back** (memory `feedback-build-only-read-back-drafts`).

## Running

- Nothing local; nothing dies with the restart. Colima not held. The #254 Settings field is uncommitted in `../steadyhand-254` (files on disk survive a restart; patch backed up).

## Next steps

1. After 15:00 WIB: the read-back queue above; commit the Settings field on #560 and merge it when green; then the lessons.
2. #255: draft spec §9.2 on route (a) (no Google quota needed; can start before 15:00 WIB).

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe ("steadyhand: the road to the first release"). Refresh steps: `.superpowers/sdd/estimates/progress.py` and `stories.py`, then republish with the date and time and a "Changed since the last update" list.

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; read open `docs/handover-*` PRs before asking Shyden anything (memory `feedback-newest-handover-may-be-in-a-pr`).
2. #242/#243/#245 parked on the broker account. Merge rule: squash into develop when every check is green on the head SHA; read the browser suite's per-browser totals. `pr-verdict.sh` returns at once before CI registers: loop it (memory `reference-pr-verdict-no-runs-yet`).
3. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage. Read a gate's `exit=` line, and grep `Errors|Unhandled`.
4. Filing a ticket: project id `PVT_kwHOCQ_jzM4BkhEb`, Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.

## Notes

- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. A new worktree needs `npm ci` in `extension/` before its first push, in a separate call from the `worktree add`.
