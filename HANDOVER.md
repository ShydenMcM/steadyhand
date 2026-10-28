# Handover: steadyhand

**Updated:** 2026-10-29 (UTC). Current state only. Older history: `git show 52c93e3:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

**Shyden is AFK asleep since about 03:40 WIB 2026-10-29** (relayed by shytalk-1e): keep working through tickets; park anything that needs him.

## Branches and heads
- `develop` = 8687380 (#428 = #341, merged); develop's push run 40767660826 green by every job (`gaps-checked`, `deploy-dev`, `coverage` included). Merge green PRs into develop without asking; never `main`.
- **#341 closed** with an evidence comment per AC; board Done. Local branch `341/no-login-name-in-audit` (b5d4d8c = the merged PR head) may be deleted.
- This handover lands through its own docs PR (`docs/handover-2026-10-29a`).
- **#336 (P2, logs suite) is next.** Groundwork in `.superpowers/sdd/336/` (`notes.md`, `candidates.py`): the ticket's text proxy still finds 46 tests, but misses #341's three planted-name trail checks (the trail read sits in `cli_world` helpers). AC 7's meta-guard must see through helpers.
- **Every code commit carries a `Gaps checked:` section** (`.githooks/commit-msg`, CI `gaps-checked`); each squash merge needs `--body-file` with one (the PR body has it: `.superpowers/sdd/341/pr-body.md`). Stage first, commit in a separate command.
- `core.hooksPath .githooks`: pre-push refuses anything uncommitted or untracked. Never `--no-verify`.
- `../steadyhand-272` (#272): develop's `.githooks/pre-push` staged beside an uncommitted `tests/guards/test_no_literal_floor.py`; its next step is merging develop (the merge message needs a section).
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (74a0a30, until 2026-11-27); `365/exact-values-backup-2026-10-27` (until 2026-11-26) and `-10-28` (until 2026-11-27); `.superpowers/sdd/365/mutations_head.py`, `pr_body_head.py`, `.superpowers/sdd/378/gaps_checked-current-2026-10-28.py` (until 2026-11-27).
- **#407 open, held** for five limits rounds at load above 20 (`.superpowers/sdd/407/measure.zsh`).

## Resume steps
1. `ListAgents`; `git status --short` clean; `git fetch`; develop's last ci run on its head green by job name.
2. If this handover's docs PR is still open: `~/.claude/scripts/wait-run.sh <repo> <run id> <sha file>`, then `~/.claude/scripts/pr-verdict.sh <pr>`; merge when green (docs-only: `--match-head-commit`, no section needed).
3. #336: re-run `python3 .superpowers/sdd/336/candidates.py` on develop; branch `336/logs-suite` off develop, board In Progress (`.superpowers/sdd/377/board_status.py 336 "In Progress"`); brainstorm, then write the plan and review it to zero in a scratch worktree (each pass runs the plan's code: typecheck, unit, guards, predicted mutations), then self-approve. Read `~/.claude/global-rules/reference-guard-forms-and-floors.md` before writing AC 7's guard.
4. The laptop runs only unit, lint, format and types. Check the text guards statically before pushing; `python3 .superpowers/sdd/365/stand_in_rule.py`. Write any script that mentions a git commit to a file and run it by path.

## Waiting on Shyden
- Told 2026-10-28, not ruled: `git-hooks-present.py` does not judge `git pull`, counts a non-executable hook as present, and `git -c core.hooksPath=...` overrides it.
- #400 and #308: his settings clicks (`main` strict off then `release-cut`; `coverage` on `main`).
- #394's guard refuses four vi members beyond the ruling's three (told 2026-10-23).
- #272: constant-name `setattr`; its reader refuses `max(...) == x` (comment 2026-10-27). #308's read-only key.
- Whether the floors check should narrow to the files floor guards read.

## Running
Nothing local. No agent.

## Next on the clean-up queue (all before #222)
Recorded priorities: #336 P2 (next), #337 P3; the rest unranked until #315 adds the board field. #348 (5, waits on repo-template#27), #400 (3), #308 (2), #315 (2, waits on repo-template#6), #317 (5), #320 (2), #337 (3), #336 (5), #359 (3), #362 (2); #272 (13); #366 (2) after #272; #407 (2) when load allows.

## Progress (2026-10-29, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 38 tickets, 212 points across 37 scored (epic #214 unscored). Closed 2026-10-22 to 2026-10-29: 11 tickets, 55 points (#341 among them).
- **By tickets: 14% complete (4 of 28 EXT stories). ETA 2026-11-22, low confidence:** 37 open scored tickets at 1.57 a day is about 24 days.
- **By effort: 212 points remaining across 37 scored open tickets. ETA 2026-11-25, low confidence:** 7.9 points a day is about 27 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), repo-template#27 (#348), the key (#308), #272's ruling, #400's and #308's settings clicks, load above 20 for #407.

## Notes
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
- `git diff-tree` ignores `--first-parent`: name the two trees.
- The floors hook wants the line exactly `Floors: none moved`; put any reason on the line before. A commit and a push go in separate commands.
