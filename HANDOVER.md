# Handover: steadyhand

**Updated:** 2026-10-29 (UTC). Current state only. Older history: `git show 013deb8:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

**Shyden is AFK asleep since about 03:40 WIB 2026-10-29** (relayed by shytalk-1e): keep working; park what needs him and ask when he is back.

## Branches and heads
- `develop` = 013deb8 (#433 = #362), green by every job on push run 40776756859. Merge green PRs into develop without asking; never `main`.
- **Closed 2026-10-29:** #341 (PR #428), #337 (every blocker linked; `.superpowers/sdd/337/verify.py`), #320 (PR #431, README), #362 (PR #433, literal-floors reader; floors run 40774892764). Evidence comment per AC on each.
- **Filed #432** (Estimate 2, P3, now workable): bounds through a parameter. Its plants run only in CI: map each new branch to a plant before the first push.
- **#317 waits on Shyden:** its CI check needs a read-only board token he creates (a GitHub App cannot read a user-owned board); noted on the ticket.
- **#336 (P2) parked on Shyden's question** (`.superpowers/sdd/336/question.md`): split about 20 mixed trail tests, or move each whole with a smaller unit copy? Board: Todo. Groundwork: `.superpowers/sdd/336/notes.md`.
- This handover lands through its own docs PR (`docs/handover-2026-10-29b`).
- **Commits and merges:** every code commit carries `Gaps checked:`. Every squash merge, docs too, needs `--body-file` with a section and the literal head SHA (the .md exemption also judges against `origin/main`). Run `git commit -F <file>` alone on its line.
- `core.hooksPath .githooks`: pre-push refuses anything uncommitted or untracked. Never `--no-verify`.
- `../steadyhand-272` (#272): develop's `.githooks/pre-push` staged beside an uncommitted `tests/guards/test_no_literal_floor.py`; its next step is merging develop (the merge message needs a section).
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (74a0a30, until 2026-11-27); `365/exact-values-backup-2026-10-27` (until 2026-11-26) and `-10-28` (until 2026-11-27); `.superpowers/sdd/365/mutations_head.py`, `pr_body_head.py`, `.superpowers/sdd/378/gaps_checked-current-2026-10-28.py` (until 2026-11-27).
- **#407 open, held** for five limits rounds at load above 20 (`.superpowers/sdd/407/measure.zsh`).

## Resume steps
1. `ListAgents`; `git status --short` clean; `git fetch`; develop's last ci run on its head green by job name.
2. If this handover's docs PR is open: `~/.claude/scripts/wait-run.sh <repo> <run id> <sha file>` for its ci and mutations runs, `~/.claude/scripts/pr-verdict.sh <pr>`, then merge with `--match-head-commit <literal sha> --body-file` (a sectioned body).
3. When Shyden is back: ask `.superpowers/sdd/336/question.md` by AskUserQuestion, then plan #336 from the answer (plan reviewed to zero in a scratch worktree, self-approved).
4. Else the next ticket: #432 (P3, 2), then #359 (3). Read `blocked_by:` first; one branch off `develop`, cut after any pending docs PR merges; In Progress once it exists (`.superpowers/sdd/377/board_status.py <n> "In Progress"`). Extension floors move only via `record-floors.yml` on a scratch ref before the first branch push.
5. The laptop runs only unit, lint, format and types. Check the text guards statically before pushing; `python3 .superpowers/sdd/365/stand_in_rule.py`.

## Waiting on Shyden
- **#336's question** (above): split mixed trail tests, or move whole with smaller unit copies.
- **#317's token:** a fine-grained read-only Projects token in a branch-restricted environment, or another route.
- Told 2026-10-29: the gap hook's ".md-only PR needs no section" exemption cannot fire for a PR into develop while develop is ahead of main (it judges against origin/main too).
- Told 2026-10-28, not ruled: `git-hooks-present.py` does not judge `git pull`, counts a non-executable hook as present, and `git -c core.hooksPath=...` overrides it.
- #400 and #308: his settings clicks (`main` strict off then `release-cut`; `coverage` on `main`).
- #394's guard refuses four vi members beyond the ruling's three (told 2026-10-23).
- #272: constant-name `setattr`; its reader refuses `max(...) == x` (comment 2026-10-27). #308's read-only key.
- Whether the floors check should narrow to the files floor guards read.

## Running
Nothing local. No agent.

## Next on the clean-up queue (all before #222)
Recorded priorities: #348 P1 (waits on repo-template#27), #336 P2 (parked), #432 P3; the rest unranked until #315. #400 (3) and #308 (2) on his clicks, #315 (2, repo-template#6), #317 (5, his token), #359 (3); #272 (13); #366 (2) after #272; #407 (2) when load allows.

## Progress (2026-10-29, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 36 tickets, 207 points across 35 scored (epic #214 unscored). Closed 2026-10-22 to 2026-10-29: 14 tickets, 62 points (#341, #337, #320 and #362 among them).
- **By tickets: 14% complete (4 of 28 EXT stories). ETA 2026-11-16, low confidence:** 35 open scored tickets at 2.0 a day is about 18 days.
- **By effort: 207 points remaining across 35 scored open tickets. ETA 2026-11-21, low confidence:** 8.9 points a day is about 23 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), repo-template#27 (#348), the key (#308), #272's ruling, #336's question, #317's token, #400's and #308's settings clicks, load above 20 for #407.

## Notes
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
- `git diff-tree` ignores `--first-parent`: name the two trees.
- The floors hook wants the line exactly `Floors: none moved`; put any reason on the line before. A commit and a push go in separate commands.
