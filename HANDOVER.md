# Handover: steadyhand

**Updated:** 2026-10-30 (UTC). Current state only. Older history: `git show d66cdce:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`.

**Ruling 2026-10-30 (every project, CLAUDE.md "Value test before EVERY decision", `~/.claude/global-rules/pending-keep-it-simple.md`):** stop checking checks. Floors, mutations, CPU/load limits, workflow-line coverage, meta-guards, population counts, `Floors:` lines and "Gaps checked" sections are DROPPED. Coverage becomes one overall threshold. Product work first. Do not edit the global layer: send global cuts to repo-template-af.

## Branches and heads
- `develop` = aafabe4, green (push run 40915551537). Merge green PRs into develop without asking; never `main`.
- **This file: edited on disk in the main checkout (on `develop`), NOT committed**; the next docs PR carries it.
- Closed 2026-10-30 as not needed (Shyden confirmed): #222, #272, #317, #336, #366, #407, #442, #444, #445. Their worktrees are removed (local branches kept), except `../steadyhand-272`, which holds 2 uncommitted files.
- Scratch branches `coverage/336/logs-suite` and `coverage/444/check-name-clash` are still on origin: pre-push refuses while this file is uncommitted. Delete them with the next docs push.
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (to 2026-11-27); `365/exact-values-backup-2026-10-27` (to 2026-11-26), `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29).

## Done this session
- Filed #443 (Node in a Dockerfile Dependabot bumps; blocked by repo-template#143; 3 pts, P1), #444 (P0, check-name clash; built, then moot), #445 (1 pt), #446 (the ONE cleanup ticket, 8 pts, P2).
- Ruling on #444 recorded ("Leave trunk pushes out"). #442 re-scored 3, blocked by #444.
- Global hook `test-isolation.py` now reads scripts started by their own path (my `gate444.sh` ran pytest unlocked). Edited BEFORE the "don't edit the global layer" message; reported to repo-template-af.

## Waiting on Shyden
- Keep or revert the test-isolation hook change (on repo-template-af's list for him, recommended keep).
- #317's token is moot (closed). #400's and #308's clicks; #446 will need him to drop `mutations` and `gaps-checked` from required checks.

## Resume steps
1. `ListAgents`; `git status --short`; `git fetch`.
2. Commit this file in a docs PR into develop; then delete the two scratch branches.
3. **#223** (EXT S4a, 8, now unblocked): core money, decimal ratios, rule files to JSON with a row check, trading days. Plain tests, no new check machinery (value test first).
4. #446 (cleanup, 8) when a PR fights the machinery, or after #223.

## Running
Nothing local. No agent. Checked 2026-10-30 before Shyden's Mac reboot: `develop` = aafabe4, this file the only uncommitted change in the main checkout (it lives in the repo, so it survives the reboot); `../steadyhand-272` still holds its 2 uncommitted files (#272 closed as not needed). Nothing depends on `$TMPDIR` or /tmp.

## Progress (2026-10-30, `uv run --locked python .superpowers/sdd/estimates/progress.py`, after the nine closes; `post-launch` left out)
- **Measured:** EXT 4 of 27 stories closed (21 of 176 points; #222 left the release as not needed). Board open: 31 tickets, 181 points across 30 scored (epic #214 unscored). Closed 2026-10-23 to 2026-10-30: 15 tickets done, 53 points, plus 9 closed as not needed.
- **By tickets: 15% complete (4 of 27 EXT stories). ETA 2026-11-13, low confidence:** 30 open scored tickets at 2.1 a day is about 14 days.
- **By effort: 181 points remaining across 30 scored open tickets. ETA 2026-11-23, low confidence:** 7.6 points a day is about 24 days.
- **Assumed:** last week's pace holds, though it went to checks, not product; the EXT stories are larger. **Outside waits:** broker account (#242), Web Store review, repo-template#143, #6 and #27.

## Notes
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
- Peer rules 2026-10-30: copied comments cite `owner/repo#N` in full. Shyden unwired 21 paperwork hooks the same day (handover size, peer labels, shell quoting, CI rituals); 25 remain (production, consent, git history, backups, secrets, test lock).
