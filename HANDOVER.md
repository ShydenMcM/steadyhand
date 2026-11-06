# Handover: steadyhand

**Updated:** 2026-11-07, #239 every AC built and in unit tests; PR opened from `239/settings-history-lessons-2`. Current state only. Older history: `git show d66cdce:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here (desktop extension; phones unavailable anyway).

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

## Branches and heads
- `develop` = 3c446c7. `239/settings-history-lessons-2`: every #239 slice committed and pushed (head: `git rev-parse HEAD`); the PR is the one `gh pr list --head 239/settings-history-lessons-2` shows.
- `239/slip-backup-2026-11-06` (16180e5, kept to 2026-12-06): **never copy or replay from it**. Local `239/settings-history-lessons` (c4bebaf): leave alone.
- `238/extension-shell` merged (PR #500); delete locally only after checking its tip equals PR #500's head 3f3dd12.
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (to 2026-11-27); `365/exact-values-backup-2026-10-27` (to 2026-11-26), `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29).

## #239 state (unit gate 3407 passed, 100% branches)
- AC1 Settings: strategy picker, goal, limits, fee preset, typed movements, universe, exclusions.
- AC2 History (bd9d768): `stockHistory` (history/src/summary.ts, ac6d345), `#recording-note`, `#stock-history`, `#forget` -> `#forget-confirm` (`#forget-yes`/`#forget-keep`); forget reopens the db empty and redraws. PanelInputs gained `factory`, `storage` (chrome.storage.local).
- AC3 Lessons (cc9f6d8): `shell/src/lessons.ts` `LESSONS` (modules -> lessons: id, title, summary, plain paragraphs) is empty until #244; tab says "The lessons come in a later release." #244 must turn the Python Markdown into plain paragraphs.
- AC4 paste/import (5f8cee7): `#paste` + `#read-paste`, `#import` (file, .html/.htm); both feed `recordRead`. "No request" is EXT S15b's.
- (c) 88379e2: journey.spec.ts `withPanel` helper + a second journey driving every tab: **unverified until CI's browser suite runs.**

## Running
- Nothing local. CI on the PR: one background `~/.claude/scripts/pr-verdict.sh <pr>`.

## Waiting
- #308, #400 (main protection) and #348 (SonarCloud): Shyden's.
- #511 stays open until #239 merges (its AC3 test is on this branch); then shut it by hand after reading each AC.

## Resume steps
1. `ListAgents`; `git status --short`; `git fetch --prune`; `git rev-parse --abbrev-ref HEAD`.
2. Read the PR's CI verdict; a red browser job: `gh run view <run> --log --job <id>`, find the cause, fix (test first), push once.
3. Green on the head SHA: squash-merge into develop (standing approval 2026-11-04). Then verify each #239 AC against code and tests case by case and shut the ticket by hand; then #511.
4. Next ticket: #513 (vitest 5.1.0), or `node ~/Developer/Repos/repo-template/scripts/board-next.ts PVT_kwHOCQ_jzM4BkhEb steadyhand 2>/dev/null`.
5. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage; scratch copies go in `pristine/`, never `*.bak`. Guards, integration and the browser suite are CI's.
6. Filing a ticket: `gh issue create`, `gh project item-add 1 --owner ShydenMcM --url <issue>`, `gh project item-edit` (project id `PVT_kwHOCQ_jzM4BkhEb`) with Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.

## Notes
- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. `git commit --amend` is refused by auto mode: add a commit.
- Throwaway probe files carry a file-level `# ruff: noqa` / `/* eslint-disable */` so pre-push passes.
- A PreToolUse refusal drops the whole command, edits included: re-apply them.
- The editor's TypeScript diagnostics disagree with `tsc --noEmit`; tsc is the authority.
- Test runs queue machine-wide behind other projects: background long runs.
- A CI job's log: `gh run view <run> --log --job <job id>`.
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
