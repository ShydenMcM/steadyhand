# Handover: steadyhand

**Updated:** 2026-10-12 23:23 WIB (16:23 UTC). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: `d198f40` (#285, PR #307): run 38276026983 green on every job, deploy-dev verified the zip's attestation. Read its head with `git rev-parse origin/develop`. Required checks now include `guards (py3.12)`, `guards (py3.13)`, `extension-guards` (read back). Merge green PRs into `develop` without asking; never `main`.
- `282-unit-tests-under-1s`: pushed, no PR, head `5edf543`; it has not taken in develop.

## #285 closed (Done): what it left in place
- Guards suite. Python: `tests/meta` became `tests/guards` (17 files), run by `pytest --suite guards` (`tests/plugins/suites.py`). Extension: `extension/tests/guards` (4), run by `npm run test:guards` (`--mode guards` picks the guards coverage list). New CI jobs: `guards (py3.12)`, `guards (py3.13)`, `extension-guards`.
- Load limit, 100_000 us of CPU per unit file, in both runners: `tests/plugins/load_clock.py`, `extension/tests/load-clock.ts` and `load-report.ts`. Burn-down lists, shrink-only (Shyden 2026-10-12): `tests/idx/test_yahoo.py` (#292 empties it) and `tests/tool-configs.test.ts` (#286 empties it).
- Floors: the `record-floors` label on a PR runs `.github/workflows/record-floors.yml`; then `npm run floors:fetch <run id>` on the laptop, and commit. Record mode is refused unless `GITHUB_WORKFLOW=record-floors`.
- Rulings (all on #285): "CI lock covers unit"; "Burn-down list" (test_yahoo); "Burn-down until #286" (the tool-config checks are not guards; a side agent's catch).
- The global hook `~/.claude/hooks/unit-limit-never-raised.py` now judges CPU_LIMITS in `.py` files too (it never had: a blind form, catalogued). The 67 cases pass; U18, U19 and U20 behave as predicted.
- 15 local mutations: all RED as predicted (`.superpowers/sdd/285/mutations.txt`).

## Resume steps
1. Run `ListAgents`; no subagents were started.
2. Next is **#286** (5): the integration suite. It empties the extension's burn-down list (`tests/tool-configs.test.ts`) and moves #286's table (tests/scripts git, test_journeys, test_paper_run, build.test). Read `~/.claude/global-rules/reference-guard-forms-and-floors.md` first; move it to In Progress; branch from `origin/develop`.
3. Then #290, #292 (empties the Python burn-down list, `test_yahoo.py`), then #282's 1 s limit last; its per-test limits go in the coverage-off limits steps #285 added.
4. #308 (1): `main`'s required checks lack `extension` and the guards jobs. It is Shyden's to approve.
5. A guards or floors change records via the `record-floors` PR label, then `cd extension && npm run floors:fetch <run id>`, and commit. The laptop runs unit only.

## Clean-up queue (Shyden: "Cleanup first, every project"), all before #222
- **#282** In Progress, 13: merge develop in, measure `test_cli_seed[BBRI]`, `test_journeys` with #286, then the 1 s limit in one push after #285, #286, #290 and #292.
- **#292** (8), **#286** (5), **#290** (5), **#287** (3, Node 26), **#288** (3, mutations in CI), **#272** (5, Python floors).

## Raised with Shyden, not filed (outside this repo or his call)
- `hooks/test-isolation.py` reads "pytest" anywhere in a command's text, even inside an edit script's heredoc or the script it names, as a test run. A Python edit that names it is refused while one of this session's runs holds the machine.
- `hooks/push-onto-running-ci.py` fails closed when pushing from a worktree under `.superpowers/`.
- `hooks/disguised-waits.py` read `tail -1; gh project item-edit ... --field-id` as `tail -f`.

## Progress (2026-10-12 16:23 UTC, `uv run --locked python .superpowers/sdd/estimates/progress.py`)
- **Measured:** EXT first release 4 of 28 stories closed. Whole board open: 33 tickets, 206 points (epic #214 unscored, 32 scored). Closed in the last 7 days: 11 tickets, 46 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-02, low confidence:** 32 open scored tickets at 1.57 a day is 21 days.
- **By effort: 206 points remaining. ETA 2026-11-13, low confidence:** 206 points at 6.6 a day is 32 days.
- **Assumed:** the last 7 days' pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review.
