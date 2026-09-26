# Handover: steadyhand

**Updated:** 2026-09-26 12:06 UTC (**M3a is implemented: S1–S5 are merged and deployed, and S6 is the PR carrying this file. Next: finish S6's merge, then plan M3b.**)
**Local:** `~/Developer/Repos/steadyhand`. S6 is on branch **`m3/s6-run-day`** (PR "feat(engine): S6 run_day with validation", `Refs #67`). Read heads with `git rev-parse`; never retype one. `main` has no release yet.
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

  #62–#66 are closed, with evidence comments, and read Done on the board. #67 (S6) is In Progress until its PR merges and deploys.
- **S6 local evidence:** red phase 690 run / 23 failed (all `NotImplementedError`), gate 690 passed at 100% branch coverage (2,604 statements, 688 branches), and M29–M33 each red with the total unchanged, every catcher set as predicted.
- **Ticket #61** (M3 plans), In Progress. Its M3a criteria are met; its M3b criteria wait for the M3b plan.
- **Merging:** each agent merge needs Shyden's go-ahead in the session, through `AskUserQuestion` naming the PR, its head SHA read from a file in that same turn, and the CI state. Pin the merge with `--match-head-commit "$(cat <file>)"`.
- **Plan tools** (git-ignored, reusable for M3b): `.superpowers/sdd/2026-09-26-m3a-engine-day/`. `stubgen.py`, `redrun.py`, `gates.py`, `mutations.py`, `render.py`, `fill.py`, `check_plan.py`. Run them with `uv run --no-project --python 3.12 python`. **`mutations.py` now runs pytest under `HYPOTHESIS_PROFILE=ci`.** Under the default `dev` profile, M18's property-test catcher was missed; under `ci` it caught it in 3 of 3 runs. A plan's mutation table is a claim about CI's profile.
- **Applying a plan task by script:** `apply_task.py <plan> <tree> <task> red|green` (in the plan tools directory) applies a task's blocks up to or after its red marker. It stops if any edit anchor matches anything other than exactly once. It applied every M3a task.

## Resume steps
1. **Finish S6.** Find the open PR from `m3/s6-run-day` (`gh pr list --head m3/s6-run-day`). Read its head into a file and check its CI run by that SHA, every job by name. Ask Shyden to merge it, as the plan's **Merging a story** says. Then read the develop run's `publish-dev` by name, close #67 with its evidence and move its card to Done.
2. **Plan M3b** (stories 7–10 of the M3 spec's §10) the same way M3a was done. Build and verify the code in a scratch worktree off `develop`; render it with the plan tools; replay it with `check_plan.py`; review it to zero; file its stories on the board; and move #61 to Done when the M3b plan is merged. `survivorship_warnings` belongs to story 7 (M3a scope decision 12).
3. Execute M3b natively, one branch and PR per story, as M3a was.

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
