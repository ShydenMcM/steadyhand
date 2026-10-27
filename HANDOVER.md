# Handover: steadyhand

**Updated:** 2026-10-26 (UTC), before Shyden's Mac restart. Current state only. Older history: `git show ff266fc:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue.

## Branches and heads
- `develop` = 92fe697 (#416, the previous handover). Develop CI run 40253346399 is green on it (12 jobs, 0 steps failed or skipped). Merge green PRs into develop without asking; never `main`.
- This handover is committed only on local branch `docs/handover-cleanup-2026-10-26`, not pushed yet.
- **#407 open, held** for five full limits rounds at one-minute load above 20 (`.superpowers/sdd/407/measure.zsh`).
- **Node:** the Mac now runs the official nodejs.org build 26.12.1 (ICU 78.3, the same as CI); Homebrew's node is uninstalled (shyden.co.uk #953). A shell that was open before the switch needs `PATH=$HOME/.local/share/node/current/bin:$PATH`. A fresh shell after the restart has it already.

## Resume steps
1. `ListAgents`; `git rev-parse origin/develop`; `command -v node` should print `~/.local/share/node/current/bin/node`.
2. Push `docs/handover-cleanup-2026-10-26` as a one-commit docs PR into develop; merge it once green.
3. **Clean-up pass 1 (2026-10-26, sections B and D) is surveyed but not finished.** The `/loop` was never armed. Put the deletion list below to Shyden in ONE AskUserQuestion; delete what he approves (re-read each tip just before `-D`); run pass 2; then run `~/.claude/scripts/cleanup-done.sh steadyhand` and add a pass-log line to `~/.claude/global-rules/reference/reference-cleanup.md`. The survey and its outputs are in `.superpowers/sdd/cleanup-2026-10-26/`. Its scripts point at the old scratchpad, so set `S` before re-running them.
4. Next: **#365** (5 points, blocks #272), then the queue below. Run #407's rounds whenever `sysctl -n vm.loadavg` reads above 20.
5. A PR changing a workflow other than ci.yml runs that workflow on `coverage/<branch>` at the PR head before the PR push (`scripts/workflow_runs.py`). Run the text guards' readers over new test files before the first push. The laptop runs only unit, lint, format and types. Gate template: `.superpowers/sdd/382/gate.sh`.

## Clean-up: proposed deletions (each checked 2026-10-26)
- **12 local branches whose tip IS their PR's head:** 287/node-26, 349/dependabot-groups, 350/typescript-major, 367/scratch-ref-recorder (PR closed), 381/coverage-gate, docs-handover-2026-10-20c/d (closed), -20e, -20f, docs-handover-cleanup-2026-10-20, docs/handover-381-closed, docs/handover-381-merged. Plus `391/cut-thirty-days` (in develop, 0 commits of its own) and `docs-handover-2026-10-20b` (one local-only commit, a superseded handover).
- **6 remote branches:** 367/scratch-ref-recorder and docs-handover-2026-10-20b/c/d (each at its closed PR's head), coverage/374/helper-coverage and coverage/374/last-seven-files (scratch refs; #374 closed).
- **Worktree `../steadyhand-391`:** 2 modified files, byte-identical to `.superpowers/sdd/374/391-attempt-20261022.patch`; #391 is closed; nothing has it open.
- **12 scratch items in `.superpowers/sdd`, about 85 MB:** 287, 374, 374b, 381, 384, 391, 394, 403, 405, cleanup-tickets (all 5 drafts were filed as #282/#285-#288/#290), deps, dev-head.txt. Their tickets are closed and nothing cites them.
- **`~/Developer/Repos/steadyhand-collect1.txt`:** a 269 KB pytest collection list from 2026-10-24 that nothing cites.
- **Kept:** 203/spec-amendment-wip (Shyden's choice), 272/python-floors and its worktree (#272 open, plus 1 untracked file), ext/s3b-guards (#222 open), 2026-09-29-m5b-paper (a backup until 2026-10-29), 2026-09-28-m5b-paper (could not be proven), Dependabot #401. Caches (50, 2.0 GB) and 2,448 artifacts are left to GitHub's expiry. 0 draft releases.
- **Done already:** two memory links re-pointed to their `feedback-` names. Board census: 181 items, 0 Done-but-open, 0 closed-not-Done, 0 off the board, 0 In Progress, only epic #214 unscored.

## Waiting on Shyden
- #400 and #308: his settings clicks (`main` strict off then `release-cut`; `coverage` on `main`).
- #394's guard refuses four vi members beyond the ruling's three (told 2026-10-23).
- #272: constant-name `setattr` read like `x.name = value`. #308's read-only key.
- Whether the floors check should narrow to the files floor guards read.

## Running
Nothing. No local job was started this session.

## Next on the clean-up queue (all before #222)
#365 (5, blocks #272), #366 (2), #377 (2), #378 (3), #348 (5, waits on repo-template#27), #400 (3), #308 (2), #315 (2), #317 (5), #320 (2), #337 (3), #336 (5), #341 (2), #359 (3), #362 (2); #407 (2) when load allows.

## Progress (2026-10-26, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT 4 of 28 stories closed (21 of 184 points). Board open: 42 tickets, 224 points across 41 scored (epic #214 unscored). Closed 2026-10-19 to 2026-10-26: 13 tickets, 70 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-17, low confidence:** 41 open scored tickets at 1.86 a day is about 22 days.
- **By effort: 224 points remaining across 41 scored open tickets. ETA 2026-11-17, low confidence:** 10 points a day is about 22 days.
- **Assumed:** last week's pace holds. **Outside waits:** broker account (#242), Web Store review, repo-template#6 (#315), the key (#308), #272's ruling, #400's and #308's settings clicks, machine load above 20 for #407.

## Notes
- Wi-Fi is unstable (Shyden, 2026-10-26): name the network as a possible cause of a failed fetch or push; still no retries.
