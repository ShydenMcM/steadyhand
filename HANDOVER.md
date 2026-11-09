# Handover: steadyhand

**Updated:** 2026-11-09. #246, #248, #249, #250 (not planned), #247, #539, #308, #348 (not planned), #400, #499, #528, #535 shut. Current state only. Older history: `git show 4c29764:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here (desktop extension; phones unavailable anyway).

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

## Branches and heads

- `develop`: read with `git rev-parse origin/develop`. No other worktree; merged branches `400/release-cut`, `528/panel-path-by-browser`, `238/extension-shell` deleted after their tips matched PRs #527, #529, #500.
- Slip backups, **never copy or replay from them**: `240/slip-backup-2026-11-07` (to 2026-12-07), `239/slip-backup-2026-11-06` (to 2026-12-06). Local `239/settings-history-lessons` (c4bebaf): leave alone.
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (to 2026-11-27); `365/exact-values-backup-2026-10-27` (to 2026-11-26), `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29).

## Shyden's answers (2026-11-08, AskUserQuestion)

- **Broker account:** cannot be opened yet (a personal prerequisite; never write its details in this public repo). #242, #243 and #245 stay parked until he says otherwise.
- **#308:** a release checklist step (`RELEASING.md`), not a scheduled job. Done; closed.
- **#400:** closed 2026-11-08. Probe PR #531 (release/probe-400, Shyden approved by AskUserQuestion): release-cut posted success and the merge state read CLEAN; closed unmerged, branch deleted. A non-release probe is refused by the release-from-a-cut hook.
- **#528:** one route to the side panel on every browser (Extensions button, then the menu's tile below the toolbar row).

## Running

- Nothing local, no PR open. Colima not held.

## P4 is open (Shyden 2026-11-09, AskUserQuestion)

- The broker account is still not open, and he lifted the no-P4 ruling: **P4 stories start by Priority before the first release**. All P4s tie, so lowest number with every blocker closed.
- Each strategy story's first AC is a spec amendment he approves before code. Measure the readings first with `.superpowers/sdd/247-low-volatility/measure.py` (point-in-time LQ45 cache in `.superpowers/sdd/m7-lq45`), ask, write spec §7.3, ask approval, then test first.
- **Strategies settled 2026-11-09:** #247 low-volatility shipped (PR #538). Dropped after measuring, closed not planned: #246 dual-momentum, #248 breakout, #249 rsi-reversion, #250 dividend-capture (it becomes #539's lesson). Figures on each ticket and in spec §7.3. Scripts: `.superpowers/sdd/{246-dual-momentum,247-low-volatility,248-breakout,249-rsi,250-capture}/measure.py`.
- **#539** (ex-date lesson): shipped in PR #540, shut.
- **Next: #251 (Indonesian, 8 points), not started.** Shyden 2026-11-09: build now, name the fluent reader later; #251 stays open until that reading is done. Every line needs the Google read-back (global rule). Then #254, #255, #256, #339, #345. #252, #253, #257 and #258 are blocked on the parked readers.
- **New tests (global rule "One journey, all its assertions"):** before writing any e2e, journey, device or integration test, look for that journey and add the assertion there. Agent briefs carry this.

## Waiting on Shyden

- #242, #243, #245: parked (above).

## Progress page

- https://claude.ai/artifact/LQUaFm9jQDeEkdqv8tmmqe ("steadyhand: the road to the first release", Shyden 2026-11-07: shared with anyone with the link, launch = the first release #245, its own slate and green look). Modelled on Yawelo Idle's page.

## Resume steps

1. `ListAgents`; `git status --short`; `git fetch --prune`; `git rev-parse --abbrev-ref HEAD`.
2. #242/#243/#245 are parked on the broker account. #348 (SonarCloud) is closed: no SonarCloud for steadyhand (Shyden 2026-11-08). Start #251.
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
