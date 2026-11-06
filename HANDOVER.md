# Handover: steadyhand

**Updated:** 2026-11-06, #239 restarted after a TDD slip. Current state only. Older history: `git show d66cdce:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here (desktop extension; phones unavailable anyway).

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

## Branches and heads
- `develop` = 3c446c7 (handover PR #510).
- `239/settings-history-lessons-2` = fresh branch from origin's `239/settings-history-lessons` (a238443, includes f263e1f); not pushed yet; #239 In Progress. Open the PR from this branch.
- Slip 2026-11-06: I wrote core `registeredStrategy` with its test in one edit. Shyden ruled a fresh branch ("this is the consequences of your actions"). The day's work (keptAdvisers, tabs, the start of the strategy picker) is on `239/slip-backup-2026-11-06` (16180e5, kept to 2026-12-06): **never copy or replay from it**; write tests and code new. The local `239/settings-history-lessons` (c4bebaf) holds the same dropped commits: leave it alone.
- `238/extension-shell` merged (PR #500); delete locally only after checking its tip equals PR #500's head 3f3dd12.
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (to 2026-11-27); `365/exact-values-backup-2026-10-27` (to 2026-11-26), `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29).

## Running
- Nothing local. Docker/Colima: never used by this session.

## #239 (Settings, History, Lessons, paste and import), done so far
- Ruling 2026-11-06 (on #239): M7 bounds yield_stocks 1-45, paid_years 1-10, momentum_stocks 1-45, fast_days 1-499, slow_days 2-500, momentum_months 2-24, skip_months 0-23.
- 48c37e2: `core/src/strategies.ts`: `STRATEGIES` (six, dividend-growth first) with bounds and help; `strategyFrom(name, values)` refuses by name.
- f263e1f: `shell/src/settings.ts`: kept-shape readers/writers for strategy, risk limits, fee preset (keys in `KEPT`), and typed readers (`typedStrategy`, `typedLimits` as percentages). `shippedTables` now exported from core. Unit 3333 passed, 100% coverage.
- Left, all written new, each test run red in its own call before any src edit: (a) the panel advises and records with the kept strategy, limits and fee preset (panel.ts hard-codes `dividendGrowth()`, `new RiskLimits()`, `new IdxMarketRules()`); `refusedSetting` once, in settings.ts. (b) tabs Advice/Settings/History/Lessons; Settings: strategy select + a labelled input per setting (help as aria-describedby), goal, limits, fee preset, universe, exclusions, typed deposits/withdrawals (history `recordTyped`, not exported from history's index yet); History: per stock days, chart reads, dividends, the recording-only-while-open note, "forget everything" confirmed in the panel (no browser dialog), then empty (`forgetEverything` in history/src/forget.ts, not exported); Lessons (catalogue; content EXT S17); paste box + file picker feeding `recordRead`. The journey must click Settings before typing the universe. (c) browser suite drives each tab with real clicks and typing. (d) PR, CI, verify each AC. Note: a kept strategy name no strategy has should be refused by `strategyOf`; strategyFrom's bound message reads "fast_days must be from 1 to 499, got 0".

## Waiting
- #308, #400 (main protection) and #348 (SonarCloud): Shyden's.

## Resume steps
1. `ListAgents`; `git status --short`; `git fetch --prune`; `git rev-parse --abbrev-ref HEAD`.
2. Resume #239 on `239/settings-history-lessons-2` at "Left" (a): a test-only call, a red run, then src.
3. After #239, next ticket: `node ~/Developer/Repos/repo-template/scripts/board-next.ts PVT_kwHOCQ_jzM4BkhEb steadyhand 2>/dev/null`.
4. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage; scratch copies go in `pristine/`, never `*.bak`. Guards (Python and extension), integration and the browser suite are CI's: the hook refuses them locally.
5. Filing a ticket: `gh issue create`, `gh project item-add 1 --owner ShydenMcM --url <issue>`, `gh project item-edit` (project id `PVT_kwHOCQ_jzM4BkhEb`) with Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue. Blocked-by: `gh api -X POST repos/ShydenMcM/steadyhand/issues/<n>/dependencies/blocked_by -F issue_id=<blocker database id>`.

## Notes
- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. `git commit --amend` is refused by auto mode: add a commit.
- Throwaway probe files carry a file-level `# ruff: noqa` / `/* eslint-disable */` so pre-push passes.
- A PreToolUse refusal drops the whole command, edits included: re-apply them.
- The editor's TypeScript diagnostics disagree with `tsc --noEmit`; tsc is the authority.
- Test runs queue machine-wide behind other projects: background long runs.
- A CI job's log: `gh run view <run> --log --job <job id>`.
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
