# Handover: steadyhand

**Updated:** 2026-09-25 16:05 UTC (the M2 plan is written, reviewed to zero and approved; its PR is open; no M2 code is merged yet)
**Local:** `~/Developer/Repos/steadyhand`, on `plan/m2-idx-rules-and-data`. Read SHAs with `git rev-parse` and never retype one. `main` has no release yet.
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M1 and all research are complete** (#24–#27, #37, #38, #41).
- **The M2 plan:** `docs/superpowers/plans/2026-09-25-m2-idx-rules-and-data.md`, plan ticket **#43** (In Progress). Stories **S1 #44, S2 #45, S3 #46, S4 #47, S5 #48, S6 #49 and S7 #50** are filed with their acceptance criteria and are on the board as Todo, each read back through its item node.
- **How the plan was verified.** Every code block in it was generated from a scratch tree built test-first. Replaying the plan from its own text (Task 1 on develop, each later task on the previous story's tree) rebuilt all seven story trees byte-identically, with every red and green count reproduced: 319, 387, 418, 453, 485, 501 and 521 tests at 100% branch coverage. 18 mutations were run inside each story's own tree, plus one live mutation, and all were caught. pip-audit is clean. The plan's review log records passes 1–4; pass 4 found nothing, so the plan is approved.
- **The plan PR** carries the plan, spec pass 14 (§3.6, §4.1, §4.3, §5.1, §9.1, §9.2, §9.4, §13), `docs/research/t-rules.md` §7 (T+2 from POJK 21/POJK.04/2018) and this file. It needs Shyden's merge approval (below).
- **Decisions made in the plan** (scope decisions 1–12): stamp duty through a new `MarketRules.daily_costs`; `verified_from` and `require_supported` on the protocol, the date derived as 2021-01-01 from `fees.toml [stamp_duty]`; T+2 as data from 26 Nov 2018; only the `ajaib` and `custom` presets; `sessions.toml` deferred to M5; the impossible-data check in M3; Yahoo's split reversal and the refusal of unrecoverable days; a user-supplied `exclusions.csv`; `universe.py` in M2.
- **Found while planning, measured 2026-09-25:** Yahoo folds rights issues into its prices without reporting them. Across 25 large IDX stocks in 2021–2025, BBRI's prices to 2021-09-07, SMGR's to 2022-12-12, MDKA's to 2022-04-13 and five INCO days in June 2024 cannot be recovered. Those three are LQ45 members inside §14 AC1's window, so M3 must choose a policy (the plan's "Carried forward").
- **Merging:** each agent merge needs Shyden's go-ahead in the session, through `AskUserQuestion` naming the PR, its head SHA read from a file in that same turn, and the CI state. Pin the merge with `--match-head-commit "$(cat <file>)"`.

## Resume steps
1. **Merge the plan PR** once CI is green and Shyden approves (see "Merging" above). The develop run afterwards must pass every job by name, `publish-dev` included. Then close #43 with a comment linking the PR and the run, and move its card to Done, reading it back through `PVTI_lAHOCQ_jzM4BkhEbzg8yfyM`.
2. **Implement S1 (#44)** from the plan's Task 1, then S2–S7 in order, one branch and PR per story, as each task's steps say. Every block is marked `<!-- file: … -->`, `<!-- file@N: … -->` or `<!-- stub: … -->`, so a task's files can be extracted from the plan by script rather than retyped. Run each story's red step before its implementation, and its mutations after.
3. Execution method: the plan recommends a choice at hand-off (subagent-driven or native); ask Shyden if he has not chosen.

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
