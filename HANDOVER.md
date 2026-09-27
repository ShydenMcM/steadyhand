# Handover: steadyhand

**Updated:** 2026-09-27 03:25 UTC (**M4a is complete: S1-S4 merged into `develop` (#92-#95), deployed, and #87-#90 closed and Done. Next: the M4b plan (S5-S8), and the training brainstorm, which needs Shyden.** Ticket #86 In Progress until the M4b plan merges.)
**Local:** `~/Developer/Repos/steadyhand`. On `m4/m4b-plan`, branched from `develop` at `bb12b26` (S4's merge); this file is its only change so far and travels in the M4b plan PR. Read heads with `git rev-parse`; never retype one. `main` has no release yet.
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
- **Merging (Shyden, 2026-09-27):** merge every green PR into `develop` without asking: *"you don't need to wait for my permission to merge to develop, just merge automatically from now on"*. Never `main`. Keep the discipline: CI completed on the head SHA read from a file, every job `success` by name, `gh pr merge --squash --match-head-commit "$(cat <file>)"`, then `publish-dev` on the develop run. If the classifier denies a merge, do not retry another way; tell Shyden in one line.
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
- **Spec:** `docs/superpowers/specs/2026-09-26-m4-income-design.md`, approved by Shyden 2026-09-26. The exemption protection end is purchase year **+ 2** (spec §2 correction).
- **M4a done (2026-09-27).** Plan `docs/superpowers/plans/2026-09-26-m4a-income-reporting.md` (PR #91, `7cd8cd4`), reviewed to zero on pass 3. Every story was applied from the plan with `apply_task.py`, its red phase matched the plan's count and failure kinds, its code was byte-identical to the verified scratch commit, its gate was green at 100%, its mutations were all caught on the real commit, and `publish-dev` was green after merging:

  | Story | Issue | PR | Merge | Develop run |
  |---|---|---|---|---|
  | S1 received income | #87 | #92 | fd41033 | 36284337515 |
  | S2 run-rate, calendar | #88 | #93 | 9cb193a | 36284582613 |
  | S3 notes, growth, projection | #89 | #94 | 598ace7 | 36289819694 |
  | S4 report, goal, backtest | #90 | #95 | bb12b26 | 36291259882 |

- **Spec amendments made in the M4a plan** (its scope decisions 4 and 5): a split on a dividend's own ex-date restates it; restatement is exact in integers. M4b's plan should cite them.
- **Plan tools, newest copy:** `.superpowers/sdd/2026-09-26-m4a-income/` (gates, redrun, stubgen, render, build_plan, check_plan, apply_task, mutations, wait_ci.sh, template.md, shared-merging.md). New since #84: a `delete` marker; `stubgen` keeps a module that only removes functions as it was in the red phase; `redrun.py`/`check_plan.py` resolve their tree path; `wait_ci.sh` uses its own temp file (two waiters shared one and raced); `shared-merging.md` now says merge without asking. Copy the directory for M4b, rewrite `mutations.py`'s list, `build_plan.py`'s `TASK`/`DEFECT`, and `template.md`.
- **M4b open item for S5:** PMK 18/2021's in-force date is blank in T-TAX; read it from BPK before writing the data row (spec §6.1). S5 also moves `income.py`'s `dividend_tax(..., reinvested_by_deadline=False, ...)` calls off the removed flag.
- **Hypothesis note:** M87 was caught by the scenario-ordering property on one run and not the next; a property's catch is not guaranteed, so a plan's predicted catchers name hand-worked tests.

## Training sub-project (Shyden, 2026-09-26)
- Shyden asked for newbie-friendly training for everything, with an opt-out, and a first-launch question on competency level and training yes/no. **Decided:** its own sub-project, brainstormed **after the M4 spec is approved**; both contextual explanations and a lesson course; content written once as Markdown in the repo, shown by the CLI (from M5 `init`) and later rendered by the dashboard.
- **Legal line** (core spec §3.3): competency may change how much is explained, **never** what the tool suggests trading (that would drift towards licensed advice).
- M4 leaves the hook: every note M4 adds has a stable key (spec §7). Keying M3's existing warnings belongs to the training sub-project.
- No ticket yet: file one with full AC when its brainstorm starts.

## Resume steps
1. The training sub-project brainstorm is due (Shyden's spec decision 8: after the spec's approval, which happened 2026-09-26). It needs Shyden in the session: raise it with `AskUserQuestion` when he is here.
2. Write the M4b plan (S5-S8) on `m4/m4b-plan` with superpowers:writing-plans, by extraction as M4a was: code first in a scratch clone on top of `develop`, gates, red runs, mutations with predictions first, render, replay (`check_plan.py`), review to zero, self-approve. Start with S5's BPK read.
3. File S5-S8, open the M4b plan PR (it carries this file), merge on green without asking, then execute S5-S8 the same way. When the M4b plan merges, #86's last criteria are met.

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
