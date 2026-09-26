# Handover: steadyhand

**Updated:** 2026-09-26 09:12 UTC (**The M3a plan is written, reviewed to zero and approved; stories #62–#67 are filed. Next: merge the `m3/spec` PR, then implement S1.**)
**Local:** `~/Developer/Repos/steadyhand`, on branch **`m3/spec`**, pushed. Read its head with `git rev-parse m3/spec`; never retype it. It holds the M3 spec, the M3a plan and this handover. `develop` is at `430b4d5`. `main` has no release yet.
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M3 spec:** `docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md`, approved by Shyden on 2026-09-26.
- **M3a plan:** `docs/superpowers/plans/2026-09-26-m3a-engine-day.md` (about 6,400 lines), approved after review pass 2 found nothing. Tasks 1–6 are stories S1–S6. Every code block was rendered from six verified story trees (each green on CI's exact gate at 100% branch coverage with the `ci` hypothesis profile) and replayed from the plan's own text, byte-identical. Suite totals by story: 555, 588, 620, 652, 667, 690 (plus 4 deselected `live` tests). Read the plan's **Scope decisions** first: in particular (1) `Portfolio.spendable_cash` and stamp duty netted with the day's trades, and (3) the strategy protocol's `decide(view, portfolio, memory)`.
- **Stories:** #62 S1, #63 S2, #64 S3, #65 S4, #66 S5, #67 S6, all on board project 1 ("steadyhand"), **Todo**, read back through their `PVTI_` nodes. Each body is its task's acceptance criteria and says `Refs #61`.
- **Ticket #61** (M3 plans), In Progress. Its M3a criteria are met by the plan; its M3b criteria wait for the M3b plan.
- **Execution method (Shyden, 2026-09-25):** native, in a fresh session, one branch and PR per story, with Shyden's merge approval on each. No subagents.
- **Merging:** each agent merge needs Shyden's go-ahead in the session, through `AskUserQuestion` naming the PR, its head SHA read from a file in that same turn, and the CI state. Pin the merge with `--match-head-commit "$(cat <file>)"`.
- **Plan tools** (git-ignored, reusable for M3b): `.superpowers/sdd/2026-09-26-m3a-engine-day/`. `stubgen.py` makes a file's red form (new functions raise `NotImplementedError`, existing ones keep their old bodies); `redrun.py` runs a story's red phase; `gates.py` runs CI's gate per story commit; `mutations.py` holds the 33 mutations with predictions and runs them; `render.py` turns `template.md` + `tasks2to6.md` (via `fill.py`) into the plan from story commits; `check_plan.py` replays a plan from its text. Run them with `uv run --no-project --python 3.12 python` (the system `python3` is 3.9). The scratch story commits they were run on lived in this session's scratchpad and are gone; the plan itself is now the source.

## Resume steps
1. `git switch m3/spec && git pull`. Find the open PR from `m3/spec` into `develop` (`gh pr list --head m3/spec`). If it is not merged, read its head into a file, check its CI run by that SHA (every job by name), and ask Shyden to merge it as the plan's **Merging a story** says. After the merge, confirm the develop run (read `publish-dev` by name).
2. Implement **S1 (#62)** natively from the plan's Task 1: branch `m3/s1-engine-additions` off `origin/develop`; write the tests and stubs exactly as given; run the whole suite and expect **555 run, 30 failed** as its Step 4 says; implement; run the gate (555 passed, 100%); run mutations M1–M6 (the plan's **Planted exactly** block), each red with the total unchanged; open the PR with `Refs #62` and the red-phase record; ask Shyden to merge.
3. Continue S2–S6 in order, one story per session where the context grows; clear at each story boundary once this file is updated.
4. After S6, plan **M3b** (stories 7–10) the same way: build and verify the code in a scratch worktree off `develop`, render it with the tools above, replay it, review it to zero, file its stories, and move #61 to Done when both plans are merged.

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
- The `python3` on this machine is Xcode's 3.9, which has no `tomllib` and no `X | Y` in `isinstance`. The code uses uv's Python 3.12 and 3.13, and uv is pinned to 0.12.18.
- **zsh:** an unquoted `$VAR` holding a command does not split into words; write `${=VAR}`. And a pytest status read through `| tail` is `tail`'s: in an `&&` chain it let a red test be committed this session (caught, fixed before anything was pushed).
- **A TestPyPI publish failure is not always ours.** An OIDC or TLS timeout goes away with `gh run rerun <id> --failed`, and `skip-existing` makes that safe.
- **Mutation tallies:** print the full `FAILED` ids, not `sort -u` of names, because parametrised cases collapse into one name.
- **Timestamps:** stamp status lines only from a `date -u` read.
