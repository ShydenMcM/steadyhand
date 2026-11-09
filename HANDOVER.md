# Handover: steadyhand

**Updated:** 2026-11-10 02:20 WIB (overnight, Shyden asleep; peer session `repo-template-c1` relayed: keep working by Priority, park anything that needs him, stop only when everything left waits on him). Current state only. Older history: `git show 4c29764:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here.

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

## For Shyden in the morning

Everything left waits on you or on the Google read-back quota (it resets 15:00 WIB):

1. **#542 (P0):** panel/core unit tests hit the 1 s timeout when other projects load the laptop (load 25-53; each passes alone in 105-356 ms; steps measured on the ticket). Rewrite the panel tests to about 20 ms each, or keep CI as the judge and run the local unit gate only on a quiet machine (then close or lower #542)?
2. **#251 scope:** the panel's own words are Indonesian (merged), the lessons follow (quota). Core's notes, refusals and the strategies' reasons reach the panel in English: about 80 message sites in core and the readers. Translate them too (a core change: each note carries a form name and its values; a new story of its own), or ship Indonesian with those in English?
3. **#251 AC4:** the fluent reader is yours to name. Panel review sheet: `.superpowers/sdd/251-indonesian/review.md`. Words worth your eye: `Saran` for the Advice tab (reads back "Suggestion"), `fraksi harga` (tick), `notasi khusus`.
4. **#254 (income projection):** spec §9.1 drafted on branch `254/projection-spec` (51a4eeb) with two questions: where the monthly contribution comes from (recommended: an optional Settings field, blank = 0) and where it shows (recommended: under Income goal on the Advice tab). Approve or change, then code starts test first.
5. **#255/#256 (exemption claims):** the extension cannot see the purchases that reinvest a dividend (Python covers claims from its own fills). Options on #255: infer from holdings between reads, read a trade-history page once the first broker exists, or the user enters each purchase.

## Branches and PRs

- `develop`: read with `git rev-parse origin/develop`. Merged overnight: #543 (#251 part 1), #545 (#544), #547 (#546), #549 (#548). #544, #546 and #548 stay open until their Indonesian lesson lands with #251 (each one's AC3).
- Merged too: #550 (Refs #251), the language switch in the browser suite's Settings journey (probe seen red on CI, run 42678904127, line 400, then undone); 6 tests on each of Chromium, Chrome and Edge.
- `251/indonesian-lessons` (pushed, WIP, red on purpose until all 37 lessons exist): per-language lesson catalogue, Lessons tab follows the language, tests for every lesson's Indonesian twin, derived list widened (%, rupiah, LQ45, T+2). 9 of 37 built into `extension/packages/shell/lessons/id/`; all 37 drafted in `.superpowers/sdd/251-indonesian/lessons-id/*.txt` (the drafts already carry #544/#546/#548's fixes).
- `254/projection-spec` (pushed, 51a4eeb): the spec draft above; no PR until approved.
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

- Nothing running. Colima not held. GitHub Actions had a major outage 01:20-01:55 WIB; the runs it cut short were re-run or superseded.

## Next steps (after 15:00 WIB, when the Google day turns)

1. Read back the 28 unread lessons (`lessons-json.py`, diff against `lessons-readback.tsv`, `readback.py`; about 32,000 characters, two Google days), fix what the read-back shows, build with `build-lessons.py`, run the lessons tests, and open the lessons PR once all 37 exist.
2. Then strategy summaries and help, and the advice view's own headings, in Indonesian; then whatever Shyden decides for core's messages.

## P4 is open (Shyden 2026-11-09)

- P4 stories start by Priority before the first release; all P4s tie, so lowest number with every blocker closed. #251 is in progress; then #254, #255, #256, #339, #345. #252, #253, #257, #258 are blocked on the parked readers. #242, #243, #245 parked on the broker account.

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe ("steadyhand: the road to the first release", Shyden 2026-11-07: shared with anyone with the link, launch = the first release #245, its own slate and green look). Modelled on Yawelo Idle's page.

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; `git rev-parse --abbrev-ref HEAD`.
2. #242/#243/#245 are parked on the broker account. #348 (SonarCloud) is closed: no SonarCloud for steadyhand (Shyden 2026-11-08). Merge the #539 PR when green, then take the next P4.
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
