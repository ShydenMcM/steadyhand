# Handover: steadyhand

**Updated:** 2026-10-21 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop`. Merge green PRs into `develop` without asking; never `main`.
- **`272/python-floors`** (#272, In Progress, 13): worktree `../steadyhand-272`, pushed, head `1c9db9d` when written (read `git rev-parse origin/272/python-floors`). No PR. Its pushed commits lack their floors, so under the 2026-10-21 rule the green chain goes to a NEW branch name with a normal push and this one is listed for deletion (never force-push).
- **Uncommitted there, on purpose:** `tests/guards/test_no_literal_floor.py`, the whole-tree guard (lands last, once every finding is fixed); copy in `.superpowers/sdd/272/test_no_literal_floor-20261020a.py`.
- `docs-handover-2026-10-21`: this file, worktree `../steadyhand-handover`.
- Local branches kept by choice: `203/spec-amendment-wip`, `ext/s3b-guards` (#222 WIP).

## #272 state (design and every ruling: `.superpowers/sdd/272/design.md`; rulings also on the ticket, read back equal)
Committed this session: `55d4604` (the reader counts the asserts it judged; mutant red in 133 of 133 files), `f42fbe0` (14 guard files' floors become `floor_breach`, ids `python.<stem without test_>.<population>`), `1c9db9d` (a count is measured: 9 mutants killed as predicted, `mutate12.py`). Local gate green at `1c9db9d`: 2,604 unit tests, 100%, both Pythons.
Guard measured (`guardmeasure.py`): 177 files, 3,136 checks, 302 classes all named; mypy 6.5 s, reads 1.6 s CPU; the guards step has 60 s, using about 10 s.
Rulings 2026-10-21: "Exact values" for 42 money/date/price checks, **split to #365** (5); "Read both" (judge asserts in scripts/ and packages/; follow a check into a helper of ours whose returned comparison it asserts); "A count is measured" (built); perf, after four rounds, **"Reader follows by position"**: the 5 budgets stay (the specs require them); split a returned tuple by position on unpacking, read a fixture parameter as its fixture's return, read an attribute from the constructor argument that set it.
76 findings left at `f42fbe0` = 42 (#365) + 23 counts + 4 perf + 7 order checks (`split.py` holds the sets).

## Resume steps
1. Run `ListAgents`. No subagents were started.
2. Merge this handover PR when green (docs fast path), then `git worktree remove ../steadyhand-handover`.
3. **#367 first** (3, blocks #272): the recorder runs on a scratch ref `refs/floors/<branch>`, not a PR label (new global rule; the `.yml` already holds no write token).
4. #272 in `../steadyhand-272`, test first, plants then mutations, each step measured:
   a. Reader by position (tuple split, fixture parameters, constructor attributes); re-run `perfvariants.py`: the 4 perf findings must clear with the tests unchanged.
   b. "Read both": the guard's population adds scripts/ and packages/; helper-returned comparisons judged.
   c. The 23 counts become `floor_breach`. `test_fast_path_reads` first: OPENED was 236 on py3.12 and 235 on py3.13 (one equality floor cannot hold both); find why before converting. `test_yahoo_live`'s count moves to a non-live test (ruled 2026-10-20).
   d. The 7 order checks: declare the YAML data's types so mypy knows them (not a re-spelling).
   e. After #365 merges: guard commit, a new branch name, record floors on the scratch ref, fold into the unpushed commits, then `mutations/272.toml` with two per converted floor, then close-out.
5. Before ANY decision question: a limits audit, and read which side `_compare_bounds` judged before describing why a finding fired (memory `feedback-measure-the-mechanism-before-asking`, fourth instance).

## Waiting on Shyden
- **#308's read-only key** (branch-protection read).

## Next on the clean-up queue (all before #222)
- **#367** (3, blocks #272), **#365** (5, blocks #272), **#366** (2, findings name the number they reached), **#348** (5, P1, waits on repo-template#27), **#308** (2, waits on the key), **#315** (2, the board has no Priority field; blocked by repo-template#6), **#317** (5), **#320** (2), **#337** (3), **#336** (5, before #245), **#341** (2), **#359** (3), **#362** (2).

## Lessons this session
- Read which side a reader judges before describing a finding's cause: two perf questions rested on a wrong cause and missed specs, and took four rounds.
- A guard's own file is in its population: its line `checks >= asserts` was a floor through `sum(1 for ...)`. That led to the counting ruling.
- Duplicate test basenames break mypy and pytest here (`test_literal_floors.py` twice), hence `test_no_literal_floor.py`.

## Progress (2026-10-21, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` tickets left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points), none in the last 7 days. Board open: 39 tickets, 217 points across 38 scored (epic #214 unscored). Closed 2026-10-14 to 2026-10-21: 7 tickets, 34 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-28, low confidence:** 38 open scored tickets at 1.0 a day is about 38 days.
- **By effort: 217 points remaining across 38 scored open tickets. ETA 2026-12-05, low confidence:** 4.9 points a day is about 45 days.
- **Assumed:** this week's pace (clean-up, CI and test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315, repo-template#27 for #348, Shyden's key for #308.
