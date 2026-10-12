# Handover: steadyhand

**Updated:** 2026-10-12 07:50 WIB (00:50 UTC). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop` = `bf95a10` (#284 hypothesis bump), green, `deploy-dev` success (run 38188822013). Default branch. Merge green PRs into `develop` without asking; never `main`.
- **`282-unit-tests-under-1s`**, pushed, no PR yet, head `bb5e507` (read with `git rev-parse origin/282-unit-tests-under-1s`), behind develop by two commits (merge develop in before the next push). Three cuts, each green and mutation-verified (`.superpowers/sdd/282/evidence.md`).

## Clean-up queue (Shyden: "Cleanup first, every project"), all before #222
Order: #285 → #286 → #290 → #292 → #282's limit last. #282's cuts go on in parallel. #287 and #288 at any point.
- **#282** In Progress, 13: **amended 2026-10-12 for the global 0.1 s CPU rule** (check AT 0.1 s; every test whose heaviest run, laptop or CI, passes 0.07 s is cut to 0.07 s). Keeps: a warm-cache cut for about 42 CLI tests, nine individual cuts (`test_yahoo` restorations, `test_cache`, `test_ledger_booking`, `test_journeys`), the 1 s limit, the CPU check, the raise-guard.
- **#292** (8, new): 52 long real runs (34 CLI, 18 golden) move to `integration`, each with a short-window unit stand-in; moved tests stay on the cold cache (AC 7). Ids in `.superpowers/sdd/unit-1s/moves.txt`.
- **#285** (8) guards suite + load limit; **#286** (5) no process/socket, creates `integration`; **#290** (5) properties suite at 500; **#287** (3) Node 26; **#288** (3) mutations in CI; **#272** (5) Python floors.

## Measured this session (`.superpowers/sdd/unit-1s/`, git-ignored)
- Probe on `bb5e507` (`probe-py-bb5e507.jsonl`, 2,379 of 2,379): 139 tests over 0.07 s on the laptop; #282's bucket 96 (about 103 with CI's heavier runs, `cut-list-007.txt`); the rest are property (#290), guard (#285), process (#286).
- Spike (reverted): every CLI test on one shared, filled cache (`spike-cache/cache.sqlite`, 140 KB, 1,240 bars, 135 fetched ranges): all 139 pass; median over-line test falls to 21% of its CPU (`probe-spike-warm.jsonl`). Seeding a test: file copy 0.20 ms CPU, sqlite backup 0.55 ms, dump replay 10.7 ms.
- Profiles (`prof-*.prof`, `profsum.py`): CLI paper tests spend about 78% in the cold cache fill (`cache.fetch` → `_ask_every_gap` → `_fill` → `yahoo._fetch`); golden 47% `engine.run_day`, 33% fill.

## Resume steps
1. Run `ListAgents`; no subagents were started this session.
2. **Clean-up pass 1 needs Shyden's run:** the auto-mode classifier refused local deletions. He chose to run `zsh <scratchpad>/cleanup-pass1.zsh` himself (removes 21 closed-ticket worktrees, 49 local branches whose tip IS a merged PR head, 15.2 GB of `.venv`/`node_modules`/caches in `.superpowers/sdd`). The scratchpad is session-local: if it is gone, rebuild from the steps in memory `feedback-branch-tip-equals-merged-head`. Then pass 2 (should find nothing new), add a pass-log entry to `~/.claude/global-rules/reference/reference-cleanup.md`, run `~/.claude/scripts/cleanup-done.sh steadyhand`. Kept on purpose: `ext/s1-ci-fast-path` (7 WIP commits past PR #260's head), `203/spec-amendment-wip`, `ext/s1-ci-fast-path-fold`, `scratch/221-chain`, `scratch/221-guards`, `ext/s3b-guards` (#222 WIP); list them for Shyden. Pass 1 done: six duplicated memories removed, remote branches already clean, no done-but-open issues; section C is the weekly cloud routine's (last run 2026-10-11, no PR).
3. **#282 warm cache, plan by extraction:** recorder writes a seed cache (full recorded range per golden stock) as a committed fixture; `recorded_source(folder, *, seeded=True)` copies it in when absent; cold-path tests pass `seeded=False`; an `integration` test rebuilds the seed and compares table contents. Check that full-range seeding serves every narrower request (`test_a_restored_day_is_the_same_whatever_range_is_asked`). Predicted mutations before and after each cut (AC 7).
4. Then #285, #286, #290, #292, and last #282's limit, CPU check and guard (ONE push); add the CPU constant to `CPU_LIMITS` in `~/.claude/hooks/unit-limit-never-raised.py`.

## Progress (2026-10-12 00:47 UTC, `.superpowers/sdd/estimates/progress.py`)
- **Measured:** EXT first release 4 of 28 stories, 21 of 184 points. Whole board open: 33 tickets, 213 points (epic #214 unscored). Closed in the last 7 days: 8 tickets, 30 points.
- **By tickets: 14% (4 of 28). ETA 2026-11-09, low confidence:** 32 open tickets at 1.14 a day is 28 days.
- **By effort: 11% (21 of 184). ETA 2026-12-01, low confidence:** 213 open points at 4.3 a day is 50 days.
- **Assumed:** the last 7 days' pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review.

## Standing notes
- Tool fix: `~/.claude/scripts/pr-verdict.sh` reading the router's stderr notice as a required check (backup `.bak-router-noise-2026-10-12`).
- claude-mem cannot save memories (provider allowance exhausted since 2026-10-10 22:21 UTC).
