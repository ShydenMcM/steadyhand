# Handover: steadyhand

**Updated:** 2026-10-13 03:51 WIB (2026-10-12 20:51 UTC). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: `f3311e7` (#290, PR #312): run 38306290685 green on every job, deploy-dev verified the zip's attestation. Read its head with `git rev-parse origin/develop`. Required checks: **14**, now incl. `properties (py3.12)` and `properties (py3.13)` (read back 2026-10-12 20:45 UTC). Merge green PRs into `develop` without asking; never `main`.
- `282-unit-tests-under-1s`: pushed, no PR, head `5edf543`; it has not taken in develop.

## #290 closed (Done): what it left in place
- Every Hypothesis property lives in `tests/properties` (`test_<folder>_<stem>.py`) and calls the unit test of its own name in `tests/<folder>/test_<stem>.py`, its stand-in, parametrized over chosen cases. `tests/engine`, `tests/idx` and `tests/properties` are on pytest's `pythonpath`.
- `pytest --suite properties` loads `tests/properties/hypothesis_profile.py`: 500 examples, no deadline, `derandomize=False` (GitHub Actions would otherwise fix the seed). Any other run refuses a Hypothesis test by name (`suites.refuse_properties`). `HYPOTHESIS_PROFILE` is gone.
- A new property: write the stand-in in unit first (cases under 0.07 s of CPU), then its driver; `tests/guards/test_property_homes.py` refuses one without the other. A red property on CI is a real defect: file, reproduce from the blob, fix, keep the shrunk case as a stand-in case.
- Evidence on #290; `.superpowers/sdd/290/` (mutations 30/30 in both homes, timings, coverage).

## Resume steps
1. Run `ListAgents`; no subagents were started.
2. Next is **#292** (8): read it, move it to In Progress (`python3 .superpowers/sdd/286/status.py 292 "In Progress"`), branch from `origin/develop`. It empties the Python load burn-down list (`tests/idx/test_yahoo.py`). Then #282's 1 s limit last (re-measure `test_journeys`, now in-process).
3. #308: Shyden runs the copy command (main = develop's 14 checks; list in the comment of 2026-10-12 20:45 UTC). When he has: read both lists back (`gh api repos/ShydenMcM/steadyhand/branches/<b>/protection/required_status_checks`), quote them on #308, close.
4. A guards or floors change records via the `record-floors` PR label, then `cd extension && npm run floors:fetch <run id>`, and commit. The laptop runs unit only.

## Clean-up queue (Shyden: "Cleanup first, every project"), all before #222
- **#292** (8), **#282** In Progress (13, last), **#287** (3, Node 26), **#288** (3, mutations in CI), **#272** (5, Python floors).

## Raised with Shyden
- Three global hook false positives, for a dedicated `~/.claude` session (his choice, 2026-10-12): `~/.claude/hook-false-positives-2026-10-13.md`.

## Progress (2026-10-12 20:50 UTC, `uv run --locked python .superpowers/sdd/estimates/progress.py`)
- **Measured:** EXT first release 4 of 28 stories closed. Whole board open: 31 tickets, 196 points (epic #214 unscored, 30 scored). Closed since 2026-10-06: 9 tickets, 42 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-06, low confidence:** 30 open scored tickets at 1.29 a day is 24 days.
- **By effort: 196 points remaining. ETA 2026-11-15, low confidence:** 196 points at 6.0 a day is 33 days.
- **Assumed:** the last week's pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review.
