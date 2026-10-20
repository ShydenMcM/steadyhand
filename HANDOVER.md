# Handover: steadyhand

**Updated:** 2026-10-20 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (`17b3312` when written). Merge green PRs into `develop` without asking; never `main`.
- **`272/python-floors`** (#272, In Progress): worktree `../steadyhand-272`, pushed, head `4e6e01e` when written (read `git rev-parse origin/272/python-floors`). 6 commits, no PR yet. Local gate green (ruff, format, mypy, 2,570 unit).
- `docs-handover-2026-10-20f`: this file, worktree `../steadyhand-handover`.
- Local branches kept by choice: `203/spec-amendment-wip`, `ext/s3b-guards` (#222 WIP).

## #272 state (design: `.superpowers/sdd/272/design.md`; every Shyden ruling is there and on the ticket)
Done on the branch: `tests/guards/floors.py` (Python `floor_breach`, one floors file `extension/tests/floors.json`), the recorder runs every Python suite but live (`RECORDED_SUITES`, `record-floors.yml` installs uv), and the reader `tests/guards/literal_floors.py` (114 plants in `tests/guard_helpers/test_literal_floors.py`).
Shyden's rulings (all 2026-10-20): every typed-in lower bound is a floor, no exemption; untraceable names refused; everything in our code followed (pytest pythonpath + `packages/*/src`), outside libraries pass; an index or slice number is no value; both sides of `<` judged; text numbers, `if ...: pytest.fail`, unittest bounds, ranges, max/min equalities, class constants, object attributes, call-of-a-call all read; the live fixture count moves to a non-live test.
Measured (`uv run --locked python -I .superpowers/sdd/272/measure3.py ../steadyhand-272`, run from the main checkout): 174 files, 3,106 asserts, **143 to fix: 37 floor constants, 52 count floors, 38 range checks, 16 untraceable**.

## Resume steps
1. Run `ListAgents`. No subagents were started.
2. Merge this handover PR when green (docs fast path), then `git worktree remove ../steadyhand-handover`.
3. #272 next, in order: (a) the whole-tree guard `tests/guards/test_literal_floors.py` (guards suite: no local run, CI's) with controls (a)-(e): `searched` over files and checks, floors `python.literal-floors.*`, `assert_tokens` per-file cross-check, fail-closed parse, the plants; a burn-down is an exemption, so it lands after the fixes; (b) the 143 fixes: count floors and constants become `assert floor_breach("python.<file>.<population>", len(x)) is None` after the verdict; range checks and untraceable bounds are rewritten so no typed-in number bounds them (never re-spelled just to dodge the reader); (c) open the PR, label `record-floors`, `npm run floors:fetch <run id>`, fold `floors.json` into the commits; (d) `mutations/272.toml`, two per converted floor; (e) close-out.
4. Before ANY decision question to Shyden: a limits audit of the code as written (memory `feedback-ask-before-editing-a-ticket-s-rule`).

## Waiting on Shyden
- **#308's read-only key** (branch-protection read).

## Next on the clean-up queue (all before #222)
- **#348** (5, P1, waits on repo-template#27), **#308** (2, waits on the key), **#315** (2, blocked by repo-template#6), **#317** (5), **#320** (2), **#337** (3), **#336** (5, before #245), **#341** (2), **#359** (3), **#362** (2, TS literal-floor reader blind to arithmetic/calls/casts, filed today).

## Lessons this session
- A narrowing written onto a ticket before asking is going behind Shyden's back; so is a known limit left out of a question. Ask with measured costs first; edit tickets only with his approved words (byte copy first; `--jq .body` adds one newline).
- `pytest --suite guards` slipped past `local-suites-unit-only.py` (logged in `~/.claude/hook-false-positives-2026-10-13.md` item 4); guards are CI's.
- A plant whose floor is found first can hide a crash path behind it: plant the non-floor shape of every branch too.

## Progress (2026-10-20, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` tickets left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points), none in the last 7 days. Board open: 36 tickets, 202 points across 35 scored (epic #214 unscored). Closed 2026-10-13 to 2026-10-20: 8 tickets, 35 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-20, low confidence:** 35 open scored tickets at 1.14 a day is about 31 days.
- **By effort: 202 points remaining across 35 scored open tickets. ETA 2026-11-29, low confidence:** 5.0 points a day is about 40 days.
- **Assumed:** this week's pace (clean-up, CI and test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315, repo-template#27 for #348, Shyden's key for #308.
