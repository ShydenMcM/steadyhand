# Handover: steadyhand

**Updated:** 2026-09-26 15:33 UTC (**#84 is built, verified and in PR #85 (`perf/84-constant-time-ledger`), awaiting CI and Shyden's merge go-ahead. Then M4.**)
**Local:** `~/Developer/Repos/steadyhand`. On `perf/84-constant-time-ledger`; `develop` is at `b4d558d` (S10's squash merge). Read heads with `git rev-parse`; never retype one. `main` has no release yet.
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

## #84 constant-time ledger booking (PR #85, card In Progress)
- **Plan:** `docs/superpowers/plans/2026-09-26-constant-time-ledger.md`, reviewed to zero in three passes and self-approved. Scope decision 1 is the design note: `Portfolio.ledger` stays a `tuple`; internally a shared chain of two-slot tuples, materialised once per snapshot on first read.
- **Evidence:** story commit `e1e2ce2` (the PR's first commit; the plan commit sits on top). Red 746 run / 1 failed; gate 746 passed at 100%; M60–M66 all caught; replay byte-identical. One booking onto 100,000 movements: 1,700,232 bytes before, 648 after.
- **Build tooling** (git-ignored `.superpowers/sdd/2026-09-26-s11-ledger/`): scratch clone `repo/`, worktrees `mut/` and `replay/` (pass them to the tools as ABSOLUTE paths), `render.py` gains `@@rewrite N` (sources as edits from the base, no stubs). `gates.py` leaves `repo/` on a detached HEAD: re-point the branch before amending.

## Resume steps
1. **PR #85:** wait for CI on the PR head (read `headRefOid` into a file; match the run's `headSha`). Then ask Shyden to merge (`AskUserQuestion` naming the PR, the head SHA read from the file in that turn, and the CI state), and merge with `--match-head-commit`. After the develop deploy is green: record both `test` jobs' perf-step times on #84 against 20.85 s (py3.12) and 12.43 s (py3.13), which is criterion 5, close #84 with the criteria mapping, and move the card to Done.
2. **Then M4** (core spec §13): the income goal tracker and projection. It starts with a spec, not code.

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
