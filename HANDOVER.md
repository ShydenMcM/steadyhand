# Handover: steadyhand

**Updated:** 2026-10-13 01:09 WIB (2026-10-12 18:09 UTC). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: `2e310bc` (#286, PR #310): run 38288047404 green on every job, deploy-dev verified the zip's attestation. Read its head with `git rev-parse origin/develop`. Required checks: 12, incl. `integration (py3.12)`, `integration (py3.13)`, `extension-integration` (read back). Merge green PRs into `develop` without asking; never `main`.
- `282-unit-tests-under-1s`: pushed, no PR, head `5edf543`; it has not taken in develop.

## #286 closed (Done): what it left in place
- Unit refuses every process and outside connection: `tests/plugins/no_process.py` (installed by `tests/conftest.py`, unit only; `perf`/`live` run unarmed), `extension/tests/lib/no-process.ts` + first setup file `tests/no-process.ts`. Real-process cases live in `tests/integration` (`pytest --suite integration`) and `extension/tests/integration` (`npm run test:integration`). The CI scripts' unit tests stand git in with the `fake_git` fixture (`tests/scripts/stood_in_git.py`).
- The extension's LOAD_BURN_DOWN list is gone (emptied). The Python one keeps `tests/idx/test_yahoo.py` until #292.
- Evidence on #286; `.superpowers/sdd/286/` (mutations 20/20, outermost probes).

## Resume steps
1. Run `ListAgents`; no subagents were started.
2. Next is **#290** (5). Read it, move it to In Progress (`python3 .superpowers/sdd/286/status.py 290 "In Progress"`), branch from `origin/develop`. Then #292 (empties the Python burn-down list), then #282's 1 s limit last (re-measure `test_journeys`, now in-process).
3. #308: Shyden approved main = develop's checks and runs the copy command himself (given 2026-10-12 17:05 UTC); AC2 decided "release checklist step". When he has run it: read both lists back (`gh api repos/ShydenMcM/steadyhand/branches/<b>/protection/required_status_checks`, no `-R`), quote them on #308 with the decision, close.
4. A guards or floors change records via the `record-floors` PR label, then `cd extension && npm run floors:fetch <run id>`, and commit. The laptop runs unit only.

## Clean-up queue (Shyden: "Cleanup first, every project"), all before #222
- **#282** In Progress, 13: merge develop in, measure `test_cli_seed[BBRI]` and `test_journeys`, then the 1 s limit in one push after #290 and #292.
- **#292** (8), **#290** (5), **#287** (3, Node 26), **#288** (3, mutations in CI), **#272** (5, Python floors).

## Raised with Shyden
- Three global hook false positives, for a dedicated `~/.claude` session (his choice, 2026-10-12): `~/.claude/hook-false-positives-2026-10-13.md`.

## Progress (2026-10-12 18:08 UTC, `uv run --locked python .superpowers/sdd/estimates/progress.py`)
- **Measured:** EXT first release 4 of 28 stories closed. Whole board open: 32 tickets, 201 points (epic #214 unscored, 31 scored). Closed since 2026-10-06: 8 tickets, 37 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-09, low confidence:** 31 open scored tickets at 1.14 a day is 27 days.
- **By effort: 201 points remaining. ETA 2026-11-20, low confidence:** 201 points at 5.3 a day is 38 days.
- **Assumed:** the last week's pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review.
