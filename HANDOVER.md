# Handover: steadyhand

**Updated:** 2026-10-20 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop`. Merge green PRs into `develop` without asking; never `main`.
- **`272/python-floors`** (#272, In Progress, Estimate 13): worktree `../steadyhand-272`, pushed, head `9df9eff` when written (read `git rev-parse origin/272/python-floors`). 9 commits, no PR yet. Local gate green (ruff, format, mypy, 2,594 unit on 3.12 and 3.13, 100% coverage).
- `docs-handover-2026-10-20g`: this file, worktree `../steadyhand-handover`.
- Local branches kept by choice: `203/spec-amendment-wip`, `ext/s3b-guards` (#222 WIP).

## #272 state (design: `.superpowers/sdd/272/design.md`; every Shyden ruling is there and on the ticket)
Done on the branch: `tests/guards/floors.py` (Python `floor_breach`, one floors file `extension/tests/floors.json`); the recorder runs every Python suite but live; the reader `tests/guards/literal_floors.py` (138 plants in `tests/guard_helpers/test_literal_floors.py`); and `tests/guards/literal_floor_types.py`, mypy's types for the reader (its tests `tests/guards/test_literal_floor_types.py` run real mypy, so guards suite, CI's).
Shyden's rulings (all 2026-10-20): every typed-in lower bound is a floor, no exemption; untraceable names refused (the attribute exemption I had added unasked is removed); everything in our code followed, outside libraries pass; an index or slice number is no value; both sides of `<` judged; text numbers, `if ...: pytest.fail`, unittest bounds, ranges, max/min equalities, class constants, object attributes, call-of-a-call, stored functions all read; **attributes and methods matched by the object's declared type (mypy), never by name: a library object passes, ours is judged from its own class (ancestors and descendants; any class for a protocol), a type not worked out is refused** (#272 rescored 8 to 13); the live fixture count moves to a non-live test.
Measured (`uv run --locked python -I ../steadyhand/.superpowers/sdd/272/typediff.py .`, run from `../steadyhand-272`): 174 files, 3,106 asserts, mypy types 6.6 s CPU, every class named; **143 to fix: 37 floor constants, 52 count floors, 38 range checks, 16 untraceable** (unchanged by matching by type). Mutations M1-M7 of the typed matching all killed.

## Resume steps
1. Run `ListAgents`. No subagents were started.
2. Merge this handover PR when green (docs fast path), then `git worktree remove ../steadyhand-handover`.
3. #272 next, in order: (a) the whole-tree guard `tests/guards/test_literal_floors.py` (guards suite: no local run, CI's) built on `Project.of_files(roots, MypyTypes(ROOT), ROOT)`, with controls (a)-(e): `searched` over files and checks, floors `python.literal-floors.*`, `assert_tokens` per-file cross-check, fail-closed parse, the plants, plus every class named by mypy; a burn-down is an exemption, so it lands after the fixes; (b) the 143 fixes: count floors and constants become `assert floor_breach("python.<file>.<population>", len(x)) is None` after the verdict; range checks and untraceable bounds are rewritten so no typed-in number bounds them (never re-spelled just to dodge the reader); (c) open the PR, label `record-floors`, `npm run floors:fetch <run id>`, fold `floors.json` into the commits; (d) `mutations/272.toml`, two per converted floor; (e) close-out.
4. Before ANY decision question to Shyden: a limits audit of the code as written (memory `feedback-ask-before-editing-a-ticket-s-rule`).

## Waiting on Shyden
- **#308's read-only key** (branch-protection read).

## Next on the clean-up queue (all before #222)
- **#348** (5, P1, waits on repo-template#27), **#308** (2, waits on the key), **#315** (2, blocked by repo-template#6), **#317** (5), **#320** (2), **#337** (3), **#336** (5, before #245), **#341** (2), **#359** (3), **#362** (2, TS literal-floor reader blind to arithmetic/calls/casts).

## Lessons this session
- Every `return <pass>` in a reader is a policy decision: audit each against the rulings before asking anything. A pass no ruling grants is an exemption (the attribute one was mine).
- Name matching meets outside libraries (`.parent`, `.values()`, `.split()`); mypy is compiled, so use its `NameAndMemberCollector` and match by exact source place (13,829 of 13,829 matched), with `preserve_asts` on or bodies are freed.
- An attribute on a non-name root (`Box().least`) was never read: plant every root shape.

## Progress (2026-10-20, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` tickets left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points), none in the last 7 days. Board open: 36 tickets, 207 points across 35 scored (epic #214 unscored). Closed 2026-10-13 to 2026-10-20: 8 tickets, 35 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-20, low confidence:** 35 open scored tickets at 1.14 a day is about 31 days.
- **By effort: 207 points remaining across 35 scored open tickets. ETA 2026-11-30, low confidence:** 5.0 points a day is about 41 days.
- **Assumed:** this week's pace (clean-up, CI and test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315, repo-template#27 for #348, Shyden's key for #308.
