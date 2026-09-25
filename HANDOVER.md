# Handover: steadyhand

**Updated:** 2026-09-25 11:55 UTC (T-HIST merged and deployed; T-FEES research done and in a PR; the M2 plan is next)
**Local:** `~/Developer/Repos/steadyhand`, on branch `research/38-t-fees`. `origin/develop` is at `48e0dc2` (the #39 merge). Read SHAs with `git rev-parse`, never retype them. `main` is at `a3eb88f` (no release yet).
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M1 is complete.** Research tickets #24 T-RULES, #25 T-TAX, #26 T-LQ45, #27 T-PAY and #37 T-HIST are done and deployed.
- **#37 T-HIST: merged** as PR #39 (squash `48e0dc2`), on Shyden's explicit instruction in this session. Develop run 36129855580 on that SHA passed all six jobs by name (lint, test py3.12, test py3.13, audit, build, publish-dev). **Issue #37 may still be open**: check it and close it with a comment naming PR #39, as #26 was.
- **#38 T-FEES: research done**, on branch `research/38-t-fees`, in a PR to `develop` (see `gh pr list --head research/38-t-fees`). It holds `docs/research/t-fees.md` (reviewed to zero in 7 passes), spec §3, §5.1, §9.1, §12 and Appendix A, spec review Pass 11, and this handover.
  - Levy: IDX 0.018%, KPEI 0.009%, KSEI 0.003%, VAT on those three (10%, then 11% from 1 Apr 2022, and 12% × 11/12 from 2025, which is also 11%), and KPEI's 0.01% guarantee fund, which carries **no VAT**. That makes 0.043%, then 0.0433%. The fund was 0.005% from about 18 Jun to 16 Dec 2020 (**secondary** source only).
  - Unverified: IDX for 2018 – 12 Mar 2020, KPEI for 2016–2018, and KSEI before 20 Jan 2021 (the 2009 list says 0.006%; 0.003% is probable).
  - Sale tax: 0.1%, PP 41/1994 as amended by PP 14/1997, collected by the exchange.
  - **Stamp duty (new):** Rp10,000 per trade confirmation from 2021 (UU 10/2020). The Rp10 million daily threshold is broker practice only; no primary source was found.
  - Brokers: Ajaib 0.1513%/0.2513% all-in, stated. Stockbit 0.15%/0.25%. IPOT 0.19%/0.29% (as of Mar 2022). None publishes a minimum fee.
- **Merging:** the auto-mode classifier denied the agent's merge of #39 last session ("Merge Without Review"). With Shyden's explicit "merge it" in this session it went through. **Approval is per PR**: ask Shyden with `AskUserQuestion` before merging the T-FEES PR.

## Resume steps
1. **The T-FEES PR.** Read its head with `gh pr view <n> --json headRefOid,statusCheckRollup`, and wait for CI on that SHA, reading every job by name. When it is green, ask Shyden (`AskUserQuestion`) whether to merge. After the merge, find the develop run for the merge SHA with `gh run list --branch develop --json databaseId,headSha,status,conclusion` (match the SHA yourself), and read every job, publish-dev included. Then close #38 and #37 with a comment naming each PR (the PR bodies say `Refs`, so neither closes on merge).
2. **Then the M2 plan** (`superpowers:writing-plans`), from spec §13 and the six research docs. The plan is reviewed on a loop to zero findings, then self-approved (global rule). Decisions it must take, and which to ask Shyden about:
   - **Ask Shyden:** whether a backtest may run before 13 Mar 2020 on unverified rule rows, or must refuse (`t-hist.md` §6 item 1). One answer should also cover the unverified fee rows (`t-fees.md` §6 item 3).
   - **Take in the plan:** how the Yahoo source treats flat zero-volume bars, and how it un-adjusts prices (`t-hist.md` §6 items 3–4); the reference price over the 2023–2024 window (§6 item 2); whether an LQ45 PDF importer is built (the lean choice is no); the §8 "another universe" key (defer to M5's config); whether stamp duty ships in M2, given that §4.3's `costs(side, gross, on)` is per trade and stamp duty is per day (`t-fees.md` §6 item 1); and whether the `stockbit` and `ipot` presets ship with an assumed `includes` list (item 2).
   - M2 scope: `rules.py` and data files, `calendar.py`, `fees.toml` and the fees task, the Yahoo source, the cache, fixtures, and probably `universe.py` (no milestone names it; say so in the plan).

## Research technique
- **Shyden's decision (2026-09-25): use another source before idx.co.id.** IDX's Terms of Use forbid scraping. Try the Internet Archive, KSEI, KPEI (idclear) or BPK first. Use idx.co.id only when none has a readable copy, and say so in the research doc.
- **Internet Archive:** use the CDX API (`web.archive.org/cdx/search/cdx`, `matchType=prefix` or `domain`, `filter=`, `collapse=urlkey`; pass `curl -g` when the filter has brackets), then `https://web.archive.org/web/<ts>id_/<original>`, spaced about 4 s apart. Some indexed captures 404 on replay, and some are **truncated at exactly 1 MiB**: check the PDF's EOF marker.
- **SRO annual reports state fee rates** in their revenue notes: IDX AR 2017 (0.018%), KPEI AR 2019 (0.009%, fund 0.01%). Useful for dating a rate when the rule text is missing.
- **idx.co.id (fallback only):** in Chrome through `browser_batch`. Parse PDFs in the page with `pdfjs-dist@4.10.38` from cdn.jsdelivr; output is capped at about 1,000 characters per call.
- **Pages that refuse curl** (403, such as ajaib.co.id): read them in Chrome with `browser_batch` (`navigate` + `get_page_text`).
- **Scanned PDFs:** render them with `uv run --no-project --with pypdfium2 --with pillow` and read the image. Text PDFs: `uv run --no-project --with pypdf`.
- **KSEI, KPEI and BPK serve curl** (KSEI needs `-A "Mozilla/5.0"`). ojk.go.id does not.
- Cloudflare sometimes shows a "verify you are human" box. Never click it; ask Shyden.

## Notes
- This is a personal project: not Shyden Ltd, and not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM project 1**, node `PVT_kwHOCQ_jzM4BkhEb`. Assert the title "steadyhand" before writing to it. New issues do NOT auto-add: use `gh project item-add 1 --owner ShydenMcM --url …`, and read it back with `gh project item-list`.
- Agent git and gh act as the `steadyhand-agent` App (administration: read). An admin write is Shyden's decision.
- The `python3` on this machine is Xcode's 3.9, which has no `tomllib`. The code uses uv's Python 3.12 and 3.13, and uv is pinned to 0.12.18.
- **A TestPyPI publish failure is not always ours.** An OIDC or TLS timeout goes away with `gh run rerun <id> --failed`, and `skip-existing` makes that safe.
- **Timestamps:** stamp status lines only from a `date -u` read.
