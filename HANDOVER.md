# Handover: steadyhand

**Updated:** 2026-10-29 (UTC). Current state only. Older history: `git show 53f1749:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

**Shyden is AFK asleep since about 03:40 WIB 2026-10-29** (relayed by shytalk-1e): keep working; park what needs him and ask when he is back.

## Branches and heads
- `develop` = 53f1749, its last code merge 8687380 (#341) green by every job on push run 40767660826. Merge green PRs into develop without asking; never `main`.
- **Closed today:** #341 (PR #428; audit lines name no one) and #337 (every blocker linked: 39 bodies gained a `blocked_by:` line, 80 links; 53 open issues judged, all match; tools `.superpowers/sdd/337/verify.py`). Each has an evidence comment per AC.
- **#336 (P2) is parked on Shyden's question** (`.superpowers/sdd/336/question.md`): about 20 trail tests are mixed (trail plus behaviour); split them, or move each whole with a smaller unit copy? Routes differ in reach, so his call. Board: Todo. Groundwork and hand classification in `.superpowers/sdd/336/notes.md`.
- This handover lands through its own docs PR (`docs/handover-2026-10-29b`).
- **Commits and merges:** every code commit carries a `Gaps checked:` section. **Every squash merge, docs included, needs `--body-file` with a section and the literal head SHA:** the hook's .md exemption compares against `origin/main` too, which develop's lead always fails (measured: 402 non-md files). Run `git commit -F <file>` alone on its line (a `cd`, redirect or `tail` beside it hides the stage from the hook).
- `core.hooksPath .githooks`: pre-push refuses anything uncommitted or untracked. Never `--no-verify`.
- `../steadyhand-272` (#272): develop's `.githooks/pre-push` staged beside an uncommitted `tests/guards/test_no_literal_floor.py`; its next step is merging develop (the merge message needs a section).
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (74a0a30, until 2026-11-27); `365/exact-values-backup-2026-10-27` (until 2026-11-26) and `-10-28` (until 2026-11-27); `.superpowers/sdd/365/mutations_head.py`, `pr_body_head.py`, `.superpowers/sdd/378/gaps_checked-current-2026-10-28.py` (until 2026-11-27).
- **#407 open, held** for five limits rounds at load above 20 (`.superpowers/sdd/407/measure.zsh`).

## Resume steps
1. `ListAgents`; `git status --short` clean; `git fetch`; develop's last ci run on its head green by job name.
2. If this handover's docs PR is open: `~/.claude/scripts/wait-run.sh <repo> <run id> <sha file>` for its ci and mutations runs, `~/.claude/scripts/pr-verdict.sh <pr>`, then merge with `--match-head-commit <literal sha> --body-file` (a sectioned body).
3. When Shyden is back: ask `.superpowers/sdd/336/question.md` by AskUserQuestion, then plan #336 from the answer (plan reviewed to zero in a scratch worktree, self-approved).
4. Otherwise the next workable ticket: no recorded Priority separates #317 (5), #320 (2), #359 (3), #362 (2); take them in that order, reading each one's `blocked_by:` first. One branch per ticket off `develop`; In Progress once its branch exists (`.superpowers/sdd/377/board_status.py <n> "In Progress"`).
5. The laptop runs only unit, lint, format and types. Check the text guards statically before pushing; `python3 .superpowers/sdd/365/stand_in_rule.py`.

## Waiting on Shyden
- **#336's question** (above): split mixed trail tests, or move whole with smaller unit copies.
- Told 2026-10-29: the gap hook's ".md-only PR needs no section" exemption cannot fire for a PR into develop while develop is ahead of main (it judges against origin/main too).
- Told 2026-10-28, not ruled: `git-hooks-present.py` does not judge `git pull`, counts a non-executable hook as present, and `git -c core.hooksPath=...` overrides it.
- #400 and #308: his settings clicks (`main` strict off then `release-cut`; `coverage` on `main`).
- #394's guard refuses four vi members beyond the ruling's three (told 2026-10-23).
- #272: constant-name `setattr`; its reader refuses `max(...) == x` (comment 2026-10-27). #308's read-only key.
- Whether the floors check should narrow to the files floor guards read.

## Running
Nothing local. No agent.

## Next on the clean-up queue (all before #222)
Recorded priorities: #336 P2 (parked), #348 P1 (waits on repo-template#27); the rest unranked until #315 adds the board field. #400 (3) and #308 (2) on his clicks, #315 (2, waits on repo-template#6), #317 (5), #320 (2), #359 (3), #362 (2); #272 (13); #366 (2) after #272; #407 (2) when load allows.

## Progress (2026-10-29, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 37 tickets, 209 points across 36 scored (epic #214 unscored). Closed 2026-10-22 to 2026-10-29: 12 tickets, 58 points (#341 and #337 among them).
- **By tickets: 14% complete (4 of 28 EXT stories). ETA 2026-11-19, low confidence:** 36 open scored tickets at 1.71 a day is about 21 days.
- **By effort: 209 points remaining across 36 scored open tickets. ETA 2026-11-23, low confidence:** 8.3 points a day is about 25 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), repo-template#27 (#348), the key (#308), #272's ruling, #336's question, #400's and #308's settings clicks, load above 20 for #407.

## Notes
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
- `git diff-tree` ignores `--first-parent`: name the two trees.
- The floors hook wants the line exactly `Floors: none moved`; put any reason on the line before. A commit and a push go in separate commands.
