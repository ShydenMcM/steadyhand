# Handover: steadyhand

**Updated:** 2026-10-28 (UTC). Current state only. Older history: `git show 34939da:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop` = 34939da. Merge green PRs into develop without asking; never `main`.
- **#378 In Progress, PR #425** (`378/gaps-checked`, head c008ad9, both commits pushed; `.superpowers/sdd/378/head.sha`). A `.githooks/commit-msg` hook plus a `gaps-checked` CI job (`scripts/gaps_checked.py commit-msg | range | landed`). First run (862565e) was red: `git diff-tree` ignores `--first-parent`, the range tests read joined streams, and #377's pre-push test plant had a bare message. All fixed in c008ad9. Waiting on ci 40726275004 and mutations 40726274943.
- Shyden's #378 rulings (on the ticket; AC6, AC7, Estimate 3 to 5): "Name it, CI is the gate" (the hook cannot see `--amend`), "Judge it at merge + after", "First-parent on a push" (**a release merge message to `main` now carries the section**).
- `~/.claude/hooks/gaps-checked-in-commits.py` (global, not in git) now judges `gh pr merge` bodies and the pulls merge API, and reads file lists with renames off: 142 cases, 15 of 15 mutants. **Every squash merge now needs `--body-file` with a section** (a docs-only PR needs none once `--match-head-commit` names its head). Backup: `.superpowers/sdd/378/hook-backup-2026-10-28/` (until 2026-11-27).
- **This clone has `core.hooksPath .githooks`:** pre-push (about 20 s) refuses anything uncommitted or untracked; once #425 merges, commit-msg refuses a code commit without its section. Never `--no-verify`.
- **`../steadyhand-272`** (#272): develop's `.githooks/pre-push` staged beside an uncommitted `tests/guards/test_no_literal_floor.py`; next step is merging develop, which after #425 brings `commit-msg` too (the merge message needs a section).
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (74a0a30, until 2026-11-27); `365/exact-values-backup-2026-10-27` (until 2026-11-26) and `-10-28` (until 2026-11-27); `.superpowers/sdd/365/mutations_head.py`, `pr_body_head.py`, `.superpowers/sdd/378/gaps_checked-current-2026-10-28.py` (until 2026-11-27).
- **#407 open, held** for five limits rounds at load above 20 (`.superpowers/sdd/407/measure.zsh`).

## Resume steps
1. `ListAgents`; `git status --short` clean; `git fetch`.
2. Read ci 40726275004 and mutations 40726274943 by job name (`gaps-checked`, `integration (py3.13)`, `coverage`, `deploy-dev`; mutations `11 of 11` plus baseline), each on `headRefOid` c008ad9 (`gh pr view 425 --json headRefOid`). If one died: `~/.claude/scripts/wait-run.sh <repo> <run id> .superpowers/sdd/378/head.sha`.
3. Green: squash-merge #425 with `--match-head-commit "$(cat .superpowers/sdd/378/head.sha)"` and `--body-file` whose text carries a `Gaps checked:` section (the global hook refuses one without). Then add `gaps-checked` to `develop`'s `required_status_checks.contexts` and read it back (AC2); if the App cannot, ask Shyden. Read the push-to-develop ci run's `gaps-checked` job (AC6, `landed` mode), then close #378 with an evidence comment per AC.
4. Red: read the failing job's log (`gh api --allow-escape-sequences repos/ShydenMcM/steadyhand/actions/jobs/<id>/logs`), fix, gate (`zsh -f .superpowers/sdd/378/gate.sh`), unit mutations (`.superpowers/sdd/378/mutate_unit.py` under the test lock), new commit, push.
5. Next ticket by the queue below. The laptop runs only unit, lint, format and types; check the text guards statically before pushing; `python3 .superpowers/sdd/365/stand_in_rule.py`.

## Waiting on Shyden
- Told 2026-10-28, not ruled: `git-hooks-present.py` does not judge `git pull`, counts a non-executable hook as present, and `git -c core.hooksPath=...` overrides it.
- #400 and #308: his settings clicks (`main` strict off then `release-cut`; `coverage` on `main`).
- #394's guard refuses four vi members beyond the ruling's three (told 2026-10-23).
- #272: constant-name `setattr`; its reader refuses `max(...) == x` (comment 2026-10-27). #308's read-only key.
- Whether the floors check should narrow to the files floor guards read.

## Running
ci 40726275004 and mutations 40726274943 on GitHub (survive `/clear`); this session's waiters on them die with it. No agent.

## Next on the clean-up queue (all before #222)
#378 (5, in PR), #348 (5, waits on repo-template#27), #400 (3), #308 (2), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2); #272 (13); #366 (2) after #272; #407 (2) when load allows.

## Progress (2026-10-28, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 40 tickets, 219 points across 39 scored (epic #214 unscored). Closed 2026-10-21 to 2026-10-28: 10 tickets, 61 points.
- **By tickets: 14% complete (4 of 28 EXT stories). ETA 2026-11-24, low confidence:** 39 open scored tickets at 1.43 a day is about 27 days.
- **By effort: 219 points remaining across 39 scored open tickets. ETA 2026-11-22, low confidence:** 8.7 points a day is about 25 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), the key (#308), #272's ruling, #400's and #308's settings clicks, load above 20 for #407.

## Notes
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
- Write any script that mentions a git commit to a file and run it by path: the gap hook reads a heredoc's text as a commit.
- `git diff-tree` ignores `--first-parent`: name the two trees.
- The floors hook wants the line exactly `Floors: none moved`; put any reason on the line before. A commit and a push go in separate commands.
