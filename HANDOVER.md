# Handover: steadyhand

**Updated:** 2026-10-28 (UTC). Current state only. Older history: `git show 48bae32:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop` = 87cd2e0 (#418, #365's exact values). Merge green PRs into develop without asking; never `main`.
- #365 closed (evidence comment), Done on the board; #272's blocked-by link to #365 removed and read back (its links now #367, #381, #374, all closed).
- #419 (msgpack CVE-2026-114613) closed: PR #420, 789e2f0.
- This handover lands through its own docs PR (`docs/handover-2026-10-28`).
- Backups (keep 30 days, never delete early): `365/exact-values-backup-2026-10-27` (98453d2, until 2026-11-26), `365/exact-values-backup-2026-10-28` (693fab5, until 2026-11-27); `.superpowers/sdd/365/mutations_head.py` and `pr_body_head.py` (until 2026-11-27).
- **#407 open, held** for five limits rounds at one-minute load above 20 (`.superpowers/sdd/407/measure.zsh`).

## Resume steps
1. `ListAgents`; `git status --short` clean; `git fetch` and confirm `develop`'s last ci run on its head is green by job name (`deploy-dev` and `coverage` included).
2. If the docs PR for this handover is still open: `~/.claude/scripts/pr-verdict.sh <pr>`, merge when green.
3. Take the next ticket by Priority from the queue below (#366 first); one branch per ticket off `develop`; set it In Progress only once its branch exists.
4. The laptop runs only unit, lint, format and types; guards, properties and integration run in CI. Before pushing a change to tests a guard reads, check that guard's rule statically (#290's: `python3 .superpowers/sdd/365/stand_in_rule.py`).

## Waiting on Shyden
- #400 and #308: his settings clicks (`main` strict off then `release-cut`; `coverage` on `main`).
- #394's guard refuses four vi members beyond the ruling's three (told 2026-10-23).
- #272: constant-name `setattr` read like `x.name = value`; its reader refuses `max(...) == x` though #365's ruling named it (comment 2026-10-27). #308's read-only key.
- Whether the floors check should narrow to the files floor guards read.

## Running
Nothing local. No agent.

## Next on the clean-up queue (all before #222)
#366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #400 (3), #308 (2), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2); #272 (13), now unblocked by #365; #407 (2) when load allows.

## Progress (2026-10-28, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 41 tickets, 219 points across 40 scored (epic #214 unscored). Closed 2026-10-21 to 2026-10-28: 9 tickets, 59 points (#419 and #365 among them).
- **By tickets: 14% complete (4 of 28 EXT stories). ETA 2026-11-28, low confidence:** 40 open scored tickets at 1.29 a day is about 31 days.
- **By effort: 219 points remaining across 40 scored open tickets. ETA 2026-11-23, low confidence:** 8.4 points a day is about 26 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), the key (#308), #272's ruling, #400's and #308's settings clicks, machine load above 20 for #407.

## Notes
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; still no retries.
- `git merge -F -` cannot read stdin: write the message file first (Write tool), then name it literally.
- `git update-ref -d` deletes a branch a worktree has checked out (memory `feedback-update-ref-skips-worktree-check`).
