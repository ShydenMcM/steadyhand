# Handover: steadyhand

**Updated:** 2026-10-28 (UTC). Current state only. Older history: `git show 34939da:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop` = 731c306 (#425 = #378, merged; develop's push run 40727223485 green by every job). Merge green PRs into develop without asking; never `main`.
- **#378 closed** with an evidence comment per AC. Done. `gaps-checked` is now in `develop`'s required checks (read back: 13 contexts, strict). Shyden's rulings are on the ticket. One consequence of "First-parent on a push": **a release merge message to `main` carries the section.**
- **Every code commit here now carries a `Gaps checked:` section.** `.githooks/commit-msg` checks it locally; CI's `gaps-checked` job checks it on every PR and every push to develop or main. A commit of only `.md` files is exempt. Stage first, then commit in a separate command: the global hook judges before `git add` runs.
- **Every squash merge needs `--body-file` with a section.** The global `~/.claude/hooks/gaps-checked-in-commits.py` (not in git) now judges `gh pr merge` and the pulls merge API (142 cases, 15 of 15 mutants). A docs-only PR needs none once `--match-head-commit` names its head. Backup: `.superpowers/sdd/378/hook-backup-2026-10-28/` (until 2026-11-27).
- **This clone has `core.hooksPath .githooks`:** pre-push (about 20 s) refuses anything uncommitted or untracked. Never `--no-verify`.
- **`../steadyhand-272`** (#272): develop's `.githooks/pre-push` staged beside an uncommitted `tests/guards/test_no_literal_floor.py`. Its next step is merging develop, which brings `commit-msg` too, so the merge message needs a section.
- This handover lands through its own docs PR (`docs/handover-2026-10-28f`). #426 was closed as stale.
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (74a0a30, until 2026-11-27); `365/exact-values-backup-2026-10-27` (until 2026-11-26) and `-10-28` (until 2026-11-27); `.superpowers/sdd/365/mutations_head.py`, `pr_body_head.py`, `.superpowers/sdd/378/gaps_checked-current-2026-10-28.py` (until 2026-11-27).
- **#407 open, held** for five limits rounds at load above 20 (`.superpowers/sdd/407/measure.zsh`).

## Resume steps
1. `ListAgents`; `git status --short` clean; `git fetch`; confirm `develop`'s last ci run on its head is green by job name (`gaps-checked`, `deploy-dev` and `coverage` included).
2. If this handover's docs PR is still open: `~/.claude/scripts/wait-run.sh <repo> <run id> <sha file>`, then `~/.claude/scripts/pr-verdict.sh <pr>`; merge when green (docs-only: `--match-head-commit`, no section needed).
3. Next ticket by the queue below. #348 waits on repo-template#27, #400 and #308 on Shyden's clicks, #315 on repo-template#6, so the first workable one is likely #317: read each one's `blocked_by:` first. One branch per ticket off `develop`; In Progress once its branch exists (`.superpowers/sdd/377/board_status.py <n> "In Progress"`).
4. The laptop runs only unit, lint, format and types. Check the text guards statically before pushing; `python3 .superpowers/sdd/365/stand_in_rule.py`. Write any script that mentions a git commit to a file and run it by path: the gap hook reads a heredoc's text as a commit.

## Waiting on Shyden
- Told 2026-10-28, not ruled: `git-hooks-present.py` does not judge `git pull`, counts a non-executable hook as present, and `git -c core.hooksPath=...` overrides it.
- #400 and #308: his settings clicks (`main` strict off then `release-cut`; `coverage` on `main`).
- #394's guard refuses four vi members beyond the ruling's three (told 2026-10-23).
- #272: constant-name `setattr`; its reader refuses `max(...) == x` (comment 2026-10-27). #308's read-only key.
- Whether the floors check should narrow to the files floor guards read.

## Running
Nothing local. No agent.

## Next on the clean-up queue (all before #222)
#348 (5, waits on repo-template#27), #400 (3), #308 (2), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2); #272 (13); #366 (2) after #272; #407 (2) when load allows.

## Progress (2026-10-28, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 39 tickets, 214 points across 38 scored (epic #214 unscored). Closed 2026-10-21 to 2026-10-28: 11 tickets, 66 points (#378 among them).
- **By tickets: 14% complete (4 of 28 EXT stories). ETA 2026-11-22, low confidence:** 38 open scored tickets at 1.57 a day is about 24 days.
- **By effort: 214 points remaining across 38 scored open tickets. ETA 2026-11-20, low confidence:** 9.4 points a day is about 23 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), repo-template#27 (#348), the key (#308), #272's ruling, #400's and #308's settings clicks, load above 20 for #407.

## Notes
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
- `git diff-tree` ignores `--first-parent`: name the two trees.
- The floors hook wants the line exactly `Floors: none moved`; put any reason on the line before. A commit and a push go in separate commands.
