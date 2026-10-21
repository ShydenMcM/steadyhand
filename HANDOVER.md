# Handover: steadyhand

**Updated:** 2026-10-21 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (74656ec when written). Merge green PRs into `develop` without asking; never `main`.
- **`272/python-floors`** (#272, In Progress, 13): worktree `../steadyhand-272`, head **e6426b2** (local, three commits past the pushed 1c9db9d: 596d098, 2d97f12, e6426b2, each at a green local gate; 2,672 unit tests, both Pythons). Never push this branch again: the green chain goes to a NEW branch name with a normal push, and this one is listed for deletion (no force-push).
- **Uncommitted there, on purpose:** `tests/guards/test_no_literal_floor.py` (lands last); copy in `.superpowers/sdd/272/test_no_literal_floor-20261020a.py`.
- **To delete when Shyden agrees:** local and remote `367/scratch-ref-recorder` (#369), and `272/python-floors` once its new branch lands.
- Kept by choice: `203/spec-amendment-wip`, `ext/s3b-guards` (#222 WIP).
- **Recording floors (#367):** steps in the header of `.github/workflows/record-floors.yml` (scratch ref, dispatch from develop, `npm run floors:fetch`, amend, normal push).

## #272 state (design and every ruling: `.superpowers/sdd/272/design.md`; rulings also on #272's body)
- Built this session, Shyden's rulings 2026-10-21: "Reader follows by position" (tuples split by position, fixture parameters read as the file's fixture, attributes from the constructor argument that set them); "A size is measured" (len() does not read what it counts; a written list or text, or a name bound to one in the file, is typed in); "Keep it" (a called stored lambda reads with the call's inputs; made unasked, raised by a side agent). Closed under approved rules: generators read by their yields, properties followed, containers filled by append and its kin.
- Tree (`posdiff.py`, mypy types): 76 findings at 1c9db9d, **70** at 2d97f12; all 4 perf findings cleared, tests unchanged. Left: 42 (#365) + 22 counts + 6 order checks (recount with `split.py`).
- **Reader coverage gap (this story's):** under unit, `tests/guards/literal_floors.py` is at 91%: 62 lines, 47 branches never run (`.superpowers/sdd/272/helper-cov.txt`; `misses.py` labels them). Coverage never measured it (`source_pkgs`); the wider gap is **#374** (filed today, 5).

## Resume steps
1. Run `ListAgents`. No subagents were started.
2. If this file's PR is open: merge it when green (docs fast path).
3. #272 in `../steadyhand-272`, test first, plants then mutations, each step measured:
   a. Close the reader's 62 lines and 47 branches with plants (starred construction, dataclass with bases, imported class, an argument standing for an object, `self.x` in a tuple target, dict and f-string sizes, ...), then `--cov=tests/guards` at 100% for `literal_floors.py` under unit (`of_files`/`module` run in the guards suite).
   b. "Read both": the population adds scripts/ and packages/; helper-returned comparisons judged.
   c. The counts become `floor_breach`. `test_fast_path_reads` first: OPENED was 236 on py3.12 and 235 on py3.13; find why before converting. `test_yahoo_live`'s count moves to a non-live test.
   d. The order checks: declare the YAML data's types so mypy knows them.
   e. After #365 merges: guard commit, a new branch name, record floors, then `mutations/272.toml` (two per converted floor), then close-out. A change that grows a TS guard's population grows its floor: record before the first push.
4. Global rule "No holes" (2026-10-21): check gaps BEFORE and AFTER every change (`~/.claude/global-rules/no-holes-check-before-and-after.md`); every commit message needs its `Gaps checked:` section (hook-enforced; only-.md commits exempt). Before ANY decision question: a limits audit.

## Waiting on Shyden
- **#308's read-only key** (branch-protection read).
- **To put to him (an older reader limit):** a `setattr` write from outside a class (`setattr(box, "least", 5)`) is never read; 3 calls use a non-constant name (`portfolio.py:166`, `:422`, `no_process.py:109`), so it needs his ruling.

## Next on the clean-up queue (all before #222)
- **#365** (5, blocks #272), **#366** (2), **#374** (5), **#377** (2, no git hooks here at all), **#378** (3, gap check in git + CI; blocked by #377), **#348** (5, P1, waits on repo-template#27), **#308** (2, waits on the key), **#315** (2, no Priority field; blocked by repo-template#6), **#317** (5), **#320** (2), **#337** (3), **#336** (5, before #245), **#341** (2), **#359** (3), **#362** (2).

## Lessons this session
- A handover's prediction is not a measurement: "the 4 perf findings clear" held for 3; line 85 reached `SNAPSHOT_VERSION` (`snapprobe.py` measured it before building).
- A more precise reader can expose a blind spot the coarse one hid (`test_income_projection.py:373` lost its floor until `append` was followed).
## Progress (2026-10-21, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points), none in the last 7 days. Board open: 39 tickets, 219 points across 38 scored (epic #214 unscored). Closed 2026-10-14 to 2026-10-21: 9 tickets, 38 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-20, low confidence:** 38 open scored tickets at 1.3 a day is about 30 days.
- **By effort: 219 points remaining across 38 scored open tickets. ETA 2026-11-30, low confidence:** 5.4 points a day is about 40 days.
- **Assumed:** this week's pace holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 (#315), repo-template#27 (#348), Shyden's key (#308).
