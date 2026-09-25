# Handover: steadyhand

**Updated:** 2026-09-25 07:05 UTC (T-PAY merged and its develop deploy verified; T-LQ45 is next)
**Local:** `~/Developer/Repos/steadyhand`, on `develop`. Read `develop` with `git rev-parse origin/develop` and never retype it. `main` is at `a3eb88f` (no release yet).
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M1 Foundations is complete.** S1–S8 and #21 are merged. See git history.
- **Research tickets:** #24 T-RULES, #25 T-TAX and #27 T-PAY are DONE. #26 T-LQ45 is open.
- **#27 T-PAY is merged:** PR #33 was squash-merged as `caebeeb` (full SHA `caebeeb333c3db5a78d99b2831ada12816fefa20`), and #27 is closed. All PR checks were green on head `57f0b12` before the merge: lint, test py3.12 and py3.13, audit, build (publish-dev skipped on the PR). Output: `docs/research/t-pay.md`, reviewed to zero in 4 passes, plus spec review Pass 8. Headlines: the default pay lag is **14** IDX trading days (the 90th percentile of 47 KSEI-scheduled dividends; median 12); POJK 15/2020 Pasal 58 sets a 30-day payment cap; Yahoo gives ex dates only; the tax reinvestment deadline is dated from the **ex date's year**; the 2025 IDX holidays are now verified; and `^JKSE` has a missing bar on 22 Sep 2026.
- **The develop deploy for `caebeeb` is verified:** run 36103175157 (`ci`, push) on the matching full SHA. All six jobs `success`, read by name: lint, test (py3.12), test (py3.13), audit, build, publish-dev (its "Verify both packages install from TestPyPI" step included).
- **Merging on green is Shyden's decision (2026-09-25), and the permission is his.** Shyden added the allow rules himself to `.claude/settings.local.json`: `Bash(gh pr merge:*)`, `Bash(gh run list:*)`, `Bash(gh run view:*)` and `Edit(HANDOVER.md)`. That file is personal and ignored by his global git ignore, so it is not in the repo. The agent cannot add or widen these rules; the auto-mode classifier refuses that as Self-Modification.

## Resume steps
1. Before any merge, read `.claude/settings.local.json`. If the rules above are missing, stop and ask Shyden. Merge only when the checks are green on the head SHA from `gh pr view --json headRefOid`. Then find the develop run with `gh run list --branch develop --json databaseId,headSha,status,conclusion`, match the SHA yourself, and read every job BY NAME (publish-dev included).
2. T-LQ45 (#26): `gh issue view 26` for the ACs, then branch `research/26-t-lq45` from develop.
3. Then the M2 plan (`superpowers:writing-plans`), reviewed to zero and self-approved.

## Research technique
- **KSEI** (web.ksei.co.id) serves plain `curl`. Dividend schedule letters are at `/Announcement/Files/{TICKER}_DIV_{recording YYYYMMDD}_ID.pdf`, and the recording date is ex + 1 trading day. The month/year filter on the list page returns HTTP 500. Extract text with `uv run --no-project --with pypdf` and `extraction_mode="layout"`.
- **idx.co.id** returns 403 to curl and WebFetch. In Chrome through `browser_batch`, open an idx.co.id page and `fetch('/primary/NewsAnnouncement/GetAllAnnouncement?keywords=…&pageNumber=1&pageSize=30&dateFrom=YYYYMMDD&dateTo=YYYYMMDD&lang=id')`. It returns JSON with `Attachments[].FullSavePath`. Parse PDFs with `pdfjs-dist@4.10.38` from cdn.jsdelivr and keep the results in `window.T`. Output is capped at about 1,000 characters per call. PDF digits can come out spaced ("18 - 0 8 - 2025"), so strip whitespace before matching dates.
- **Regulations:** peraturan.bpk.go.id `/Download/<id>/…pdf` serves curl. ojk.go.id does not.
- Cloudflare sometimes shows a "verify you are human" box. Never click it; ask Shyden.

## Notes
- This is a personal project: not Shyden Ltd, and not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM project 1**, node `PVT_kwHOCQ_jzM4BkhEb`. Assert the title "steadyhand" before writing to it. New issues do NOT auto-add; use `addProjectV2ItemById`.
- Agent git and gh act as the `steadyhand-agent` App (administration: read). An admin write is Shyden's decision.
- The `python3` on this machine is Xcode's 3.9. The code uses uv's Python 3.12 and 3.13, and uv is pinned to 0.12.18.
- **A TestPyPI publish failure is not always ours.** An OIDC or TLS timeout goes away with `gh run rerun <id> --failed`, and `skip-existing` makes that safe.
