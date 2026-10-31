# Handover: steadyhand

**Updated:** 2026-10-31 (UTC). Current state only. Older history: `git show d66cdce:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`.

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision. Do not edit the global layer: send global cuts to repo-template-af.

## Branches and heads
- `develop` = b931850 (PR #449 squash, #223 closed 2026-10-31 with every criterion checked on the ticket; AC3 reworded by Shyden: rule JSON lives in `extension/packages/core/rules/`). Merge green PRs into develop without asking; never `main`.
- Required checks: develop 11 (incl. `coverage`), main 10.
- No feature branch open. Worktrees for #223 and #446 removed (tips were the merged heads). `../steadyhand-272` still holds 2 uncommitted files (#272 closed as not needed).
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (to 2026-11-27); `365/exact-values-backup-2026-10-27` (to 2026-11-26), `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29).

## Next ticket
- The board has **no Priority field** (fields read 2026-10-31), so Priority cannot pick yet. **#315** (2 points) adds it; its blocker shyden-labs/repo-template#6 is closed and PR #7 is merged, so it is unblocked. Then **#224** (EXT S4b, 13) or **#225** (EXT S4c, 3), both unblocked by #223.

## Waiting on Shyden
- Delete the scratch branches `coverage/336/logs-suite` and `coverage/444/check-name-clash` on origin (auto mode refused the delete).
- Keep or revert the test-isolation hook change (recommended keep).

## Resume steps
1. `ListAgents`; `git status --short`; `git fetch`.
2. Start #315 on a branch from `develop` (read the ticket and repo-template's `board-next` first; this repo reads, never edits, repo-template).
3. Then #224 or #225, by the Priority #315 sets.

## Running
Nothing.

## Progress (2026-10-31, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 5 of 27 stories closed (29 of 176 points). Board: 29 open, 165 points (#214 epic unscored). Closed 2026-10-24 to 2026-10-31: 14 tickets, 63 points.
- **By tickets: 19% complete (5 of 27 EXT stories). ETA 2026-11-15, low confidence:** 29 open tickets at 2.0 a day.
- **By effort: 165 points remaining across 28 scored open tickets. ETA 2026-11-18, low confidence:** 9.0 points a day.
- **Assumed:** last week's pace holds (most of it went to checks, not product). **Outside waits:** broker account (#242), Web Store review, repo-template#143.

## Notes
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
- Copied comments cite `owner/repo#N` in full.
