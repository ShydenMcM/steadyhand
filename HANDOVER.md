# Handover: steadyhand

**Updated:** 2026-09-25 22:09 UTC (S1 #44 is implemented on `m2/s1-calendar` and goes to develop through its PR; S2 is next)
**Local:** `~/Developer/Repos/steadyhand`. Read SHAs with `git rev-parse` and never retype one. `main` has no release yet.
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M1, all research and the M2 plan are complete.** The plan is `docs/superpowers/plans/2026-09-25-m2-idx-rules-and-data.md`, merged by PR #51 (squash `0958346`). Develop run 36194713689 passed all six jobs by name, publish-dev included. Plan ticket #43 is closed with an AC-by-AC comment, and its card is Done (read back through its item node).
- **Stories:** S1 #44 (implemented, PR into develop), S2 #45, S3 #46, S4 #47, S5 #48, S6 #49, S7 #50 (Todo). Each body is the plan task's acceptance criteria.
- **S1 as run (2026-09-25):** red `63 failed`, all `NotImplementedError`; gate `319 passed` at 100%; M17 caught by `test_a_dropped_holiday_fails_the_arithmetic_check`. M18 is caught by **one** test in S1's tree, not the table's six: the other five consume `Dated` in S2–S4, so re-run M18 in S4's tree to see all six. Self-review minors, left as they are: `require_schema` accepts `schema = true` or `1.0` (both `== 1`), and `get_decimal` accepts `"-0"` and `"1_0"`.
- **Tools kept on disk** in the git-ignored `.superpowers/sdd/2026-09-25-m2-idx-rules-and-data/`: `extract.py PLAN START END` writes every marked block in a line range (use one range per step, because a stub and its implementation share a path); `mutate.py FILE OLD NEW` plants a mutation and fails closed unless the anchor matches exactly once. `progress.md` there is the plan ledger. Anchor mutations on the real indentation (M17's check is at 4 spaces, not 8).
- **Execution method (Shyden, 2026-09-25): native, in a fresh session.** Implement the stories yourself from the plan, in order, one branch and PR per story, with Shyden's merge approval on each. No subagents.
- **The plan's code is already verified.** Every block was generated from a tree built test-first, and replaying the plan from its own text rebuilt all seven story trees byte-identically. The red counts reproduced (63, 68, 31, 35+5, 30+2, 4+12, 16+4), and so did the green counts (319, 387, 418, 453, 485, 501, 521 at 100% branch coverage). 18 mutations were run inside their owning stories' trees, plus 1 live one, and all were caught.
- **Found while planning:** Yahoo folds rights issues into its prices without reporting them (BBRI to 2021-09-07, SMGR to 2022-12-12, MDKA to 2022-04-13, five INCO days in June 2024). The Yahoo source refuses those days. M3 must choose a policy (see the plan's "Carried forward").
- **Merging:** each agent merge needs Shyden's go-ahead in the session, through `AskUserQuestion` naming the PR, its head SHA read from a file in that same turn, and the CI state. Pin the merge with `--match-head-commit "$(cat <file>)"`.

## Resume steps
1. **Confirm S1 landed:** #44 closed, its card Done (read back through `PVTI_lAHOCQ_jzM4BkhEbzg8yf2c`), and the develop run for the merge commit green by job name, `publish-dev` included. If any of that is missing, finish it first, following the plan's **Merging a story**.
2. **S2 (#45), the plan's Task 2 (line 1529 on).** Card to In Progress and read it back. `git switch -c m2/s2-ticks-bands origin/develop`. Extract each step's blocks with `extract.py` using that step's line range, never by retyping. Follow the steps in order: tests, stubs, the red run (the plan's Expected), the implementation, the gate (expect `387 passed`, 100%), the story's mutations, commit, merge, deploy check, close.
3. Then S3–S7 the same way, each from `origin/develop` after the previous story merges. S5 has extra steps: its `uv add` commands, recording the three fixtures, and one live test run.
3. Clear the session at each story boundary once the handover is updated.

## Research technique
- **Shyden's decision (2026-09-25): use another source before idx.co.id.** IDX's Terms of Use forbid scraping. Try the Internet Archive, KSEI, KPEI (idclear) or BPK first. Use idx.co.id only when none has a readable copy, and say so in the research doc.
- **Internet Archive:** use the CDX API (`web.archive.org/cdx/search/cdx`, `matchType=prefix` or `domain`, `filter=`, `collapse=urlkey`; pass `curl -g` when the filter has brackets), then `https://web.archive.org/web/<ts>id_/<original>`, spaced about 4 s apart. Some indexed captures 404 on replay, and some are **truncated at exactly 1 MiB**: check the PDF's EOF marker.
- **An IDX rule's cover decision can hold its own attachment back.** Read the cover's MEMUTUSKAN items and the revocation clause before quoting an attachment as in force.
- **BPK** serves curl: search with `peraturan.bpk.go.id/Search?keywords=…&nomor=…&tahun=…`, then `/Details/<id>` and its `/Download/…` PDF. Text PDFs: `uv run --no-project --with pypdf`.
- **Yahoo probes:** `uv run --no-project --with yfinance==1.7.0`. `history(raise_errors=…)` is deprecated in 1.7.0; set `yfinance.config.debug.hide_exceptions = False` instead.
- **Pages that refuse curl** (403, such as ajaib.co.id): read them in Chrome with `browser_batch` (`navigate` + `get_page_text`).
- Cloudflare sometimes shows a "verify you are human" box. Never click it; ask Shyden.

## Notes
- This is a personal project: not Shyden Ltd, and not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM project 1**, node `PVT_kwHOCQ_jzM4BkhEb`. Assert the title "steadyhand" before writing to it. New issues do NOT auto-add: use `gh project item-add 1 --owner ShydenMcM --url … --format json`, then read the `PVTI_…` id back with `gh api graphql` `node(id:){... on ProjectV2Item{project{title} fieldValueByName(name:"Status"){...}}}`. **Not `gh project item-list`**, which lags. Status field `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk`: Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`.
- Agent git and gh act as the `steadyhand-agent` App (administration: read). An admin write is Shyden's decision.
- The `python3` on this machine is Xcode's 3.9, which has no `tomllib`. The code uses uv's Python 3.12 and 3.13, and uv is pinned to 0.12.18.
- **A TestPyPI publish failure is not always ours.** An OIDC or TLS timeout goes away with `gh run rerun <id> --failed`, and `skip-existing` makes that safe.
- **Timestamps:** stamp status lines only from a `date -u` read.
