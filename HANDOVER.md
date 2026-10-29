# Handover: steadyhand

**Updated:** 2026-10-29 (UTC), overnight while Shyden sleeps (back about 06:00 WIB). Current state only. Older history: `git show d66cdce:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop` = d18bf00, green (push run 40784775572, all 13 jobs). Merge green PRs into develop without asking; never `main`.
- **Closed 2026-10-29:** #341, #337, #320, #362, #432 (PR #435 → d18bf00; 8 of 8 mutations as predicted; evidence comment per AC).
- This handover: docs PR on `docs/handover-2026-10-29e` (also the README's Cloudflare note). PR #436 (the previous handover) is closed unmerged, replaced by this one.
- **Commits and merges:** every code commit carries `Gaps checked:`. Every squash merge, docs too, needs `--body-file` with a section and `--match-head-commit` with the SHA from a file. Run `git commit -F <file>` alone on its line; push before `gh pr create`, in separate calls.
- `core.hooksPath .githooks`: pre-push refuses anything uncommitted or untracked. Never `--no-verify`.
- `../steadyhand-272` (#272): develop's `.githooks/pre-push` staged beside an uncommitted `tests/guards/test_no_literal_floor.py`; next step is merging develop (the message needs a section).
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (74a0a30, until 2026-11-27); `365/exact-values-backup-2026-10-27` (until 2026-11-26) and `-10-28` (until 2026-11-27); `.superpowers/sdd/365/mutations_head.py`, `pr_body_head.py`, `.superpowers/sdd/378/gaps_checked-current-2026-10-28.py` (until 2026-11-27).
- **#407 open, held** for five limits rounds at load above 20 (`.superpowers/sdd/407/measure.zsh`).

## Rulings 2026-10-29 (all recorded on their tickets)
- **#336:** "Split each test": trail assertions move to `logs` on the full input; behaviour assertions stay in unit as written; moved trail checks keep a unit stand-in. AC 2 and AC 3 reworded on the ticket.
- **#317:** a classic token with only `read:project` (fine-grained tokens cannot read a user-owned board: GitHub docs), also stored as a Dependabot secret of the same name (Dependabot runs get no Actions secrets). Still to measure: an environment branch rule that admits `refs/pull/<n>/merge`; then post Shyden's click list on #317.
- **#359:** every project may READ repo-template (never write). Form read at `75e741b` (`.superpowers/sdd/359/`). **Parked**, two questions on the ticket: the template has `blank_issues_enabled: true` (AC 1 says off), and the form names `docs/project-board.md` and `scripts/file-story.ts`, which this repo lacks.
- **Cloudflare environments rule:** N/A, no hosted surface (0 files mention Cloudflare); no story. README notes it.

## Resume steps
1. `ListAgents`; `git status --short` clean; `git fetch`.
2. This docs PR: wait its ci, merge with `--body-file` (a section) and `--match-head-commit`.
3. **#336 (P2, 5):** follow `.superpowers/sdd/336/notes.md`: re-run `candidates.py` on develop d18bf00, finish AC 1's per-test classification (test_paper_run, test_paper_commands, journeys, integration, perf; the 3 helper-hidden trail checks), then write the plan with the split ruling, review it to zero in a scratch worktree, branch `336/logs-suite`.
4. **#317 (5):** measure the PR-ref environment rule, post the click list; the reader, its fail-closed paths and the unit mocks can be built before the token exists.
5. When Shyden is back: ask #359's two questions.

## Waiting on Shyden
- **#359:** the two questions above.
- **#317:** creating the classic token and its two secrets, once the click list is posted.
- Told 2026-10-29: the gap hook's ".md-only PR needs no section" exemption never fires while develop is ahead of main.
- Told 2026-10-28, not ruled: `git-hooks-present.py` gaps (`git pull`, a non-executable hook, `-c core.hooksPath`).
- #400 and #308: his settings clicks. #394's four vi members. #272's `setattr` ruling and #308's key. Whether the floors check narrows to the files floor guards read.

## Running
Nothing local. No agent.

## Queue
#348 P1 (repo-template#27), #336 P2 (5, unblocked), #317 (5, building), #359 (3, parked); #400 (3) and #308 (2) his clicks, #315 (2, repo-template#6); #272 (13, ruling); #366 (2) after #272; #407 (2) at load above 20.

## Progress (2026-10-29, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 35 tickets, 205 points across 34 scored (epic #214 unscored). Closed 2026-10-22 to 2026-10-29: 15 tickets, 64 points.
- **By tickets: 14% complete (4 of 28 EXT stories). ETA 2026-11-14, low confidence:** 34 open scored tickets at 2.1 a day is about 16 days.
- **By effort: 205 points remaining across 34 scored open tickets. ETA 2026-11-21, low confidence:** 9.1 points a day is about 22 days.
- **Assumed:** last week's pace holds; it will not while much of the queue waits on him. **Outside waits:** broker account (#242), Web Store review, repo-template#6 and #27, #317's token, #359's questions, #272's ruling, #400's and #308's clicks, load for #407.

## Notes
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
- Extension floors move only through `record-floors.yml` on a scratch ref before a branch's first push; map every new guard branch to a plant first.
- The floors hook wants `Floors: none moved` or `Floors: recorded in run <id>`.
