# Handover: steadyhand

**Updated:** 2026-11-08. #308, #348 (not planned), #499, #528 shut; #400's workflow merged (PR #527). Current state only. Older history: `git show 4c29764:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here (desktop extension; phones unavailable anyway).

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (this handover lands after PR #527).
- `400/release-cut` (worktree `../steadyhand-308`) was PR #527, merged at head 8912ef5; remove the worktree and branch after checking the tip equals that head.
- Slip backups, **never copy or replay from them**: `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06). Local `239/settings-history-lessons` (c4bebaf): leave alone.
- `238/extension-shell` merged (PR #500); delete locally only after checking its tip equals PR #500's head 3f3dd12.
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (to 2026-11-27); `365/exact-values-backup-2026-10-27` (to 2026-11-26), `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29).

## Shyden's answers (2026-11-08, AskUserQuestion)
- **Broker account:** cannot be opened yet (a personal prerequisite; never write its details in this public repo). #242, #243 and #245 stay parked until he says otherwise. Still no P4 "EXT later" stories.
- **#308:** a release checklist step (`RELEASING.md`), not a scheduled job. Done; closed.
- **#400:** confirmed. `main` is no longer strict and requires `release-cut` from GitHub Actions (app 15368), set through the API at his request ("do it for me") and read back on #400. The workflow merged (PR #527, head 8912ef5). #400 stays open until `release-cut` is seen posting on a real pull request into `main`: at the first release (#245), or on a probe pull request from a `release/` branch if Shyden allows it (this session's permissions refused opening one).
- **#528:** one route to the side panel on every browser (Extensions button, then the menu's tile below the toolbar row).

## Running
- Nothing local, no PR open.

## Waiting on Shyden
- #242, #243, #245: parked (above).
- #400: Shyden's say on a probe pull request into `main` (above).

## Progress page
- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe ("steadyhand: the road to the first release", Shyden 2026-11-07: shared with anyone with the link, launch = the first release #245, its own slate and green look). Modelled on Yawelo Idle's page.

## Resume steps
1. `ListAgents`; `git status --short`; `git fetch --prune`; `git rev-parse --abbrev-ref HEAD`.
2. Ask Shyden whether a probe pull request into `main` may prove #400's `release-cut`; never merge it.
3. Nothing else is workable without Shyden: #242/#243/#245 are parked. #348 (SonarCloud) is closed: no SonarCloud for steadyhand (Shyden 2026-11-08). Ask him, never start P4.
4. Merge rule: squash into develop when every check is green on the head SHA (standing approval 2026-11-04); read the browser suite's per-browser totals and each new guard by name before merging.
5. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage; scratch copies go in `pristine/`, never `*.bak`. Guards, integration and the browser suite are CI's. Read a gate's `exit=` line, and grep `Errors|Unhandled`, never only `Tests`.
6. Filing a ticket: `gh issue create`, `gh project item-add 1 --owner ShydenMcM --url <issue>`, `gh project item-edit` (project id `PVT_kwHOCQ_jzM4BkhEb`) with Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue.
7. **Every session ends by refreshing the progress page** (Shyden 2026-11-07): run `.superpowers/sdd/estimates/progress.py` (headline figures) and `stories.py` (every EXT and post-launch story, for the milestone counts); `Artifact action:"read"` the page URL above, edit the saved file it names (date, counts, points, pace, waits), then publish it with that `url`. Plain wording, no "we", measured vs assumed stated.

## Notes
- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. `git commit --amend` is refused by auto mode: add a commit.
- Throwaway probe files carry a file-level `# ruff: noqa` / `/* eslint-disable */` so pre-push passes.
- A PreToolUse refusal drops the whole command, edits included: re-apply them.
- The editor's TypeScript diagnostics disagree with `tsc --noEmit`; tsc is the authority.
- Test runs queue machine-wide behind other projects: background long runs.
- A CI job's log: `gh run view <run> --log --job <job id>`.
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
