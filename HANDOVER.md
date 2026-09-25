# Handover: steadyhand

**Updated:** 2026-09-25 05:57 UTC (T-TAX finished)
**Local:** `~/Developer/Repos/steadyhand`, on branch `research/25-t-tax` (branched from `develop` at e7189d0) until #25 merges. Read `develop` with `git rev-parse origin/develop` and never retype it. `main` is at `a3eb88f` (no release yet).
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M1 Foundations is complete.** S1–S8 and #21 are merged. See git history.
- **Research tickets filed on 2026-09-25 and on the board (ShydenMcM project 1):** #24 T-RULES, #25 T-TAX, #26 T-LQ45, #27 T-PAY.
- **#24 T-RULES is DONE.** PR #28 merged as e7189d0, and #24 is closed. The develop deploy, run 36087600375, succeeded on all six jobs, publish-dev included. The output is `docs/research/t-rules.md`. Headline finding: **Kep-00136/BEI/09-2026** takes the minimum price to Rp1 from **28 Sep 2026** and makes ARA/ARB symmetric from **1 Jan 2027**. The spec's §3.6 is corrected.
- **#25 T-TAX is DONE on `research/25-t-tax`** (PR into develop; check `gh pr list --head research/25-t-tax --state all`). The output is `docs/research/t-tax.md`, reviewed to zero in 4 passes. Headline: **dividends to resident individuals are paid gross, with no withholding** (PP 55/2022 Pasal 9(2)(l)). They are exempt if invested by 31 Mar of the next year and held 3 tax years, with a yearly report through the Portal Wajib Pajak (PMK 18/2021 Pasal 35–36; PMK 81/2024 Pasal 370–374). Spec §3.5, §4, §5, §6.2, §9, §12 and Appendix A are corrected (spec review Pass 7). The switch stays default-off. M4 replaces `dividend_tax`'s bool with a per-dividend exemption claim.
- **Found while gating #25:** the local Hypothesis `dev` profile keeps the 200 ms deadline, and `tests/engine/test_portfolio_properties.py::test_cash_and_share_invariants` took 291 ms once (`DeadlineExceeded`, a false red). CI's `ci` profile sets `deadline=None`, so CI cannot hit it. It is filed as its own ticket.

## Resume steps
1. If the #25 PR is not merged: `gh pr checks <n>`, compare the run's SHA with `gh pr view <n> --json headRefOid`, merge when every required check is green, then watch the develop deploy (read every job BY NAME).
2. Fix the Hypothesis deadline flake ticket (its own branch from develop).
3. T-PAY (#27), then T-LQ45 (#26), then the M2 plan (`superpowers:writing-plans`), reviewed to zero and self-approved.

## Research technique (idx.co.id)
- idx.co.id returns 403 to curl and WebFetch. Use Chrome through `browser_batch`: open an idx.co.id page, then run a JS `fetch` of the PDF, then `pdfjs-dist@4.10.38` from cdn.jsdelivr (`getDocument({data: new Uint8Array(buf)})`). Tool output is capped at about 1,000 characters per JS call, so slice deliberately. Output containing `key=value` pairs is blocked as "cookie data".
- A local sink server does NOT work, because Chrome's local-network permission hangs the call. The IDX rules are under /id/peraturan/peraturan-bei/ › "Peraturan Perdagangan", and the holiday announcements are at /en/news/announcement (keyword "Holiday").
- Cloudflare sometimes shows a "verify you are human" box. Never click it; ask Shyden.

## Notes
- This is a personal project: not Shyden Ltd, and not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM project 1**, node `PVT_kwHOCQ_jzM4BkhEb`. Assert the title "steadyhand" before writing to it. New issues do NOT auto-add; use `addProjectV2ItemById`.
- Agent git and gh act as the `steadyhand-agent` App (administration: read). An admin write is Shyden's decision.
- The `python3` on this machine is Xcode's 3.9. The code uses uv's Python 3.12 and 3.13, and uv is pinned to 0.12.18.
- **A TestPyPI publish failure is not always ours.** An OIDC or TLS timeout goes away with `gh run rerun <id> --failed`, and `skip-existing` makes that safe.
