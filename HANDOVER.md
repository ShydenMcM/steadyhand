# Handover: steadyhand

**Updated:** 2026-09-26 19:02 UTC (**M4a plan written, reviewed to zero and self-approved. Next: push `m4/spec`, file S1-S4, open the plan PR, merge on Shyden's go-ahead, then execute S1.** Branch `m4/spec`; read its head with `git rev-parse HEAD`, never retype one. Ticket #86 In Progress.)
**Local:** `~/Developer/Repos/steadyhand`. On `m4/spec`: the spec commits, `fe1051c` (five-year recordings), `d5d7e21` (the plan), and this file, all on top of `develop` (`8fe2a69`). `main` has no release yet.
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M3 spec:** `docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md`, approved 2026-09-26.
- **M3a plan:** `docs/superpowers/plans/2026-09-26-m3a-engine-day.md`, executed in full on 2026-09-26. Every task's red phase, gate and mutations reproduced the plan's numbers exactly.
- **Stories merged into `develop`, each deployed with `publish-dev` green:**

  | Story | Issue | PR | Merge | Develop run |
  |---|---|---|---|---|
  | S1 | #62 | #69 | 39c7a1c | 36234663632 |
  | S2 | #63 | #70 | fedcb99 | 36236257868 |
  | S3 | #64 | #71 | 936e10c | 36238379009 |
  | S4 | #65 | #72 | 7edf533 | 36240622744 |
  | S5 | #66 | #73 | 3fdb1f8 | 36240786668 |
  | S6 | #67 | #74 | 06b7f73 | 36241093106 |

  #62–#67 are closed, with evidence comments, and read Done on the board. #61 has a comment recording that M3a is done.
- **S6 local evidence:** red phase 690 run / 23 failed (all `NotImplementedError`), gate 690 passed at 100% branch coverage (2,604 statements, 688 branches), and M29–M33 each red with the total unchanged, every catcher set as predicted.
- **Ticket #61** (M3 plans), In Progress. Its M3a criteria are met; its M3b criteria are met by the plan PR, after which #61 moves to Done.
- **Merging:** each agent merge needs Shyden's go-ahead in the session, through `AskUserQuestion` naming the PR, its head SHA read from a file in that same turn, and the CI state. Pin the merge with `--match-head-commit "$(cat <file>)"`.
- **Plan tools** (git-ignored, reusable for M3b): `.superpowers/sdd/2026-09-26-m3a-engine-day/`. `stubgen.py`, `redrun.py`, `gates.py`, `mutations.py`, `render.py`, `fill.py`, `check_plan.py`. Run them with `uv run --no-project --python 3.12 python`. **`mutations.py` now runs pytest under `HYPOTHESIS_PROFILE=ci`.** Under the default `dev` profile, M18's property-test catcher was missed; under `ci` it caught it in 3 of 3 runs. A plan's mutation table is a claim about CI's profile.
- **Applying a plan task by script:** `apply_task.py <plan> <tree> <task> red|green` (in the plan tools directory) applies a task's blocks up to or after its red marker. It stops if any edit anchor matches anything other than exactly once. It applied every M3a task.

## M3b (plan approved and merged 2026-09-26, PR #79 `a642b17`; #61 Done)
- **Plan:** `docs/superpowers/plans/2026-09-26-m3b-backtester.md`. Each story was applied from the plan by `apply_task.py`; its red count matched, its tree was byte-identical to the plan's verified commit (checked against a live `git diff` control), its gate was green, and its mutations were all caught on the story's own commit.

  | Story | Issue | PR | Merge | Develop run |
  |---|---|---|---|---|
  | S7 backtest | #75 | #80 | b318e76 | 36246848386 |
  | S8 metrics | #76 | #81 | cf10525 | 36247075105 |
  | S9 golden + truncation | #77 | #82 | e3c51f3 | 36248773000 |
  | S10 performance + cash ledger | #78 | #83 | b4d558d | 36250088306 |

- **S10 evidence:** red 738 run / 0 failed (by design), and the perf test still running past 45 s on the old `Portfolio`; gate 738 passed at 100%; M57–M59 caught. **Perf baseline** (CI run 36248966364): 20.85 s on py3.12 and 12.43 s on py3.13 against the 30 s budget, and 10.46 s locally. Recorded on #78.
- **Build tooling** (git-ignored `.superpowers/sdd/2026-09-26-m3b-backtester/`): the scratch clone `repo/`, `stories.txt`, `wait_ci.sh <sha file> <branch>` (dry-run with `DRY_RUN=1`), and the plan tools. Merge SHAs are kept in `merge*-sha` files there.

## #84 constant-time ledger booking (done 2026-09-26)
- **Plan:** `docs/superpowers/plans/2026-09-26-constant-time-ledger.md`. Scope decision 1 is the design note: `Portfolio.ledger` stays a `tuple`; internally it is a shared chain of two-slot tuples, walked once per snapshot on first read. **M5 should save that tuple; if it wants each day's new movements, add a method yielding only those, never a daily read of `.ledger` (that would be quadratic again).**
- **CI perf step** (pytest summary line): py3.12 16.51 s (was 20.85 s), py3.13 8.43 s (was 12.43 s). Recorded on #84.
- **Plan tooling, newest copy:** `.superpowers/sdd/2026-09-26-s11-ledger/` (git-ignored). `render.py` has `@@rewrite N` (a story that changes no public name: red is the new tests on the old code); `mutations.py` resolves its worktree path; `gates.py` returns the scratch repo to its branch. Start the next plan's tools from this copy.

## M4 income (spec 2026-09-26, ticket #86)
- **Spec:** `docs/superpowers/specs/2026-09-26-m4-income-design.md`, approved by Shyden 2026-09-26. Decisions in its §2 (split M4a/M4b; goal on take-home; projection from the run-rate; pure functions; settlement grace). The exemption protection end is purchase year **+ 2** (spec §2 correction).
- **M4a plan:** `docs/superpowers/plans/2026-09-26-m4a-income-reporting.md`. Tasks 0-4 = the plan PR and stories S1-S4. Reviewed to zero on pass 3 and self-approved (review log at its end). Verified by extraction: story commits in the scratch clone `.superpowers/sdd/2026-09-26-m4a-income/repo` (branch `m4a-stories`; SHAs in `stories.txt`, base in `base-sha` = the recordings commit), gates green (757/778/812/830 at 100%), `check_plan.py` replay "problems: 0" with every tree byte-identical, 37 mutations (M67-M103) all caught.
- **Scope decisions worth knowing before executing** (plan §"Scope decisions"): `income_report` takes 5 args via `IncomeSettings`; a split on the dividend's own ex-date restates it and restatement is exact in integers (both amend spec §3.3); `notes.py` lands in S3, not S1; the golden run moves to five-year recordings and gains a goal (every S9 figure unchanged, checked); the perf test's synthetic dividend moved to the first weekday from 15 June.
- **Executing a story:** `apply_task.py <plan> <tree> <task> red|green` in the plan tools dir applies a task's blocks. Task 4's golden file is generated by `uv run python scripts/record_golden.py` (its SHA-256 is in the plan); `apply_task.py` does not run it, so run it by hand after the green blocks, then Step 6's check.
- **Plan tools, newest copy:** `.superpowers/sdd/2026-09-26-m4a-income/`. New since #84: a `delete` marker (render, apply_task, check_plan); `stubgen` keeps a module that only removes functions as it was in the red phase; `redrun.py` and `check_plan.py` resolve their tree path (a relative one lost pytest's report). Start M4b's tools from this copy.
- **Open item for S5 (M4b):** PMK 18/2021's in-force date is blank in T-TAX; read it from BPK before writing the data row.

## Training sub-project (Shyden, 2026-09-26)
- Shyden asked for newbie-friendly training for everything, with an opt-out, and a first-launch question on competency level and training yes/no. **Decided:** its own sub-project, brainstormed **after the M4 spec is approved**; both contextual explanations and a lesson course; content written once as Markdown in the repo, shown by the CLI (from M5 `init`) and later rendered by the dashboard.
- **Legal line** (core spec §3.3): competency may change how much is explained, **never** what the tool suggests trading (that would drift towards licensed advice).
- M4 leaves the hook: every note M4 adds has a stable key (spec §7). Keying M3's existing warnings belongs to the training sub-project.
- No ticket yet: file one with full AC when its brainstorm starts.

## Resume steps
1. `git push -u origin m4/spec` (runs as the App). Confirm with `git ls-remote origin m4/spec`.
2. Plan Task 0 Step 3: file S1-S4 as issues (title from the plan's Stories table, body = that task's acceptance criteria), add each to board project 1, Status Todo, read each card back via its `PVTI_` node asserting `project.title` = `steadyhand`. Tick #86's "Stories S1-S4 are filed" and "M4a plan ... reviewed to zero" criteria.
3. Open the PR `m4/spec` -> `develop` (`Refs #86`, never a closing keyword). Wait for CI on the head SHA (write it to a file), read every job by name, then ask Shyden to approve the merge with `AskUserQuestion` (PR, head SHA read from the file that turn, CI state). Merge with `--match-head-commit`. Check `publish-dev` on the develop run.
4. Execute S1 (plan Task 1) on `m4/s1-received-income` from `origin/develop`, then S2-S4 in order, each merged the same way.
5. The training sub-project brainstorm is due now: Shyden decided it follows the spec's approval (spec decision 8), which has happened. It needs Shyden in the session, so raise it when he is.
6. After M4a merges: write the M4b plan (S5-S8) the same way.

## Research technique
- **Shyden's decision (2026-09-25): use another source before idx.co.id.** IDX's Terms of Use forbid scraping. Try the Internet Archive, KSEI, KPEI (idclear) or BPK first. Use idx.co.id only when none has a readable copy, and say so in the research doc.
- **Internet Archive:** use the CDX API (`web.archive.org/cdx/search/cdx`, `matchType=prefix` or `domain`, `filter=`, `collapse=urlkey`; pass `curl -g` when the filter has brackets), then `https://web.archive.org/web/<ts>id_/<original>`, spaced about 4 s apart. Some indexed captures 404 on replay, and some are **truncated at exactly 1 MiB**: check the PDF's EOF marker.
- **An IDX rule's cover decision can hold its own attachment back.** Read the cover's MEMUTUSKAN items and the revocation clause before quoting an attachment as in force.
- **BPK** serves curl: search with `peraturan.bpk.go.id/Search?keywords=…&nomor=…&tahun=…`, then `/Details/<id>` and its `/Download/…` PDF. Text PDFs: `uv run --no-project --with pypdf`.
- **Yahoo probes:** `uv run --no-project --with yfinance==1.7.0`. `history(raise_errors=…)` is deprecated in 1.7.0; set `yfinance.config.debug.hide_exceptions = False` instead.
- **Pages that refuse curl** (403, such as ajaib.co.id): read them in Chrome with `browser_batch` (`navigate` + `get_page_text`).
- Cloudflare sometimes shows a "verify you are human" box. Never click it; ask Shyden.

## Notes
- This is a personal project: not Shyden Ltd, and not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM project 1**, node `PVT_kwHOCQ_jzM4BkhEb`. Assert the title "steadyhand" before writing to it (`gh project view 1 --owner ShydenMcM --format json`). `gh project` calls run on the operator's login, while agent `gh api` calls run as the App, which cannot see this user-owned board, so an issue's `projectItems` reads empty. Get a card's id from `gh project item-add 1 --owner ShydenMcM --url … --format json --jq .id`, which is idempotent for an existing card. Status field `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk`: Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`.
- Agent git and gh act as the `steadyhand-agent` App (administration: read). An admin write is Shyden's decision.
- The `python3` on this machine is Xcode's 3.9, which has no `tomllib` and no `X | Y` in `isinstance`. The code uses uv's Python 3.12 and 3.13, and uv is pinned to 0.12.18.
- **zsh:** an unquoted `$VAR` holding a command does not split into words; write `${=VAR}`. And a pytest status read through `| tail` is `tail`'s: capture `rc=$?` with no pipe in between.
- **A TestPyPI publish failure is not always ours.** An OIDC or TLS timeout goes away with `gh run rerun <id> --failed`, and `skip-existing` makes that safe.
- **Mutation tallies:** print the full `FAILED` ids, not `sort -u` of names, because parametrised cases collapse into one name.
- **Timestamps:** stamp status lines only from a `date -u` read.
