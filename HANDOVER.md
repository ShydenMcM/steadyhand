# Handover: steadyhand

**Updated:** 2026-10-16 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (`fb6f739` when written, PR #344). Merge green PRs into `develop` without asking; never `main`.
- `docs-handover-345-audit-trail`: this file, one docs commit, PR into `develop`.
- Local branches left from earlier: `docs-handover-288-done` (PR #344 merged), `288-mutations-in-ci`, `288-pin-mutation-limit`. Delete each only once its tip is confirmed as a merged PR head.

## Done this session (2026-10-16)
- **Logging is two systems** (Shyden, global, "SPLIT the same day" in `reference-engineering-standards.md`): diagnostic logs (repo-template#18, #19, #22, #23) and audit trails (repo-template#24, #25). #339 (the extension's on-device log) is the first kind: its body now names repo-template#19 as a blocker (the GitHub link already existed) and points to #345. **#345 filed** (5, P4, `post-launch`): the paper `audit` table adopts repo-template#25. Shyden chose "Ticket it, after release". Blocked by repo-template#25, #336 and #341, all linked and read back.
- **#288 closed.** PR #342 (`9ff5167`): `mutations.yml` runs on every PR, with a plan step that fails a PR changing a non-unit test no mutation file targets. PR #343 (`12d5160`): the step's limit is 23 min, four times the slowest of three measured runs (5 min 35 s). AC 4's broken-anchor proof: run 38873554741 failed on `B1: the anchor matches 0 times`, with P1 still judged. AC 1 reworded in the issue body (every PR, no label; `HYPOTHESIS_PROFILE=ci` obsolete since #290).
- **#292 closed** (30 of 30 red as predicted) and **#282 closed** (5 run: 4 red; 282-P2 green and recorded green, since only the stand-in can see it, like F7). Results are posted on each.
- **Required checks: `main` now equals `develop`**, 15 each, `strict: true`, read back and identical (Shyden: "do not have any gaps"). Posted on #308.
- **#308 AC 2 decided by Shyden: a daily check.** A scheduled job compares the two lists and opens an issue for ShydenMcM if they differ, with a planted mismatch. It needs a read-only branch-protection key in its own `main`-only environment (prod-cron pattern). **Shyden creates the key**; re-scored 1 → 2 on the board.

## Resume steps
1. Run `ListAgents`. No subagents were started.
2. Merge this handover PR when green (docs fast path).
3. Next on the queue: **#287** (3, Node 26; worked example yawelo-idle #501 / PR #507). Then the list below.
4. When Shyden has made #308's key: build the daily workflow (environment allowing `main` only, `--ref main` dispatch, a pin test, a planted mismatch that opens an issue).

## Waiting on Shyden / to do
- **#308's read-only key** (branch-protection read).
- Ticket-filing procedure (global, 2026-10-16, `reference-identity-and-agile.md` lines 41-42): steadyhand has no `.github/ISSUE_TEMPLATE`. File a story (search first) to bring the form and the open board up to yawelo-idle's `story.yml` and repo-template#20.

## Next on the clean-up queue (all before #222)
- **#287** (3, Node 26), **#272** (5, Python floors, including #323's five), **#308** (2, waits on the key), **#315** (2, board Priority, blocked by repo-template#6), **#317** (5, orphan check in the PR gate), **#320** (2, README for the extension direction), **#337** (3, blocker links), **#336** (5, logs suite, before #245), **#341** (2, login name out of the paper audit). #339 (extension log) and #345 (paper audit trail) are post-release.

## Raised with Shyden
- Three global hook false positives, for a dedicated `~/.claude` session (his choice, 2026-10-12): `~/.claude/hook-false-positives-2026-10-13.md`.

## Progress (2026-10-16, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` tickets left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points). Board open: 34 tickets, 192 points across 33 scored (epic #214 unscored). Closed 2026-10-09 to 2026-10-16: 10 tickets, 53 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-08, low confidence:** 33 open scored tickets at 1.43 a day is about 23 days.
- **By effort: 192 points remaining across 33 scored open tickets. ETA 2026-11-11, low confidence:** 7.6 points a day is about 25 days.
- **Assumed:** last week's pace (test and CI work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315, Shyden's key for #308.
