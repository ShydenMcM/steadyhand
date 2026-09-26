# Handover: steadyhand

**Updated:** 2026-09-26 07:38 UTC (**M3 spec approved; the M3a plan is next.** M2 is complete, and so is its develop deploy.)
**Local:** `~/Developer/Repos/steadyhand`, on branch **`m3/spec`**, pushed. Its head is read with `git rev-parse m3/spec`, never retyped. It holds the spec (2 commits) and this handover (committed with it). `develop` is at `430b4d5`. `main` has no release yet.
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M3 spec:** `docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md`, approved by Shyden on 2026-09-26 (review loop closed on pass 3). His four decisions are in §2: a pure core (`run_day(state, inputs) -> (state, report)`); rights-issue days refused by Yahoo are skipped, so the stock can't be traded and, if held, is frozen at its last clean close; a start before the universe's first list is refused, naming the first covered date; a kill switch halts the backtest for the rest of the run. He also approved the seven further calls listed in the spec (missing bars over history skip the day with a warning; buy-and-hold fixes its set and never sells; a unit value drives the kill switches; a split cancels pending orders; golden settings allow 25% per stock and the performance test uses a fixed-rules test market; `survivorship_warnings` loses its before-first-list branch; the pay-date override moves to M5 and pre-start history to M6).
- **Delivery (spec §1.2, §10):** one spec, two plans. **M3a** covers stories 1-6 (engine additions plus the disclaimer guard for `docs/`; MarketView and buy-and-hold; SimulatedBroker; sizer, risk and unit value; corporate actions; run_day). **M3b** covers stories 7-10 (backtest; metrics; golden and truncation tests; performance).
- **Ticket:** #61 "M3 plans: engine day (M3a) and backtester (M3b)", on board project 1 (title read back "steadyhand"), **In Progress**. Its ACs cover both plans, the stories filed before code, and the PR from `m3/spec`.
- **M2 facts still needed:** develop's suite is **522 passed, 4 deselected** at 100% (S7's gate). The plan tools `extract.py` and `mutate.py` are in the git-ignored `.superpowers/sdd/2026-09-25-m2-idx-rules-and-data/` and can be reused for M3.
- **Execution method (Shyden, 2026-09-25):** native, in a fresh session, one branch and PR per story, with Shyden's merge approval on each. No subagents.
- **Merging:** each agent merge needs Shyden's go-ahead in the session, through `AskUserQuestion` naming the PR, its head SHA read from a file in that same turn, and the CI state. Pin the merge with `--match-head-commit "$(cat <file>)"`.
- **publish-dev never runs on a PR.** A story that adds a runtime dependency runs the verify install locally first. M3 is standard-library only (spec §3.2), so none should.

## Resume steps
1. `git switch m3/spec && git pull`. Read the M3 spec in full (under 200 lines), then the M2 plan's layout and its first task (`docs/superpowers/plans/2026-09-25-m2-idx-rules-and-data.md`) as the house format for a plan.
2. Invoke `superpowers:writing-plans` for **M3a**, saved to `docs/superpowers/plans/2026-09-26-m3a-engine-day.md`. Verify the code by extraction, as M2 was: assemble every block into a scratch worktree off `m3/spec`, run the stubbed red run, the gate (ruff, format, mypy, pytest at 100% branch coverage) and every mutation over the whole suite. Log each review pass in the plan until one finds nothing, then self-approve.
3. File stories 1-6 on the board (project 1; assert the title "steadyhand"; read back the `PVTI_` node) with each task's ACs. Then open the PR from `m3/spec` to `develop` with "Refs #61", and ask Shyden to merge.
4. Implement M3a stories natively in order, then plan M3b the same way.
5. Clear the session at each story boundary once the handover is updated.

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
- **Mutation tallies:** print the full `FAILED` ids, not `sort -u` of names, because parametrised cases collapse into one name.
- **Timestamps:** stamp status lines only from a `date -u` read.
