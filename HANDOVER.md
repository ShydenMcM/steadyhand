# Handover: steadyhand

**Updated:** 2026-09-25 06:07 UTC (T-TAX and #30 merged and deployed; T-PAY is next)
**Local:** `~/Developer/Repos/steadyhand`, on `develop`. Read `develop` with `git rev-parse origin/develop` and never retype it. `main` is at `a3eb88f` (no release yet).
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M1 Foundations is complete.** S1–S8 and #21 are merged. See git history.
- **Research tickets filed on 2026-09-25 and on the board (ShydenMcM project 1):** #24 T-RULES, #25 T-TAX, #26 T-LQ45, #27 T-PAY.
- **#24 T-RULES is DONE.** PR #28 merged as e7189d0, and #24 is closed. The develop deploy, run 36087600375, succeeded on all six jobs, publish-dev included. The output is `docs/research/t-rules.md`. Headline finding: **Kep-00136/BEI/09-2026** takes the minimum price to Rp1 from **28 Sep 2026** and makes ARA/ARB symmetric from **1 Jan 2027**. The spec's §3.6 is corrected.
- **#25 T-TAX is DONE.** PR #29 merged as fe46b86, and #25 is closed. The develop deploy, run 36101096840, succeeded on all six jobs, publish-dev included. The output is `docs/research/t-tax.md`, reviewed to zero in 4 passes. Headline: **dividends to resident individuals are paid gross, with no withholding** (PP 55/2022 Pasal 9(2)(l)). They are exempt if invested by 31 Mar of the next year and held 3 tax years, with a yearly report through the Portal Wajib Pajak (PMK 18/2021 Pasal 35–36; PMK 81/2024 Pasal 370–374). Spec review Pass 7 corrects the spec. The switch stays default-off, and **M4 must replace `dividend_tax`'s `reinvested_by_deadline: bool` with a per-dividend exemption claim** (spec §6.2; t-tax.md §7).
- **#30 is DONE.** PR #31 merged as b83e692 (develop deploy run 36101397838, all six jobs green): the local Hypothesis `dev` profile now has `deadline=None`, pinned by `tests/meta/test_hypothesis_profiles.py` (mutation-verified).

## Resume steps (T-PAY, #27)
1. `git switch develop && git pull`, then `gh issue view 27` for AC1–AC5. Branch `research/27-t-pay` from develop.
2. AC1 needs at least 20 cash-dividend announcements (at least 10 issuers, at least 2 years) with cum, ex, recording and payment dates plus source URLs. Get them from idx.co.id announcements or KSEI, through Chrome (see Research technique below). **Plan every browser sequence as one `browser_batch`.**
3. AC2 counts the lag in IDX trading days. The holiday calendar is verified only for 2026–2027 (`docs/research/t-rules.md` §4). Any sample year outside that needs its own holiday announcement first, or the count is unverified.
4. AC3 is the IDX/KSEI rule on the gap between recording date and payment date. AC5 asks whether yfinance `.JK` exposes a payment date, which can be checked locally with `uv run --no-project --with yfinance`.
5. Write `docs/research/t-pay.md`, correct spec §5 (the pay-lag default) and §12, review to zero, open a PR into develop that closes #27, merge on green checks for the head SHA, and watch the deploy. Then T-LQ45 (#26), then the M2 plan (`superpowers:writing-plans`), reviewed to zero and self-approved.

## Research technique (idx.co.id)
- idx.co.id returns 403 to curl and WebFetch. Use Chrome through `browser_batch`: open an idx.co.id page, then run a JS `fetch` of the PDF, then `pdfjs-dist@4.10.38` from cdn.jsdelivr (`getDocument({data: new Uint8Array(buf)})`). Tool output is capped at about 1,000 characters per JS call, so slice deliberately. Output containing `key=value` pairs is blocked as "cookie data".
- A local sink server does NOT work, because Chrome's local-network permission hangs the call. The IDX rules are under /id/peraturan/peraturan-bei/ › "Peraturan Perdagangan", and the holiday announcements are at /en/news/announcement (keyword "Holiday").
- Cloudflare sometimes shows a "verify you are human" box. Never click it; ask Shyden.

## Notes
- This is a personal project: not Shyden Ltd, and not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM project 1**, node `PVT_kwHOCQ_jzM4BkhEb`. Assert the title "steadyhand" before writing to it. New issues do NOT auto-add; use `addProjectV2ItemById`.
- Agent git and gh act as the `steadyhand-agent` App (administration: read). An admin write is Shyden's decision.
- The `python3` on this machine is Xcode's 3.9. The code uses uv's Python 3.12 and 3.13, and uv is pinned to 0.12.18.
- **A TestPyPI publish failure is not always ours.** An OIDC or TLS timeout goes away with `gh run rerun <id> --failed`, and `skip-existing` makes that safe.
