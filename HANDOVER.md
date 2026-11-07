# Handover: steadyhand

**Updated:** 2026-11-07, #239-#241, #244, #511, #513, #517 shut; every first-release story left is parked on Shyden. He was AFK most of the day (relayed 2026-11-07): his decisions go to AskUserQuestion or here. Current state only. Older history: `git show d66cdce:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here (desktop extension; phones unavailable anyway).

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

## Branches and heads
- `develop` = c88b49e (#520). No ticket branch in flight.
- Slip backups, **never copy or replay from them**: `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06). Local `239/settings-history-lessons` (c4bebaf): leave alone.
- `238/extension-shell` merged (PR #500); delete locally only after checking its tip equals PR #500's head 3f3dd12.
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (to 2026-11-27); `365/exact-values-backup-2026-10-27` (to 2026-11-26), `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29).

## Parked for Shyden (asked 2026-11-07 by AskUserQuestion)
- #499 (P1, 3): his ruling among its three options (a same-day deposit after the read making a false daily-loss halt) before ACs can be set.
- #242, #243 (P1, 8 each): a POEMS or BIONS account, its agreement read for automated-reading terms, and his saved pages (spec §5.3).
- #245 (P1, release): blocked by #242 and #243; then the release environment and his admin part (AC4).
- #308, #400 (main protection), #348 (SonarCloud): P2, his.
- Whether to start P4 "EXT later" stories (#253 income received first by size) before the first release.

## Running
- Nothing local. A PR's CI: wait with `until ~/.claude/scripts/pr-verdict.sh <pr> | grep -q "runs=\[ci:completed"; do sleep 60; done` in the background.

## Waiting
- #308, #400 (main protection) and #348 (SonarCloud): Shyden's.

## Resume steps
1. `ListAgents`; `git status --short`; `git fetch --prune`; `git rev-parse --abbrev-ref HEAD`.
2. Read Shyden's answers (#499 option; P4 or wait). #499: set its ACs from the ruling, tests red first, own branch.
3. Otherwise `node ~/Developer/Repos/repo-template/scripts/board-next.ts PVT_kwHOCQ_jzM4BkhEb steadyhand 2>/dev/null` and skip what is parked above.
4. Merge rule: squash into develop when every check is green on the head SHA (standing approval 2026-11-04); read the browser suite's per-browser totals and each new guard by name before merging.
5. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage; scratch copies go in `pristine/`, never `*.bak`. Guards, integration and the browser suite are CI's. Read a gate's `exit=` line, and grep `Errors|Unhandled`, never only `Tests`.
6. Filing a ticket: `gh issue create`, `gh project item-add 1 --owner ShydenMcM --url <issue>`, `gh project item-edit` (project id `PVT_kwHOCQ_jzM4BkhEb`) with Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.

## Notes
- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. `git commit --amend` is refused by auto mode: add a commit.
- Throwaway probe files carry a file-level `# ruff: noqa` / `/* eslint-disable */` so pre-push passes.
- A PreToolUse refusal drops the whole command, edits included: re-apply them.
- The editor's TypeScript diagnostics disagree with `tsc --noEmit`; tsc is the authority.
- Test runs queue machine-wide behind other projects: background long runs.
- A CI job's log: `gh run view <run> --log --job <job id>`.
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
