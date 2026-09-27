# Handover: steadyhand

**Updated:** 2026-09-27 10:40 UTC (**The M4b plan is approved** and its PR carries the plan and five new recordings. Stories S5–S8 are #110–#113, Todo. **Next: execute Task 1 (S5, #110).**)
**Local:** `~/Developer/Repos/steadyhand`. `develop` holds the T1 spec and plan, and `main` has no release yet. `t1/training-spec` and `m4/m4b-plan` are merged or superseded and deleted. Start each story's branch from `origin/develop`. Read heads with `git rev-parse`; never retype one.
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
- **M4b's PMK 18/2021 read is done:** in force 17 February 2021 (Pasal 119; BPK Download/155338, p158). S5 writes it into T-TAX. Pasal 109's refund route for dividends since 2 November 2020 is recorded, not modelled (M4b scope decision 1).
- **Hypothesis note:** M87 was caught by the scenario-ordering property on one run and not the next; a property's catch is not guaranteed, so a plan's predicted catchers name hand-worked tests.

## M4b exemption claim (plan approved 2026-09-27, ticket #86)
- **Plan:** `docs/superpowers/plans/2026-09-27-m4b-exemption-claim.md`, built by extraction and reviewed to zero on pass 5. Its twelve scope decisions fill in or amend the M4 spec: the rule's start, the `dividend_exemption` table in `fees.toml` (from 2009, so `verified_from` stays 1 January 2021), `Payout`, the claim's `uncovered` part, the two bookkeeping functions, the break tie-break, and the switch-on golden run's scripted trader (`ExemptionScript`) over new recordings to 29 April 2022, which the plan PR carries.
- **Scratch chain** (`.superpowers/sdd/2026-09-27-m4b-exemption/repo`, branch `m4b-chain2`): fixtures `cf283a6`, then S5 `fff6fa7`, S6 `7223349`, S7 `3e728f8`, S8 `813ae4c` (full SHAs in `stories.txt`). Every story passed CI's gate on its own commit (1021, 1037, 1049, 1053 tests at 100%; perf 7.6–8.4 s), its red phase fails for the right reasons (51, 18, 28, 4), 32 mutations (M140–M171) all go red (31 exactly as predicted, M155 with one more catcher), and the plan replays byte-identical from its own text.
- **Stories:** S5 #110, S6 #111, S7 #112, S8 #113 (Todo). Each merges as the plan's **Merging a story** says; `close_story.sh <issue> <pr> <develop run>` in the tools directory closes one.
- **Tools** (git-ignored, newest copy): `.superpowers/sdd/2026-09-27-m4b-exemption/`. New: `stubgen` keeps a pre-existing class's fields in the red phase (S5's first red run failed 241 unrelated tests without it); `file_stories.sh`; worktrees `wt-red`, `wt-mut`, `wt-replay`.

## T1 training foundation (spec approved 2026-09-27, ticket #96)
- **Spec:** `docs/superpowers/specs/2026-09-27-training-design.md`, approved by Shyden after a section-by-section design and 3 review passes. It records the decisions: any self-hoster in English (with an `en/` folder), three levels plus off, the foundation built before M4b, M3's warnings keyed, `term.*` keys derived by a type walk from the report roots, lessons shipped in both wheels, and an import allowlist as the legal control.
- **Plan:** `docs/superpowers/plans/2026-09-27-t1-training-foundation.md`, built by extraction and reviewed to zero on pass 2. Every story was built and gated first in a scratch chain (`develop` `acca50e` + the spec, then S1 `0779c10`, S2 `9867efe`, S3 `aae3144`, S4 `1053538`). The plan replays byte-identical from its own text, and 36 mutations (M104–M139) all go red, 35 of them exactly as predicted and M138 by hand. Its scope decisions 1–3 amend the T1 spec: `LessonNotFoundError`, `LESSONS` and `catalogue()` in S4, and the figure walk reading properties and skipping private names.
- **Executed 2026-09-27.** Each story was applied with `apply_task.py`, its red count and failure kinds matched the plan, its code was byte-identical to the scratch commit (only the plan and handover docs differ, which `develop` already had), its gate was green at 100%, and its mutations were all caught on the real commit. S2–S4 were built stacked on the previous story and cherry-picked onto `develop` after its squash merge, with the tree checked identical.

  | Story | Issue | PR | Merge | Develop run |
  |---|---|---|---|---|
  | S1 keys | #99 | #105 | 68eb583 | 36308697779 |
  | S2 catalogue | #100 | #106 | 58324e5 | 36309132815 |
  | S3 renderer | #101 | #107 | cdd7df3 | 36309330894 |
  | S4 content | #102 | #108 | 2342be8 | 36309671264 |

- **S4 finding:** `tax.dividend` stated the day-15 payment rule without citing t-tax §5, where PMK 81/2024 Pasal 373 is quoted. PR #108's second commit adds the citation. The plan's Step 6 check is document-level and passed; the section-level check (`scratchpad` script, 48 values) is what found it.
- **Story close-out script:** `.superpowers/sdd/2026-09-27-t1-training/close_story.sh <issue> <pr> <develop run>` comments, closes, moves the card to Done and reads it back through the `PVTI_` node.
- **Plan tools** (git-ignored): `.superpowers/sdd/2026-09-27-t1-training/`. The scratch clone `repo/` (branch `t1-chain2`), `stories.txt`, `plan-base-sha`, `mutations.py` (M104–M139), `fills/` (red and gate results), `mut-all.log`, and the worktrees `wt-red`, `wt-mut` and `wt-replay`. New since M4a: `build_plan.py` fills any «FIELD» from `fills/FIELD.md`, and `render.py`'s `MAX_HUNKS` is 10.

## Bug #97 (done 2026-09-27)
- Gating T1 found a defect already on `develop`. The M4a projection rounded income down every month, so a larger contribution could take longer (Rp6 a month took 1.7 years where Rp5 took 1.6). It is fixed in PR #98, merged as `acca50e`: the yield is kept as an exact integer ratio and rounded down only where a month uses it. The counterexample is pinned as an `@example`. PR CI run 36305425417 and develop run 36305531569 were green, `publish-dev` included. #97 is closed and Done.

## Training sub-project background (Shyden, 2026-09-26)
- Shyden asked for newbie-friendly training for everything, with an opt-out, and a first-launch question on competency level and training yes/no. **Decided:** its own sub-project, brainstormed **after the M4 spec is approved**; both contextual explanations and a lesson course; content written once as Markdown in the repo, shown by the CLI (from M5 `init`) and later rendered by the dashboard.
- **Legal line** (core spec §3.3): competency may change how much is explained, **never** what the tool suggests trading (that would drift towards licensed advice).
- M4 leaves the hook: every note M4 adds has a stable key (spec §7). Keying M3's existing warnings belongs to the training sub-project.
- Brainstormed 2026-09-27: see the T1 section above.

## Resume steps
1. If the plan PR (`m4/m4b-plan`) is not merged yet, merge it as the plan's **Merging a story** says.
2. Execute the plan's Task 1 (S5, #110) from `origin/develop`: `apply_task.py <plan> <tree> 1 red`, compare the red run with the plan, then `green`; check the tree equals the scratch S5 commit apart from the plan and handover docs; run the gate and M140–M148; PR, merge, deploy, close. Then Tasks 2–4 the same way, each on the previous story's merge.

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
- **macOS has no `tac`** (use `tail -r`). A `$(tac …)` that fails leaves an empty list, and `git switch -C` then resets the branch with nothing to pick: check the list is non-empty before any reset. Recovered from the reflog on 2026-09-27.
