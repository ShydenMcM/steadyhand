# Handover: steadyhand

**Updated:** 2026-10-29 (UTC), before a computer restart Shyden asked for. Current state only. Older history: `git show e3f633d:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop` = e3f633d, green. Merge green PRs into develop without asking; never `main`.
- **#432 open on `432/literal-floors-through-parameters` = e632d76 (pushed, equal to origin), PR #435.** Floors folded (run 40778504888). Its ci run 40778779806 and mutations run 40778780015 were running at the restart; their waiter died with it. Board: In Progress.
- This handover: docs PR on `docs/handover-2026-10-29d`.
- **Closed 2026-10-29:** #341, #337, #320, #362 (evidence comment per AC on each). Filed #432.
- **Commits and merges:** every code commit carries `Gaps checked:`. Every squash merge, docs too, needs `--body-file` with a section and the literal head SHA. Run `git commit -F <file>` alone on its line; push before `gh pr create`, in separate calls.
- `core.hooksPath .githooks`: pre-push refuses anything uncommitted or untracked. Never `--no-verify`.
- `../steadyhand-272` (#272): develop's `.githooks/pre-push` staged beside an uncommitted `tests/guards/test_no_literal_floor.py`; next step is merging develop (the message needs a section).
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (74a0a30, until 2026-11-27); `365/exact-values-backup-2026-10-27` (until 2026-11-26) and `-10-28` (until 2026-11-27); `.superpowers/sdd/365/mutations_head.py`, `pr_body_head.py`, `.superpowers/sdd/378/gaps_checked-current-2026-10-28.py` (until 2026-11-27).
- **#407 open, held** for five limits rounds at load above 20 (`.superpowers/sdd/407/measure.zsh`).

## Resume steps
1. `ListAgents`; `git status --short` clean; `git fetch`.
2. #435: `gh pr view 435 --json headRefOid`; it must read e632d768f84a7916e0d471bae5ce2afdf66ac80b (`.superpowers/sdd/432/pr-head.txt`). Then `~/.claude/scripts/wait-run.sh <repo> 40778779806 .superpowers/sdd/432/pr-head.txt`, the same for 40778780015, then `~/.claude/scripts/pr-verdict.sh 435`. Read `mutations-report.md` (`gh run download 40778780015`): Q1-Q7 all as predicted.
3. Green: `gh pr merge 435 --squash --match-head-commit e632d768f84a7916e0d471bae5ce2afdf66ac80b --body-file .superpowers/sdd/432/pr-body.md`; develop's push run green by job; close #432 with an evidence comment per AC; board Done. Red: read the failure (guards branch coverage is 100%), fix in a new commit.
4. This handover's docs PR: wait its ci, then merge with `--body-file` (a section) and the literal head SHA.
5. Every remaining clean-up ticket waits on Shyden, another repo or load (below). Ask him the three questions first.

## Waiting on Shyden
- **#336:** about 20 trail tests are mixed (trail plus behaviour): split each, or move whole with a smaller unit copy? `.superpowers/sdd/336/question.md` (ask by AskUserQuestion).
- **#317:** a fine-grained read-only Projects token in a branch-restricted environment (a GitHub App cannot read his user-owned board).
- **#359:** repo-template's story form: he pastes `.github/ISSUE_TEMPLATE/story.yml` and `config.yml` from its develop, or allows the read (a relayed read through repo-template's session is the same read).
- Told 2026-10-29: the gap hook's ".md-only PR needs no section" exemption never fires while develop is ahead of main.
- Told 2026-10-28, not ruled: `git-hooks-present.py` gaps (`git pull`, a non-executable hook, `-c core.hooksPath`).
- #400 and #308: his settings clicks. #394's four vi members. #272's `setattr` ruling and #308's key. Whether the floors check narrows to the files floor guards read.

## Running
Nothing local after the restart: the #435 waiter dies with it (re-run in step 2). No agent.

## Queue
#348 P1 (repo-template#27), #336 P2 (his question), #432 P3 (PR #435); #400 (3) and #308 (2) his clicks, #315 (2, repo-template#6), #317 (5, token), #359 (3, form); #272 (13, ruling); #366 (2) after #272; #407 (2) at load above 20.

## Progress (2026-10-29, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 36 tickets, 207 points across 35 scored (epic #214 unscored). Closed 2026-10-22 to 2026-10-29: 14 tickets, 62 points.
- **By tickets: 14% complete (4 of 28 EXT stories). ETA 2026-11-16, low confidence:** 35 open scored tickets at 2.0 a day is about 18 days.
- **By effort: 207 points remaining across 35 scored open tickets. ETA 2026-11-21, low confidence:** 8.9 points a day is about 23 days.
- **Assumed:** last week's pace holds; it will not while most of the queue waits on him. **Outside waits:** broker account (#242), Web Store review, repo-template#6 and #27, #336's question, #317's token, #359's form, #272's ruling, #400's and #308's clicks, load for #407.

## Notes
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
- Extension floors move only through `record-floors.yml` on a scratch ref before a branch's first push; map every new guard branch to a plant first.
- The floors hook wants `Floors: none moved` or `Floors: recorded in run <id>`.
