# Handover: steadyhand

**Updated:** 2026-11-08. #308, #348 (not planned), #400, #499, #528 shut. Current state only. Older history: `git show 4c29764:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here (desktop extension; phones unavailable anyway).

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop`. No other worktree; merged branches `400/release-cut`, `528/panel-path-by-browser`, `238/extension-shell` deleted after their tips matched PRs #527, #529, #500.
- Slip backups, **never copy or replay from them**: `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06). Local `239/settings-history-lessons` (c4bebaf): leave alone.
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (to 2026-11-27); `365/exact-values-backup-2026-10-27` (to 2026-11-26), `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29).

## Shyden's answers (2026-11-08, AskUserQuestion)
- **Broker account:** cannot be opened yet (a personal prerequisite; never write its details in this public repo). #242, #243 and #245 stay parked until he says otherwise. Still no P4 "EXT later" stories.
- **#308:** a release checklist step (`RELEASING.md`), not a scheduled job. Done; closed.
- **#400:** closed 2026-11-08. Probe PR #531 (release/probe-400, Shyden approved by AskUserQuestion): release-cut posted success and the merge state read CLEAN; closed unmerged, branch deleted. A non-release probe is refused by the release-from-a-cut hook.
- **#528:** one route to the side panel on every browser (Extensions button, then the menu's tile below the toolbar row).

## Running
- Nothing local, no PR open.

## Paused (Shyden 2026-11-08 23:24 WIB, AskUserQuestion)
- steadyhand is paused until the broker account exists. Start nothing; at resume, ask him whether the account is open.
- **Overnight relay, 2026-11-08 23:48 WIB (repo-template session, relaying Shyden going to sleep: "take the next ticket by Priority"):** the pause holds. The board was re-read: open tickets are #242, #243, #245 (parked), the #214 epic and the P4 "EXT later" stories he ruled out before the first release, so no ticket is workable. A relay names no ticket, and it does not lift his own ruling.
- **For Shyden when back:** is the broker account open? If not, does the pause stand? Only he can change either.

## Waiting on Shyden
- #242, #243, #245: parked (above).

## Progress page
- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe ("steadyhand: the road to the first release", Shyden 2026-11-07: shared with anyone with the link, launch = the first release #245, its own slate and green look). Modelled on Yawelo Idle's page.

## Resume steps
1. `ListAgents`; `git status --short`; `git fetch --prune`; `git rev-parse --abbrev-ref HEAD`.
2. Nothing is workable without Shyden: #242/#243/#245 are parked. #348 (SonarCloud) is closed: no SonarCloud for steadyhand (Shyden 2026-11-08). Ask him, never start P4.
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
