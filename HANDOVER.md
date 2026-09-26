# Handover: steadyhand

**Updated:** 2026-09-26 06:47 UTC (S6 #49 merged by PR #59, `5eb9496`; develop run green on all six jobs, publish-dev included; #49 closed, card Done. S7 #50 implemented on `m2/s7-universe` and opened as a PR. Once it merges, M2 is complete.)
**Local:** `~/Developer/Repos/steadyhand`, on `m2/s7-universe` (S7's PR branch). This handover is committed on that branch. Read SHAs with `git rev-parse` and never retype one. `main` has no release yet.
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M1, all research and the M2 plan are complete.** The plan is `docs/superpowers/plans/2026-09-25-m2-idx-rules-and-data.md` (PR #51, squash `0958346`).
- **Stories:** S1 #44 to S5 #48 are Done, and so is bug #57. S6 #49 is Done. S7 #50 is In Progress (PR open). Each body is the plan task's acceptance criteria.
- **S1 as run:** red `63 failed`, gate `319 passed`. M18 was caught by **one** test in S1's tree; re-run M18 in S4's tree to see all six catchers.
- **S2 as run:** the plan puts S2's `.toml` data after its red run, so extract the data first. Red `68 failed`, gate `387 passed`. M1 and M2 were caught exactly on the edge cases; re-run both in S7's tree.
- **S3 as run (2026-09-26):** `data/fees.toml` was extracted before the red run. Red `31 failed`, all `NotImplementedError`; gate `418 passed` at 100%. The wheel carries all four data files, and `sessions.toml` is absent (the negative control). M4 was caught by 2 tests, M5 by 4 and M6 by 2. **M6's other listed catcher, `test_daily_costs_are_the_stamp_duty`, is S4's** (`tests/idx/test_rules.py`, plan line 3623): re-run M6 in S4's tree, next to M18. **Done in S4:** M6 caught 3 (that test included), M18 caught 6.
- **S3 departs from the plan text in one place.** Self-review found that `FeeSchedule.dividend_tax` accepted a USD or negative dividend. Commit `4e551d3` adds a shared `_require_rupiah` guard and folds the new assertions into the existing `test_gross_must_be_a_non_negative_rupiah_amount`, so **every later count in the plan still holds** (453, 485, 501, 521). No later task re-extracts `fees.py` (its only marker is plan line 2989), so replaying S4-S7 will not overwrite the fix.
- **S5 as run (2026-09-26):** red `30 failed, 2 passed` as the plan predicted; fixtures recorded 2026-09-26; gate `485 passed, 4 deselected` at 100%, audit clean, live `4 passed`. Mutations: M9 2, M10 1, M11 1, M16 1, M19 1 of 4 live. **M10's other catcher, `test_unrecoverable_prices_are_never_cached`, is S6's**: re-run M10 in S6's tree.
- **S6 as run (2026-09-26):** red `4 failed, 12 errors`, all `NotImplementedError`; gate `502 passed, 4 deselected` at 100%. Mutations over the whole suite, 502 every run: M10 2 (`never_cached` included), M12 1, M13 1, M14 2. **S6 departs from the plan in one place:** `test_missing_skips_stored_ranges_and_non_trading_gaps` held no hole made only of weekend days, so a narrow M14 (weekend-only holes fetched, trimming kept) passed it. Commit `fe4bfef` adds one assertion to that test (6-7 Nov 2021) without adding a test, so S7's count still holds. No later task re-extracts `test_cache.py`.
- **S7 as run (2026-09-26):** red `16 failed, 4 errors`, all `NotImplementedError`; gate `522 passed, 4 deselected` at 100%, and all four dists built. Mutations over the whole suite, 522 every run: M1 7, M2 5, M15 2, all as the table says.
- **#57 shifts every later gate count by one.** The fix added `test_the_testpypi_check_takes_every_dependency_from_pypi_first` to `tests/meta/test_supply_chain.py`, which the plan doesn't know about, so develop's suite is **486**. Expect S6's gate at **502** (plan says 501) and S7's at **522** (plan 521). Red counts run only the new files and are unchanged.
- **publish-dev never runs on a PR or in the plan replay.** A story that adds a runtime dependency or changes packaging runs the verify step's install locally against the live indexes before merging (`uv pip install -v`, and read which host served each wheel). S6 (SQLite, stdlib) and S7 add no dependency per the plan; check `uv add` in their steps anyway.
- **Tools kept on disk** in the git-ignored `.superpowers/sdd/2026-09-25-m2-idx-rules-and-data/`: `extract.py PLAN START END` writes every marked block in a line range (one range per step, because a stub and its implementation share a path); `mutate.py FILE OLD NEW` plants a mutation and fails closed unless the anchor matches exactly once. `progress.md` there is the plan ledger. An `<!-- excerpt: -->` block (S3's ci.yml step) is not extracted: apply it by hand.
- **Execution method (Shyden, 2026-09-25): native, in a fresh session.** Implement the stories yourself from the plan, in order, one branch and PR per story, with Shyden's merge approval on each. No subagents.
- **The plan's code is already verified**: replaying it rebuilt all seven story trees byte-identically, with red counts 63, 68, 31, 35+5, 30+2, 4+12, 16+4 and green counts 319, 387, 418, 453, 485, 501, 521 at 100% branch coverage.
- **Found while planning:** Yahoo folds rights issues into its prices without reporting them (BBRI to 2021-09-07, SMGR to 2022-12-12, MDKA to 2022-04-13, five INCO days in June 2024). The Yahoo source refuses those days. M3 must choose a policy (see the plan's "Carried forward").
- **Merging:** each agent merge needs Shyden's go-ahead in the session, through `AskUserQuestion` naming the PR, its head SHA read from a file in that same turn, and the CI state. Pin the merge with `--match-head-commit "$(cat <file>)"`.

## Resume steps
1. **S7's PR:** if not merged, wait for its CI (step 3) and ask Shyden to merge (see Merging). Then read develop's run job by job, close #50 with the AC to test mapping, and move card `PVTI_lAHOCQ_jzM4BkhEbzg8ygXA` to Done.
2. **M2 is then complete. M3 (the backtest) has no spec or plan yet.** Start with brainstorming, then a spec and a plan, each reviewed to zero. Feed in the plan's "Carried forward to later plans" section (line 7015): the rights-issue policy, the pre-LQ45 start, daily stamp-duty costs and the price-band check.
3. **CI waiters:** find a run with `gh run list --branch B --workflow ci` matched to the SHA read from a file, then poll `gh run view <id> --json status` until `completed`, and read every job by name. A merge also starts "Dependency Graph" runs on the same SHA.
4. Clear the session at each story boundary once the handover is updated.

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
