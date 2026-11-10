# Handover: steadyhand

**Updated:** 2026-11-10 15:45 WIB (laptop shutdown requested via peer `repo-template-23`). Current state only. Older history: `git show 4c29764:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here.

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

## Shyden's answers (2026-11-10, AskUserQuestion; each recorded on its ticket)

- **#542:** no test rewrite; CI judges, and the local unit gate runs only on a quiet machine. #542 closed not planned.
- **#251 scope:** Indonesian ships with core's notes, refusals and strategy reasons in English; translating them is #553 (P4, 8 points, blocked by #251).
- **#254:** spec §9.1 approved: optional Settings field "Monthly amount you add, in rupiah" (blank = 0); the projection shows under Income goal on the Advice tab.
- **#255/#256:** the user enters each purchase that reinvests a dividend (a form in the panel).
- **Still his:** #251 AC4, the fluent Indonesian reader (review sheet `.superpowers/sdd/251-indonesian/review.md`). PR #541 (stale handover, conflicting) should be closed: auto mode refused my close; ask him or leave it.

## Branches and PRs

- **#556 closed** (P0, Dependabot's Node bump refused with a 400 while the pin lived under `.github/`): PR #557 moved it to `docker/node/Dockerfile` (squash 18820a64); Dependabot then opened **PR #558** (node 26.13.0). #558 is red only on `test_the_node_dockerfile_names_node_26_12_1` (`tests/guards/test_supply_chain.py` lines 349/354, by design): rename the test and set the literal to 26.13.0 on the Dependabot branch, push, merge when green.
- **PR #552** `254/projection-spec` (spec §9.1 approved, plus the fourth root taken as Python does, `ln`/`exp` in decimal.js): all 11 required checks green on f8d705d9, but BEHIND develop since #557 merged: merge develop in, push, squash-merge when green on the new head.
- **PR #554** `254/projection-core` (worktree `../steadyhand-254`): core's `incomeGrowth` and `project` in `extension/packages/core/src/projection.ts`, 14 unit tests, 80-portfolio parity harness (`scripts/core_fixtures.py` `projection_cases`, `parity-projection.json`, in `.prettierignore`). Laptop: 3979 unit tests, 100% branches, lint/types/prettier clean; six mutants caught. CI on 83f7dd2b: `extension-guards` FAILED, not yet read (`gh run view <run> --log-failed`). After #552 merges, merge develop into it before merging.
- `251/indonesian-lessons` (pushed, WIP, red on purpose until all 37 lessons exist): 9 of 37 built in `extension/packages/shell/lessons/id/`; all 37 drafted in `.superpowers/sdd/251-indonesian/lessons-id/*.txt`. #544, #546 and #548 stay open until their Indonesian lesson lands (each one's AC3).
- Backups (keep 30 days): `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06), `377/wip-backup-2026-10-28` (to 2026-11-27), `365/exact-values-backup-2026-10-27` (to 2026-11-26) and `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29). Never copy or replay from the slip backups. Local `239/settings-history-lessons` (c4bebaf): leave alone.

## Shyden's answers (2026-11-08, AskUserQuestion)

- **Broker account:** cannot be opened yet (a personal prerequisite; never write its details in this public repo). #242, #243 and #245 stay parked until he says otherwise.
- **#308:** a release checklist step (`RELEASING.md`), not a scheduled job. Done; closed.
- **#400:** closed 2026-11-08. Probe PR #531 (release/probe-400, Shyden approved by AskUserQuestion): release-cut posted success and the merge state read CLEAN; closed unmerged, branch deleted. A non-release probe is refused by the release-from-a-cut hook.
- **#528:** one route to the side panel on every browser (Extensions button, then the menu's tile below the toolbar row).

## #251 Indonesian: how the translation runs

- Writer: Claude. Reader: Google Cloud Translation via `.superpowers/sdd/251-indonesian/readback.py <lines.json> <out.tsv>` (shared ledger `~/.config/shyden/google-translate-ledger.json`, never past 16,000 a Google day; the day turns at 15:00 WIB; slots, code spans and "steadyhand" sent untranslated). 2026-11-09 Google day: 15,803 used.
- Lessons: `lessons-json.py lessons-id.json` collects draft paragraphs; diff against `lessons-readback.tsv`, read back only what changed; `build-lessons.py` writes `lessons/id/*.md`. **Build only drafts whose every paragraph is read back** (one slip caught 2026-11-10, memory `feedback-build-only-read-back-drafts`). About 28 lessons (about 32,000 characters) remain: two Google days.
- Still to do after the lessons: strategy summaries and help, advice lines and core's refusal reasons in Indonesian; the browser suite's journey checking the language switch (add to an existing journey); the fluent reader.

## Running

- Nothing local. Colima not held. No outside waits: every PR's CI has finished. The Google day turned at 15:00 WIB (a new 16,000).

## Next steps

1. #558: fix the version test (above), merge when green. Then #552: merge develop in, merge when green. Then #554: read and fix its `extension-guards` failure, merge develop in, merge when green.
2. #254 part 2 (new branch from develop, test first): the Settings field (kept like the goal), the Advice tab's lines under Income goal (one per scenario, "Projection, not a promise", years never a date; a missing list when `incomeGrowth` returns missing), and the `income.projection` and `income.growth` lessons (rewritten where they name the backtest or configuration file). New panel words and the two lessons need Indonesian twins, read back by Google after 15:00 WIB.
3. After 15:00 WIB: the 28 unread #251 lessons (`lessons-json.py`, diff against `lessons-readback.tsv`, `readback.py`; about 32,000 characters, two Google days), then strategy summaries, help and the advice view's headings.
4. Then #255/#256 with the user-entered purchases ruling.

## P4 is open (Shyden 2026-11-09)

- P4 stories start by Priority before the first release; all P4s tie, so lowest number with every blocker closed. #251 is in progress; then #254, #255, #256, #339, #345. #252, #253, #257, #258 are blocked on the parked readers. #242, #243, #245 parked on the broker account.

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe ("steadyhand: the road to the first release", Shyden 2026-11-07: shared with anyone with the link, launch = the first release #245, its own slate and green look). Modelled on Yawelo Idle's page.

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; `git rev-parse --abbrev-ref HEAD`.
2. #242/#243/#245 are parked on the broker account. #348 (SonarCloud) is closed: no SonarCloud for steadyhand (Shyden 2026-11-08). Then follow Next steps above; the local unit gate runs only when `uptime` load is low (#542 ruling).
3. Merge rule: squash into develop when every check is green on the head SHA (standing approval 2026-11-04); read the browser suite's per-browser totals and each new guard by name before merging.
4. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage; scratch copies go in `pristine/`, never `*.bak`. Guards, integration and the browser suite are CI's. Read a gate's `exit=` line, and grep `Errors|Unhandled`, never only `Tests`.
5. Filing a ticket: `gh issue create`, `gh project item-add 1 --owner ShydenMcM --url <issue>`, `gh project item-edit` (project id `PVT_kwHOCQ_jzM4BkhEb`) with Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.
6. **Every session ends by refreshing the progress page** (Shyden 2026-11-07): run `.superpowers/sdd/estimates/progress.py` (headline figures) and `stories.py` (every EXT and post-launch story, for the milestone counts); `Artifact action:"read"` the page URL above, write its body (from `<title>`) to a scratchpad file with the edits (date, counts, points, pace, waits), then publish it with that `url`. Each refresh shows "Updated <d Month yyyy>, <HH:MM> WIB" (`date '+%-d %B %Y, %H:%M %Z'`) and a "Changed since the last update" list of 2-5 bullets near the top (Shyden 2026-11-08, global rule). Plain wording, no "we", measured vs assumed stated.

## Notes

- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. `git commit --amend` is refused by auto mode: add a commit.
- Throwaway probe files carry a file-level `# ruff: noqa` / `/* eslint-disable */` so pre-push passes.
- A PreToolUse refusal drops the whole command, edits included: re-apply them.
- The editor's TypeScript diagnostics disagree with `tsc --noEmit`; tsc is the authority.
- Test runs queue machine-wide behind other projects: background long runs.
- A CI job's log: `gh run view <run> --log --job <job id>`.
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
