# Handover: steadyhand

**Updated:** 2026-10-03 16:45 WIB (2026-10-03 09:45 UTC) (**the standing test clean-ups come before M7**: #173, #179 and #174-#177 are merged and deployed, and the one-test-per-case guard is strict; next #178, then #184, then M7. See Resume steps 1.)
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
- **Executed 2026-09-27.** Each story was applied with `apply_task.py`, its red count and failure kinds matched the plan, its tree was byte-identical to the scratch commit (only the plan and handover docs differ), its gate was green at 100%, and its mutations were all caught on the real commit (M155 with one more catcher, as in the plan). S6–S8 were built stacked and moved onto `develop` by SHA after each squash merge, with each tree checked unchanged.

  | Story | Issue | PR | Merge | Develop run |
  |---|---|---|---|---|
  | Plan and recordings | #86 | #114 | d55ea8b | 36313303284 |
  | S5 rules, switch, claim | #110 | #115 | 7363018 | 36313474258 |
  | S6 matching, deadline tax | #111 | #116 | 6fa386b | 36313957374 |
  | S7 protection, grace, breaks | #112 | #117 | 66500d8 | 36314142172 |
  | S8 report, switch-on golden | #113 | #118 | 3f79c3e | 36314316667 |

- **Story scripts** (tools directory): `file_stories.sh`, `merge_story.sh <pr> <first M> <last M> <total> <log> <mutated commit>` (posts the mutation results, checks the mutated tree equals the PR head, merges pinned to it) and `close_story.sh <issue> <pr> <develop run>`.
- **Tools** (git-ignored, newest copy): `.superpowers/sdd/2026-09-27-m4b-exemption/`. New: `stubgen` keeps a pre-existing class's fields in the red phase (S5's first red run failed 241 unrelated tests without it); `file_stories.sh`; worktrees `wt-red`, `wt-mut`, `wt-replay`.

## M5 paper trading and the CLI (spec approved 2026-09-27, epic #120)
- **Spec:** `docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md`, reviewed to zero on pass 8 and approved by Shyden, including 19 details listed to him item by item. Branch `m5/spec`; the spec PR carries this handover.
- **Decisions:** one spec, two plans (M5a S1–S4 config and stateless CLI; M5b S5–S8 paper trading); missed days are caught up in order (cap 30, `--catch-up` lifts it); a strategy change needs `paper switch`; state is one snapshot row plus append-only `day_reports`, `audit`, `runs`.
- **Things the plans must not miss:** `[training]` is parsed by `output.py`, never `config.py` (T1 §5 item 3); `Portfolio.restore` is a new engine constructor (S5); the fetch step of `backtest` becomes public and paper calls it over the whole range from the opening day (the golden invariant paper == backtest depends on it); guides move into the engine wheel (S4); performance budgets are measured in the scratch build, then pinned.
- **Epic card:** `PVTI_lAHOCQ_jzM4BkhEbzg9CRmw`, In Progress.
- **M5a plan:** `docs/superpowers/plans/2026-09-27-m5a-cli.md`, built by extraction and reviewed to zero on pass 3. Scratch chain (`.superpowers/sdd/2026-09-27-m5a-cli/repo`, branch `m5a-chain4`) on `develop` `c2b8062`: S1 `1a58cf2`, S2 `426739f`, S3 `670cab2`, S4 `e10a47f` (full SHAs in `stories.txt`). Gates 1122, 1207, 1257, 1272 at 100%; red 69, 80, 44, 41 failed; 47 mutations M172–M218 all red (45 exactly as predicted, M193 and M207 with one more catcher), M219 by hand; the plan replays byte-identical from its own text. Its fourteen scope decisions amend the M5 spec: `main(argv, world)`, a context-manager source, `buy-and-hold` default, the config ranges, an engine `compare`, the CSV's two dividend columns, `Registered(make, summary, turnover)` callable, the wheel check as a CI step, and more.
- **Executed 2026-09-27.** Each story was applied with `apply_task.py`; its red count matched, its code tree was byte-identical to the scratch commit (only the plan and handover docs differ), its gate was green at 100%, and its mutations were all caught on the real commit exactly as the plan predicts (M219 by hand on S4). S2–S4 were built stacked and moved onto `develop` with `rebase --onto` after each squash merge; `develop` requires a branch up to date, so S1 was rebased after the plan merged.

  | Story | Issue | PR | Merge | Develop run |
  |---|---|---|---|---|
  | Plan | #120 | #126 | 6cc6115 | 36331687408 |
  | S1 config | #122 | #127 | ff73a95 | 36332354155 |
  | S2 shell, init, training, learn | #123 | #128 | b1450b1 | 36332826309 |
  | S3 backtest, compare | #124 | #129 | 058dad8 | 36333114942 |
  | S4 guides, strategies, explain | #125 | #130 | 9a78c9e | 36333553346 |

- **Execution finding:** S4's red phase reads `39 failed, 2 errors` in pytest where the plan said "41 failed" (two tests stop in a fixture that builds a stubbed name). PR #130 corrected the plan's text; `redrun.py` now prints pytest's own split.
- **Found while building (carried forward):** a backtest ending on the recordings' last day but starting late (25–31 January 2022) stops with exit 3: its income report reads five years back into BBRI's unrecoverable prices. M4 §8's rule, kept; whether an income report should leave out such a stock is a question for its own ticket.
- **M5a tools** (git-ignored, newest copy): `.superpowers/sdd/2026-09-27-m5a-cli/`. New: `render.py` and `redrun.py` list files with `--no-renames` (a moved file was rendered with no delete); `wheel_check.sh <tree>` runs CI's guide step locally from `ci.yml` itself; `prose_check.py <plan>` checks every cited test exists and each task's mutation range; `rerun.sh`; worktrees `wt-red`, `wt-mut`, `wt-replay`, `wt-wheel`.

## M5b paper trading (plan approved 2026-09-30, done 2026-09-30, epic #120 Done)
- **Merged into `develop`, each deployed with `publish-dev` green:**

  | Story | Issue | PR | Merge | Develop run | Gate | Mutations |
  |---|---|---|---|---|---|---|
  | S5 snapshot codec | #135 | #140 | fd90040 | 36633548195 | 1323 | M220–M236 |
  | S6 state database | #136 | #141 | 5c5ba81 | 36648875544 | 1354 | M237–M246, M264 |
  | S7 `paper run` | #137 | #142 | a09c39e | 36650250101 | 1390 | M247–M263, M265 |
  | S8 every order reason keyed | #138 | #143 | 6f5afb5 | 36650747043 | 1389 | M266–M273 |
  | S9 the paper commands | #139 | #144 | 434d886 | 36651146684 | 1443 | M274–M295 |

  Every gate at 100% branch coverage on Python 3.12, with the suite also passing on 3.13 under `-W error`; every mutation red exactly as predicted, with the total unchanged; each PR carries its mutation comment.
- **Execution finding** (the plan's `## Execution findings`): S6 failed CI's `test (py3.13)` on 15 `ResourceWarning: unclosed database` from a test helper; 3.12 does not warn, and the plan had been gated on 3.12 alone. Fixed with `closing(...)`, the same sweep hardened one S7 test, and `gate-local.sh` now runs 3.13 too.
- **Tooling change:** `merge_story.sh` selects a story's mutations by the story label in the log, since S6's and S7's sets are not contiguous, and refuses a log with an anchor failure, a missed catcher, a crash, a wrong total or a line not PREDICTED/SUPERSET.
- **Plan:** `docs/superpowers/plans/2026-09-29-m5b-paper-trading.md`, built by extraction and reviewed to zero on pass 5. Five stories: S5 snapshot codec, S6 state database, S7 `paper run`, S8 every order reason keyed, S9 the paper commands (M5 §10's S8 split in two, scope decision 14). Twenty-three scope decisions amend the M5 spec (among them: no `Portfolio.restore`, `Config.goal` non-optional, `resume` refused while the drawdown is at or past the limit, a prompt's change refused if another run saved a day meanwhile).
- **Scratch chain** (`.superpowers/sdd/2026-09-29-m5b-paper/repo`, branch `m5b-chain2`) on `develop` `9cd514c`: S5 `a583773`, S6 `f41d97e`, S7 `e8bab1e`, S8 `dabc803`, S9 `a33a143` (full SHAs in `stories.txt`). Gates 1323, 1354, 1390, 1389, 1443 at 100%; red 41, 30, 51, 31, 55; 76 mutations M220–M295 all red exactly as predicted (`mut-final.log`); the plan replays byte-identical (`replay.out`).
- **Tools** (git-ignored, newest copy): `.superpowers/sdd/2026-09-29-m5b-paper/`. New: `stubgen` keeps a removed top-level function's old definition in the red phase (a rename); `prose_check.py` reads every story's tree; `interface_check.py` (every Produces name defined in its story's tree, with a positive control); `gate-local.sh`, `chain-final.sh`; worktrees `wt-dev`, `wt-red`, `wt-mut`, `wt-replay`. Build findings: `build-log.md`.
- **Performance** (idle machine): one day on a five-year account 0.17 s (budget 1 s), a 30-day catch-up 1.64 s (10 s), a five-year state 650,053 bytes (800,000). A perf run beside another session's Playwright starved 7 of 8 tests: time nothing beside a heavy job.

## M6 strategy wave 1 (spec approved 2026-09-30, done 2026-10-01, epic #146 Done)
- **Merged into `develop`, each deployed with `publish-dev` green:**

  | Story | Issue | PR | Merge | Develop run |
  |---|---|---|---|---|
  | S1 | #149 | #154 | 32015b2 | 36790760852 |
  | S2 | #150 | #155 | 05f33f4 | 36792120737 |
  | S3 | #151 | #156 | c3a939c | 36793660355 |
  | S4 | #152 | #157 | 5d5b9f5 | 36796224511 |
  | S5 | #153 | #158 | 0226bb2 | 36797176250 |

  Every story's red phase matched the plan by count and by kind, its tree was byte-identical to the scratch commit (new files compared with `git add -N`), and its gate matched the plan (1486, 1500, 1529, 1594, 1595 at 100% on 3.12 and 3.13). All 77 mutations M296–M372 ran red on the real commits with the total unchanged; every SUPERSET had exactly the plan run's catchers. Each PR carries its mutation comment.
- **Spec:** `docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md` (PR #147, `e2d36e4`).
- **Plan:** `docs/superpowers/plans/2026-09-30-m6-strategy-wave-1.md`, built by extraction and reviewed to zero on pass 8 (its review log). Five stories, not the spec's four (Shyden's decision, 2026-09-30): S1 engine data path, S2 the IDX dividends-only look-back, S3 `monthly-savings`, S4 `dividend-growth` + default + golden run, S5 module 8. Fifteen scope decisions amend the spec.
- **Scratch chain** (`.superpowers/sdd/2026-09-30-m6-wave1/repo`, branch `m6-chain`) on `develop` `e2d36e4`: SHAs in `stories.txt` there (S1 `31ff423`, S2 `3726991`, S3 `e6c5a1f`, S4 `c1745a7`, S5 `9c87c50`). Gates 1486, 1500, 1529, 1594, 1595 at 100% on 3.12 and 3.13 (`gates.py` now runs 3.13); red 35, 20, 29, 58, 2; 77 mutations M296–M372 all red (`mut-final.log`); the plan replays byte-identical (`replay2.out`).
- **Tools** (git-ignored, newest copy): `.superpowers/sdd/2026-09-30-m6-wave1/`. New: `stubgen` stubs a new `__post_init__` as `return`, keeps the body of a function the module calls at import, and re-adds a renamed method's old text; `redrun.py`, `check_plan.py` and the plan's red step pass `--continue-on-collection-errors`; `gates.py` runs Python 3.13; `prose_check.py` and `interface_check.py` carry M6's ranges and search `scripts/`. Build findings: `build-log.md`; state: `PROGRESS.md`. Added while executing: `red_kinds.sh <pytest output>` (failure kinds per section, validated against every story's plan answer), `mut_summary.sh <log>` (the story's lines, and each SUPERSET compared with the plan's run), and `wait_ci.sh` now re-watches until the run reads `completed` and exits 0 only on completed + success (`gh run watch` returned on S4's develop run before `publish-dev` had started).
- **For Shyden (carried forward):** the engine still credits nothing on a day whose prices the source refused, although the IDX source can now read that day's dividend; crediting it changes M3's figures, so it wants its own ticket and his decision.

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

## Standing test clean-ups (global rules of 2026-10-02; started 2026-10-03, before M7)
Shyden's global CLAUDE.md requires three clean-ups in every repo before other test work: one test per case, every guard proving what it saw, and no retries. They are tickets #173–#179 on the steadyhand board.

| Ticket | What | State |
|---|---|---|
| #173 | `tests/meta/test_one_test_per_case.py` + `looped_cases.py`: refuses a judging loop in a test body, with a shrink-only `BURN_DOWN` (88 sites in 66 tests on 2026-10-03), retired by #177: the guard now refuses any looped case | Done (PR #180, `c373cd1`) |
| #179 | Yahoo asks once and fails fast by name; `tests/meta/test_no_retry.py` refuses any retry in `packages/` | Done (PR #181, `8a071fc`) |
| #174 | convert `tests/cli` + `tests/scripts` (12 sites) | Done (PR #182, `07d65a5`) |
| #175 | convert `tests/engine` (35 sites) | Done (PR #185, `f62a388`) |
| #176 | convert `tests/idx` + `tests/golden` (25 sites) | Done (PR #187, `b65b8f1`) |
| #177 | convert `tests/meta` + `tests/perf` (16 sites) | Done (PR #188, `4fecd70`; retired `BURN_DOWN`) |
| #178 | guard-liveness audit of every guard (15 test files + 3 reader modules) | Todo |
| #184 | engine tests asserting an absence over a run that never produces the thing (found in #175: the refused-day order checks) | Todo |

- **How a conversion ticket runs** (as #174 did):
  1. Classify each site in the ticket before changing anything: known before the run → `@pytest.mark.parametrize`; runtime population or one sequential journey → `# runtime population: <why>` on the loop's first line. For an `all(`/`any(` call, open it on its own line so the comment sits on the call's line.
  2. Keep every assertion. A whole-population fact (a count, an exit code) becomes its own test. An expensive setup becomes a module-scoped fixture.
  3. Run #173's guard: every converted file must fail "these no longer loop" and none "a fixed population". Then delete those `BURN_DOWN` entries by script, asserting the count.
  4. Make one production mutation per converted test that breaks a single case. A mutation in the constant the test reads is tautological; break the code that uses it. A state that carries forward (monthly savings) leaks into the next case, so pick the case whose successor tolerates it.
  5. Record `--durations` before and after on an idle machine, and say when load explains a difference.
- **Live check of #179:** the daily `yahoo-shape` schedule ran against Yahoo on `8a071fc`, the one-attempt client, and passed (run 37104917431).
- **Already flagged for #178:** `test_no_float.py` asserts `findings == {}` with only a file-name subset as liveness, which is files opened, not judged units.
- **Tools** (git-ignored, `.superpowers/sdd/2026-10-03-test-audit/`): `judging.py` (an independent scan of judging loops), `burn_down.py` (prints the totals and the `BURN_DOWN` literal from the guard's reader), `file_ticket.sh <title> <body>` (asserts the board title, files the issue, sets Todo, reads it back), `mutate173.py`, `mutate179.py` (whole suite per mutation), `mutate174.py` and `mutate175.py` (one file per mutation, the exact failing set), `probe175.py` (what the refused-days run queues and fills each day), `classify174.md`, `classify175.md`, `classify174.md`, `pr*.md`, and the worktree `wt-mut`. Run the mutation scripts with `python -u` so their logs stream.
- **Lessons recorded in memory this session:** build a mutation's prediction from the guard's own findings, never from a looser scan or a list cut with `tail`, and reconcile its sum against the printed total. The reply header opens the turn's final text block.
- **#175 lessons:** a check whose run never produces the thing cannot be mutated red; trying to mutate each converted test is how #175 found the refused-day order checks blind (#184). Durations compare only back to back under the same load: run `develop` in the worktree straight after the branch. Never start a second `uv run --python X` in a tree whose gate is running: it rebuilds the shared `.venv` under the gate (a 3.13 run failed on missing yfinance metadata).
- **#176/#177:** a repeated action (`for _ in range(2)`) is a sequence, written out as named steps, not a case or a runtime population. A mutation that would also break other users of the same code is run against the converted test's node only (`mutate176.py`, `mutate177.py`). `land.sh <pr> <branch> <head file> <tag>` waits for the PR's CI, merges matching the head, and waits for the develop run. A timed backtest moved into a fixture reports as **setup** in `--durations`.

## Resume steps
0. M6 is done. `main` still has no release (M10).
1. **First, the standing test clean-ups** (section above): #178 (the guard-liveness audit: list every guard from the code, record the unit it judges against the unit its liveness counts, prove each flag with a blinding mutation, fix with controls (a)-(d), file the rest), then #184 (absence checks that cannot fail), one branch and PR each, merged into `develop` when CI is green. Start by re-reading the ticket. **Then M7, strategy wave 2** (core design §M6–M9: "Strategy waves 1–4, each with its guides"). It has no spec yet: start with brainstorming, then the spec reviewed to zero, then the plan built by extraction as M6's was (copy the tools from `.superpowers/sdd/2026-09-30-m6-wave1/`, the newest copy). The M3 spec's table puts **bars before the backtest's start** (a price look-back) in M7; M6 built only the dividend look-back.
2. **#160 recover Yahoo's unreported price factor: DONE 2026-10-03** (plan `docs/superpowers/plans/2026-10-01-price-factor-recovery.md`, spec `docs/superpowers/specs/2026-10-01-price-factor-recovery-design.md`, both merged in PR #165 `833005a`). Every story was applied from the plan by `apply_task.py`, is byte-identical to the verified chain commit, matched the plan's red count and failure kinds, was green at 100% branch coverage, had all its mutations caught on the real commit, and was deployed with `publish-dev` green:

   | Story | Issue | PR | Merge | Red | Gate | Mutations |
   |---|---|---|---|---|---|---|
   | S1 price-factor proof | #166 | #169 | 1e99356 | 30 / 1625 | 1625 | M373-M385 13/13 |
   | S2 source and cache | #167 | #170 | e19f163 | 137 + 7 errors / 1650 | 1650 | M386-M402 17/17 |
   | S3 notes and lesson | #168 | #171 | 6d29798 | 15 / 1659 | 1659 | M403-M412 10/10 |

   - BBRI's 146 refused days in the golden windows are restored (factor 1.100019, proven by 7,380 prices); #170's body tables every golden figure that moved, with its cause. Each golden run now carries a `data.prices.restored` warning.
   - **#160 stays open for Shyden:** its title and criteria still describe crediting a refused day's dividend; rewriting them to the spec is his. #161 and #162 are on the board as Todo.
   - The plan tools in git-ignored `.superpowers/sdd/2026-10-01-160-plan/` (`apply_task.py`, `mutations.py`, `pass_checks.sh`, `amend_chain.py`, `cite_check.py`, `files_check.py`, `blocks_same.py`, `comments_of.py`, `close_story.sh`) are the newest copies: copy them for M7's plan. `mutations.py` takes `<repo> <worktree> <stories file> [ids]`; to run it on real commits, point it at this repo, a `git worktree add --detach` tree, and a stories file of the real story SHAs.
3. **Session naming:** `.claude/settings.local.json` has a SessionStart hook returning `sessionTitle: "Steadyhand"` (Shyden 2026-10-01). `/color` has no documented automatic route; Shyden types it.

## Research technique
- **Shyden's decision (2026-09-25): use another source before idx.co.id.** IDX's Terms of Use forbid scraping. Try the Internet Archive, KSEI, KPEI (idclear) or BPK first. Use idx.co.id only when none has a readable copy, and say so in the research doc.
- **Internet Archive:** use the CDX API (`web.archive.org/cdx/search/cdx`, `matchType=prefix` or `domain`, `filter=`, `collapse=urlkey`; pass `curl -g` when the filter has brackets), then `https://web.archive.org/web/<ts>id_/<original>`, spaced about 4 s apart. Some indexed captures 404 on replay, and some are **truncated at exactly 1 MiB**: check the PDF's EOF marker.
- **An IDX rule's cover decision can hold its own attachment back.** Read the cover's MEMUTUSKAN items and the revocation clause before quoting an attachment as in force.
- **BPK** serves curl: search with `peraturan.bpk.go.id/Search?keywords=…&nomor=…&tahun=…`, then `/Details/<id>` and its `/Download/…` PDF. Text PDFs: `uv run --no-project --with pypdf`.
- **Yahoo probes:** `uv run --no-project --with yfinance==1.7.0`. `history(raise_errors=…)` is deprecated in 1.7.0; set `yfinance.config.debug.hide_exceptions = False` instead.
- **Pages that refuse curl** (403, such as ajaib.co.id): read them in Chrome with `browser_batch` (`navigate` + `get_page_text`).
- Cloudflare sometimes shows a "verify you are human" box. Never click it; ask Shyden.

## Notes
- This is a personal project: not Shyden Labs, and not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM project 1**, node `PVT_kwHOCQ_jzM4BkhEb`. Assert the title "steadyhand" before writing to it (`gh project view 1 --owner ShydenMcM --format json`). `gh project` calls run on the operator's login, while agent `gh api` calls run as the App, which cannot see this user-owned board, so an issue's `projectItems` reads empty. Get a card's id from `gh project item-add 1 --owner ShydenMcM --url … --format json --jq .id`, which is idempotent for an existing card. Status field `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk`: Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`.
- Agent git and gh act as the `steadyhand-agent` App (administration: read). An admin write is Shyden's decision.
- The `python3` on this machine is Xcode's 3.9, which has no `tomllib` and no `X | Y` in `isinstance`. The code uses uv's Python 3.12 and 3.13, and uv is pinned to 0.12.18.
- **zsh:** an unquoted `$VAR` holding a command does not split into words; write `${=VAR}`. And a pytest status read through `| tail` is `tail`'s: capture `rc=$?` with no pipe in between.
- **Never re-run a failed job to make it pass** (Shyden's rule, 2026-10-02; #179). A TestPyPI publish failure is read and named: if the cause is ours, fix it; if it is outside our control (an OIDC or TLS timeout), report it to Shyden by name with the run id, and do not re-run.
- **Mutation tallies:** print the full `FAILED` ids, not `sort -u` of names, because parametrised cases collapse into one name.
- **Timestamps:** stamp status lines only from a `date -u` read.
- **macOS has no `tac`** (use `tail -r`). A `$(tac …)` that fails leaves an empty list, and `git switch -C` then resets the branch with nothing to pick: check the list is non-empty before any reset. Recovered from the reflog on 2026-09-27.
