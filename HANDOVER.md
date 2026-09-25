# Handover: steadyhand

**Updated:** 2026-09-25 14:32 UTC (T-VERIFY #41 researched and pushed; its PR is next; the M2 plan has not started)
**Local:** `~/Developer/Repos/steadyhand`, on branch `research/41-t-verify`, pushed. Read its head with `git rev-parse origin/research/41-t-verify`, never retype it. `develop` is at the #40 merge. `main` has no release yet.
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M1 is complete.** Research #24 T-RULES, #25 T-TAX, #26 T-LQ45, #27 T-PAY, #37 T-HIST and #38 T-FEES are merged and closed.
- **Shyden's decision (2026-09-25): a backtest refuses any date whose rule or fee rows are not primary-verified.** No `verified = false` rows ship. He chose to research the gaps first (#41, T-VERIFY), falling back to a later start date if they stayed open.
- **#41 T-VERIFY** is on the steadyhand board as In Progress, committed on `research/41-t-verify` with this handover. Findings, in `docs/research/t-verify.md`, reviewed in four passes to zero:
  - KSEI 0.003% is verified from FY2019. KPEI's 0.005% guarantee-fund cut ran 18 Jun – 17 Dec 2020, which corrects T-FEES's 16 Dec.
  - **The reference price has been the previous close since 7 Sep 2020** (Kep-00063, then the interim clauses in every II-A cover decision until Kep-00196). T-RULES and T-HIST read the attachments' opening price, and are corrected.
  - The stamp-duty Rp10M threshold is PP 3/2022's exemption from 12 Jan 2022. Before that, every confirmation was dutiable from 1 Jan 2021. **Stamp duty before 2021 is unverified, so the earliest verified date is 2021-01-01.** Spec §14 AC1 now starts there, and §9.1 derives the refusal date from the data files.
  - `t-fees.md`, `t-hist.md`, `t-rules.md` and the spec (Passes 12 and 13) carry the corrections.
- **Merging:** each agent merge needs Shyden's go-ahead in the session, through `AskUserQuestion` naming the PR, its head SHA and CI state. Pin the merge with `--match-head-commit`.

## Resume steps
1. **Finish #41.** Open the PR from `research/41-t-verify` to `develop` with `Refs #41` (never a closing keyword). Wait for CI, ask Shyden to merge, then verify the develop run's six jobs by name (publish-dev included), comment the findings on #41, close it, and move its board item to Done (item `PVTI_lAHOCQ_jzM4BkhEbzg8xE38`, read back through its node).
2. **The M2 plan.** Use `superpowers:writing-plans` from spec §13 and the seven research docs (`docs/research/t-*.md`). The plan is reviewed on a loop to zero findings, then self-approved (global rule), and it needs a story ticket on the steadyhand board with full AC before implementation.
   - **Ask Shyden first** (`t-verify.md` §5 item 1): does stamp duty from 1 Jan 2021 to the broker's collection start charge what the law imposed (every confirmation until 11 Jan 2022, then over Rp10M), or what brokers actually debited (unverified)? The strict rule points to the law, but for small accounts the gap is about 0.2% per trading day.
   - **Take in the plan:** the per-day stamp duty against §4.3's per-trade `costs()` (`t-verify.md` §5 item 2); the refusal date derived from the data files (spec §9.1); the "impossible data" check using the previous close from 7 Sep 2020, with the IPO and corporate-action exceptions (`t-verify.md` §4.2); Yahoo's flat zero-volume bars and its adjusted prices (`t-hist.md` §6 items 3–4); no LQ45 PDF importer; the §8 "another universe" key deferred to M5; whether `stockbit` and `ipot` ship with an assumed `includes` list (`t-fees.md` §6 item 2).
   - M2 scope: `rules.py` and the data files, `calendar.py`, `fees.toml` and the fees task, the Yahoo source, the cache, fixtures, and probably `universe.py` (no milestone names it; say so in the plan).

## Research technique
- **Shyden's decision (2026-09-25): use another source before idx.co.id.** IDX's Terms of Use forbid scraping. Try the Internet Archive, KSEI, KPEI (idclear) or BPK first. Use idx.co.id only when none has a readable copy, and say so in the research doc.
- **Internet Archive:** use the CDX API (`web.archive.org/cdx/search/cdx`, `matchType=prefix` or `domain`, `filter=`, `collapse=urlkey`; pass `curl -g` when the filter has brackets), then `https://web.archive.org/web/<ts>id_/<original>`, spaced about 4 s apart. Some indexed captures 404 on replay, and some are **truncated at exactly 1 MiB**: check the PDF's EOF marker.
- **An IDX rule's cover decision can hold its own attachment back.** Kep-00108, Kep-00061 and Kep-00055 each print the opening price in the II-A attachment and, in the cover's numbered items, say that clause *"belum diberlakukan"* and set an interim rule. Read the cover's MEMUTUSKAN items and the revocation clause (*"dicabut dan dinyatakan tidak berlaku"*) before quoting an attachment as in force. Each II-A's revocation clause names its predecessor, which is how the chain of versions is proved.
- **IDX's rules pages render their list server-side** (`window.__NUXT__`: `NumberOfDecree`, `Description`, `Attachment`), so Archive captures of `www.idx.co.id/id/peraturan/peraturan-bei/` show which II-A was in force on the capture date. The pages list only decisions still in force. An `id_` replay may come back gzip-compressed: use `curl --compressed`, or `gunzip -c`.
- **KSEI and KPEI annual reports:** KSEI's are listed at `web.ksei.co.id/annual-reports` (2014–2025). KPEI's sit under `assets-website.idclear.co.id/idclear/storage/<n>/`: dump the CDX prefix and grep it, because a regex CDX filter returned nothing where the known 2019 file existed. The audited notes state each SRO's own fee rates and decision dates.
- **Stamp-duty law:** UU 10/2020, PMK 151/2021 and PP 3/2022 (the Rp10M exemption) are on BPK. BPK's search takes `?keywords=` plus `nomor=` and `tahun=`.
- **SRO annual reports state fee rates** in their revenue notes: IDX AR 2017 (0.018%), KPEI AR 2019 (0.009%, fund 0.01%). Useful for dating a rate when the rule text is missing.
- **idx.co.id (fallback only):** in Chrome through `browser_batch`. Parse PDFs in the page with `pdfjs-dist@4.10.38` from cdn.jsdelivr; output is capped at about 1,000 characters per call.
- **Pages that refuse curl** (403, such as ajaib.co.id): read them in Chrome with `browser_batch` (`navigate` + `get_page_text`).
- **Scanned PDFs:** render them with `uv run --no-project --with pypdfium2 --with pillow` and read the image. Text PDFs: `uv run --no-project --with pypdf`.
- **KSEI, KPEI and BPK serve curl** (KSEI needs `-A "Mozilla/5.0"`). ojk.go.id does not.
- Cloudflare sometimes shows a "verify you are human" box. Never click it; ask Shyden.

## Notes
- This is a personal project: not Shyden Ltd, and not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM project 1**, node `PVT_kwHOCQ_jzM4BkhEb`. Assert the title "steadyhand" before writing to it. New issues do NOT auto-add: use `gh project item-add 1 --owner ShydenMcM --url …`, then read the `PVTI_…` id it returns (`--format json`) with `gh api graphql` `node(id:){... on ProjectV2Item{project{title} fieldValueByName(name:"Status"){...}}}`. **Not `gh project item-list`:** on 2026-09-25 it lagged behind the add and listed 17 items without #41 while the item existed. Status field `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk`: Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`.
- Agent git and gh act as the `steadyhand-agent` App (administration: read). An admin write is Shyden's decision.
- The `python3` on this machine is Xcode's 3.9, which has no `tomllib`. The code uses uv's Python 3.12 and 3.13, and uv is pinned to 0.12.18.
- **A TestPyPI publish failure is not always ours.** An OIDC or TLS timeout goes away with `gh run rerun <id> --failed`, and `skip-existing` makes that safe.
- **Timestamps:** stamp status lines only from a `date -u` read.
