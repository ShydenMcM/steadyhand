# Handover: steadyhand

**Updated:** 2026-10-21 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop`. Merge green PRs into `develop` without asking; never `main`.
- **#367 closed 2026-10-21:** merged as PR #372 (`1d2bf57`), with its own floors recorded by the new flow (run 39529922449). PR #369 (same change, pushed without floors) was closed for it.
- **#370 closed 2026-10-21 (P0, filed this session):** certifi 2026.10.19 (PYSEC-2026-4320, compromised emSign intermediates), PR #371 (`eeafe5f`).
- **To delete when Shyden agrees** (closed-unmerged heads, content landed elsewhere): local and remote `367/scratch-ref-recorder` (`3d7160a`, #369), and `272/python-floors` once its new branch lands.
- **`272/python-floors`** (#272, In Progress, 13): worktree `../steadyhand-272`, pushed, head `1c9db9d` when written. No PR. Its pushed commits lack their floors, so the green chain goes to a NEW branch name with a normal push and this one is listed for deletion (never force-push).
- **Uncommitted there, on purpose:** `tests/guards/test_no_literal_floor.py` (lands last); copy in `.superpowers/sdd/272/test_no_literal_floor-20261020a.py`.
- Local branches kept by choice: `203/spec-amendment-wip`, `ext/s3b-guards` (#222 WIP).

## The recorder now (#367)
Push the unpushed commit to `refs/floors/<branch>`, `gh workflow run record-floors.yml --ref develop -f ref=refs/floors/<branch>`, `npm run floors:fetch <run id>` in `extension/`, amend, push the branch normally, delete the ref. Steps and why (GitHub cannot run ON a scratch ref, measured): `.github/workflows/record-floors.yml` header. Global rule amended to match; `global-rules/pending-scratch-ref-dispatch.md` tells other projects.

## #272 state (design and every ruling: `.superpowers/sdd/272/design.md`)
Committed: `55d4604`, `f42fbe0`, `1c9db9d`; local gate green at `1c9db9d` (2,604 unit tests, 100%, both Pythons). 76 findings left at `f42fbe0` = 42 (#365) + 23 counts + 4 perf + 7 order checks (`split.py`). Rulings 2026-10-21: "Exact values" split to #365; "Read both"; "A count is measured" (built); "Reader follows by position".

## Resume steps
1. Run `ListAgents`. No subagents were started.
2. If this file's PR is open: merge it when green (docs fast path).
3. #272 in `../steadyhand-272`, test first, plants then mutations, each step measured:
   a. Reader by position (tuple split, fixture parameters, constructor attributes); re-run `perfvariants.py`: the 4 perf findings must clear with the tests unchanged.
   b. "Read both": the population adds scripts/ and packages/; helper-returned comparisons judged.
   c. The 23 counts become `floor_breach`. `test_fast_path_reads` first: OPENED was 236 on py3.12 and 235 on py3.13; find why before converting. `test_yahoo_live`'s count moves to a non-live test.
   d. The 7 order checks: declare the YAML data's types so mypy knows them.
   e. After #365 merges: guard commit, a new branch name, record floors with the flow above, then `mutations/272.toml` (two per converted floor), then close-out.
   A change that grows a TS guard's population grows its floor: record before the first push (the flow above), or the PR goes red in `extension-guards` as #369 did.
4. Before ANY decision question: a limits audit, and read which side `_compare_bounds` judged before describing a finding's cause.

## Waiting on Shyden
- **#308's read-only key** (branch-protection read).

## Next on the clean-up queue (all before #222)
- **#365** (5, blocks #272; #367 no longer blocks it), **#366** (2), **#348** (5, P1, waits on repo-template#27), **#308** (2, waits on the key), **#315** (2, board has no Priority field; blocked by repo-template#6), **#317** (5), **#320** (2), **#337** (3), **#336** (5, before #245), **#341** (2), **#359** (3), **#362** (2).

## Lessons this session
- A rule's mechanism is measured before it is built on: "runs on a push to the scratch ref" was impossible on GitHub; a 2-minute probe (a throwaway workflow pushed only to a scratch ref, with develop's run as the known positive) settled it before any code.
- `pr-verdict.sh` returns a snapshot; wait with `wait-run.sh` on each run id.
- Record floors BEFORE the first push: #369 pushed a guard-population change without them, and a pushed commit cannot take them (no force-push), so it cost a new branch and PR.
- A new advisory can turn `audit` red on every PR overnight (certifi, #370): read every red job by name, never assume it is the PR's own.
- A push to origin took about 3 minutes here today (network); background it.
- The board's Status has no `Draft` option (Todo, In Progress, Done); the tickets-are-issues migration covers it.

## Progress (2026-10-21, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` tickets left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points), none in the last 7 days. Board open: 38 tickets, 214 points across 37 scored (epic #214 unscored). Closed 2026-10-14 to 2026-10-21: 9 tickets, 38 points (today: #367, #370).
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-19, low confidence:** 37 open scored tickets at 1.3 a day is about 29 days.
- **By effort: 214 points remaining across 37 scored open tickets. ETA 2026-11-29, low confidence:** 5.4 points a day is about 39 days.
- **Assumed:** this week's pace (clean-up, CI and test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315, repo-template#27 for #348, Shyden's key for #308.
