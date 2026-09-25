# Handover: steadyhand

**Updated:** 2026-09-25 07:45 UTC (all four research tickets done and deployed; the M2 plan is next)
**Local:** `~/Developer/Repos/steadyhand`, on `develop`. Read `develop` with `git rev-parse origin/develop` and never retype it. `main` is at `a3eb88f` (no release yet).
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M1 Foundations is complete.** S1–S8 and #21 are merged. See git history.
- **Research tickets are all DONE:** #24 T-RULES, #25 T-TAX, #27 T-PAY and #26 T-LQ45. Each has `docs/research/t-*.md` and a spec review pass (6 to 9).
- **#26 T-LQ45 is merged:** PR #35 was squash-merged as `014f7ec` (full SHA `014f7ec861c16b67828a13cde8d602a695d0db02`), and #26 is closed. Checks were green on head `9a32b4e` before the merge. The develop deploy, run 36108411710 on the matching SHA, had all six jobs `success` by name, with publish-dev's TestPyPI install check included. Output: `docs/research/t-lq45.md`, reviewed to zero in 6 passes, plus spec Pass 9.
  - **Sources:** IDX review announcements (on idx.co.id from 2024), plus Internet Archive copies of IDX's 2004–2018 announcements and its 2013–2025 LQ45 fact-sheet booklets.
  - **Coverage:** the earliest list found is Feb–Jul 2004. For 2016–2025, 19 of 24 reviews have a primary list. The gaps are Feb 2019, Feb and Aug 2021, Aug 2022 and Feb 2023. Reviews are quarterly from May 2024.
  - **Format:** `lq45_members.toml`, one record per IDX document with the full 45 codes.
  - **Licensing:** IDX's Terms of Use bar commercial redistribution and scraping, so the file is user-supplied, never shipped. Spec §9.4 and the `[universe] lq45_members` key in §9.5 reflect this.
- **Merging on green is Shyden's decision (2026-09-25), and the permission is his.** He added the allow rules himself to `.claude/settings.local.json`: `Bash(gh pr merge:*)`, `Bash(gh run list:*)`, `Bash(gh run view:*)` and `Edit(HANDOVER.md)`. That file is personal and ignored by his global git ignore, so it is not in the repo. PRs #34 and #35 merged under them. The agent cannot add or widen these rules; the auto-mode classifier refuses that as Self-Modification.

## Resume steps
1. **Merges:** before any merge, read `.claude/settings.local.json`. If the rules above are missing, stop and ask Shyden. Merge only when the checks are green on the head SHA from `gh pr view --json headRefOid`, with `gh pr merge --match-head-commit <that SHA>`. Then find the develop run with `gh run list --branch develop --json databaseId,headSha,status,conclusion`, match the SHA yourself, and read every job BY NAME (publish-dev included).
2. **The M2 plan:** use `superpowers:writing-plans`. Read the spec's §13 for M2's scope and the four research docs for its data. Review the plan to zero, then self-approve it.
3. **Open for the M2 plan, not decided:**
   - §8 says the universe is the LQ45 "unless the operator configures otherwise", but no config key exists for another universe (recorded in spec Pass 9).
   - The M2 plan decides whether `steadyhand-idx` gets a local importer for PDFs the user saved (never a downloader; `t-lq45.md` §5).

## Research technique
- **Shyden's decision (2026-09-25): use another source before idx.co.id.** IDX's Terms of Use forbid "web scrapping/crawling". Try the Internet Archive, KSEI or BPK first. Use the idx.co.id browser technique below only when no other source has the document, and say in the research doc which documents came that way.
- **Internet Archive:** `curl -G https://web.archive.org/cdx/search/cdx --data-urlencode "url=idx.co.id" --data-urlencode "matchType=domain" --data-urlencode "filter=original:.*lq45.*" --data-urlencode "filter=mimetype:application/pdf" --data-urlencode "collapse=urlkey" --data-urlencode "fl=timestamp,original"`. Download raw files from `https://web.archive.org/web/<ts>id_/<original>`. Space the downloads about 4 s apart: a burst of 57 lost 32 to throttling.
- **Scanned PDFs:** `scratchpad/lq45/ocr.swift` (macOS Vision; `swiftc -O -o ocr ocr.swift`) reads them, and needs no installs. It is session scratch, so rewrite it if the scratchpad is gone. The OCR reads Latin capitals as Cyrillic look-alikes and misreads about 2 codes per 45 while keeping the count at 45. Never trust a count; cross-check against a second source.
- **KSEI** (web.ksei.co.id) serves plain `curl`. Dividend schedule letters are at `/Announcement/Files/{TICKER}_DIV_{recording YYYYMMDD}_ID.pdf`, and the recording date is ex + 1 trading day. The month/year filter on the list page returns HTTP 500. Extract text with `uv run --no-project --with pypdf` and `extraction_mode="layout"`.
- **idx.co.id (fallback only)** returns 403 to curl and WebFetch. In Chrome through `browser_batch`, open an idx.co.id page and `fetch('/primary/NewsAnnouncement/GetAllAnnouncement?keywords=…&pageNumber=1&pageSize=100&dateFrom=YYYYMMDD&dateTo=YYYYMMDD&lang=id')`. Its archive starts in **July 2023**. It returns JSON with `Attachments[].FullSavePath`; some attachments are `.zip` (unzip with `fflate@0.8.2` from cdn.jsdelivr). Parse PDFs with `pdfjs-dist@4.10.38`. Output is capped at about 1,000 characters per call, and `localStorage` keeps results across navigations within the site. PDF digits can come out spaced, so strip whitespace before matching dates.
- **Regulations:** peraturan.bpk.go.id `/Download/<id>/…pdf` serves curl. ojk.go.id does not.
- Cloudflare sometimes shows a "verify you are human" box. Never click it; ask Shyden.

## Notes
- This is a personal project: not Shyden Ltd, and not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM project 1**, node `PVT_kwHOCQ_jzM4BkhEb`. Assert the title "steadyhand" before writing to it. New issues do NOT auto-add; use `addProjectV2ItemById`.
- Agent git and gh act as the `steadyhand-agent` App (administration: read). An admin write is Shyden's decision.
- The `python3` on this machine is Xcode's 3.9, which has no `tomllib`. The code uses uv's Python 3.12 and 3.13, and uv is pinned to 0.12.18.
- **A TestPyPI publish failure is not always ours.** An OIDC or TLS timeout goes away with `gh run rerun <id> --failed`, and `skip-existing` makes that safe.
