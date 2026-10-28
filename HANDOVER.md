# Handover: steadyhand

**Updated:** 2026-10-28 (UTC). Current state only. Older history: `git show fbc261b:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop` = ea66922 (#423 handover; #422 = #377's tracked git hooks, d271ae1). Merge green PRs into develop without asking; never `main`.
- #377 closed (evidence comment), Done. #378 unblocked (link and body line removed, read back). #366 now `blocked_by: #272`. #407, #378, #366 and #272 reworded "both Pythons" to the pinned Python, each with a comment.
- **This clone has `core.hooksPath .githooks`:** every push runs the pre-push (about 20 s) and is refused while anything is uncommitted or untracked, or when the pushed branch is not checked out. Commit or stash first; never `--no-verify`.
- **`../steadyhand-272`** (#272) has develop's `.githooks/pre-push` staged (Shyden "Both", 2026-10-28), beside its uncommitted `tests/guards/test_no_literal_floor.py`; its next step is merging develop. `~/.claude/hooks/git-hooks-present.py` now lets through a merge of one commit holding every missing hook, executable (29 cases, 19 mutants). The docs worktree is removed.
- This handover lands through its own docs PR (`docs/handover-2026-10-28d`).
- Backups (keep 30 days, never delete early): `377/wip-backup-2026-10-28` (74a0a30, until 2026-11-27); `365/exact-values-backup-2026-10-27` (98453d2, until 2026-11-26), `365/exact-values-backup-2026-10-28` (693fab5, until 2026-11-27); `.superpowers/sdd/365/mutations_head.py` and `pr_body_head.py` (until 2026-11-27).
- **#407 open, held** for five limits rounds at one-minute load above 20 (`.superpowers/sdd/407/measure.zsh`).

## Resume steps
1. `ListAgents`; `git status --short` clean; `git fetch` and confirm `develop`'s last ci run on its head is green by job name (`deploy-dev` and `coverage` included).
2. If this handover's docs PR is still open: wait with `~/.claude/scripts/wait-run.sh <repo> <run id> <sha file>`, then `~/.claude/scripts/pr-verdict.sh <pr>` (a one-shot snapshot); merge when green.
3. Next ticket by the queue below (#378 first); one branch per ticket off `develop`; In Progress once its branch exists (`.superpowers/sdd/377/board_status.py <n> "In Progress"`).
4. The laptop runs only unit, lint, format and types; guards, integration and properties run in CI. Before pushing, check statically: the text guards, `assert all/any` or asserting loops in tests, literal workflow counts in `tests/guards` (e.g. `SETUP_NODE_STEPS`), and anything reading the whole working tree (CI locks the fast path unreadable). #290's: `python3 .superpowers/sdd/365/stand_in_rule.py`.

## Waiting on Shyden
- Told 2026-10-28, not ruled: `git-hooks-present.py` does not judge `git pull`, counts a non-executable hook as present (`isfile`), and `git -c core.hooksPath=...` overrides it per command.
- #400 and #308: his settings clicks (`main` strict off then `release-cut`; `coverage` on `main`).
- #394's guard refuses four vi members beyond the ruling's three (told 2026-10-23).
- #272: constant-name `setattr` read like `x.name = value`; its reader refuses `max(...) == x` though #365's ruling named it (comment 2026-10-27). #308's read-only key.
- Whether the floors check should narrow to the files floor guards read.

## Running
Nothing local. No agent.

## Next on the clean-up queue (all before #222)
#378 (3), #348 (5, waits on repo-template#27), #400 (3), #308 (2), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2); #272 (13); #366 (2) after #272; #407 (2) when load allows.

## Progress (2026-10-28, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 40 tickets, 217 points across 39 scored (epic #214 unscored). Closed 2026-10-21 to 2026-10-28: 10 tickets, 61 points (#377 among them).
- **By tickets: 14% complete (4 of 28 EXT stories). ETA 2026-11-24, low confidence:** 39 open scored tickets at 1.43 a day is about 27 days.
- **By effort: 217 points remaining across 39 scored open tickets. ETA 2026-11-22, low confidence:** 8.7 points a day is about 25 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), the key (#308), #272's ruling, #400's and #308's settings clicks, machine load above 20 for #407.

## Notes
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; still no retries.
- `git merge -F -` cannot read stdin: write the message file first (Write tool), then name it literally.
- `git update-ref -d` deletes a branch a worktree has checked out (memory `feedback-update-ref-skips-worktree-check`).
- The floors hook wants the line exactly `Floors: none moved`; put any reason on the line before.
- A commit and a push go in separate commands (push-conflicts-with-develop judges HEAD before the command).
