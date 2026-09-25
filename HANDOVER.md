# Handover: steadyhand

**Updated:** 2026-09-25 02:51 UTC (session cleared at the operator's request, partway through T-TAX)
**Local:** `~/Developer/Repos/steadyhand`, on branch `research/25-t-tax` (branched from `develop` at e7189d0). Read `develop` with `git rev-parse origin/develop` and never retype it. `main` is at `a3eb88f` (no release yet).
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## State
- **M1 Foundations is complete.** S1–S8 and #21 are merged. See git history.
- **Research tickets filed on 2026-09-25 and on the board (ShydenMcM project 1):** #24 T-RULES, #25 T-TAX, #26 T-LQ45, #27 T-PAY.
- **#24 T-RULES is DONE.** PR #28 merged as e7189d0, and #24 is closed. The develop deploy, run 36087600375, succeeded on all six jobs, publish-dev included. The output is `docs/research/t-rules.md`. Headline finding: **Kep-00136/BEI/09-2026** takes the minimum price to Rp1 from **28 Sep 2026** and makes ARA/ARB symmetric from **1 Jan 2027**. The spec's §3.6 is corrected.
- **#25 T-TAX is IN PROGRESS.** The findings so far are in `docs/research/t-tax-notes-wip.md`, committed on `research/25-t-tax`. The sources are PMK 18/2021 (Pasal 15, 16 and 34–36; Pasal 37–41 were revoked by PMK 81/2024), PMK 81/2024 (Pasal 370–374), PP 55/2022 Pasal 9(2), and PP 20/2026 (no dividend change). The biggest finding: **dividends to resident individuals are paid gross, with no withholding** (PP 55/2022 Pasal 9(2)(l)). The investor self-pays 10% only if they do not reinvest, and spec §3.5's "10% final withholding tax" is wrong.

## Resume steps (T-TAX, #25)
1. `git switch research/25-t-tax && git pull`, then read `docs/research/t-tax-notes-wip.md` (its STILL TODO section).
2. Find where the 10% rate comes from: UU PPh Pasal 17 ayat (2c) as amended by UU HPP 7/2021, and whether PP 19/2009 is still in force. BPK's `peraturan.bpk.go.id/Details/<id>` pages give `/Download/<id>/…pdf`. curl works there. Extract the text with `uv run --no-project --with pypdf==5.4.0`. **Look up each Details id with WebSearch; never guess one** (a guessed id returned an unrelated city regulation).
3. Write `docs/research/t-tax.md` against #25's AC1–AC7, delete the WIP notes file, correct spec §3.5 and §6 (reinvestment), and log a spec review pass. Review it to zero, then open a PR into develop that closes #25, merge when every required check is green on the head SHA, and watch the develop deploy.
4. Then T-PAY (#27) and T-LQ45 (#26), then the M2 plan (`superpowers:writing-plans`), reviewed to zero and self-approved.

## Research technique (idx.co.id)
- idx.co.id returns 403 to curl and WebFetch. Use Chrome through `browser_batch`: open an idx.co.id page, then run a JS `fetch` of the PDF, then `pdfjs-dist@4.10.38` from cdn.jsdelivr (`getDocument({data: new Uint8Array(buf)})`). Tool output is capped at about 1,000 characters per JS call, so slice deliberately. Output containing `key=value` pairs is blocked as "cookie data".
- A local sink server does NOT work, because Chrome's local-network permission hangs the call. The IDX rules are under /id/peraturan/peraturan-bei/ › "Peraturan Perdagangan", and the holiday announcements are at /en/news/announcement (keyword "Holiday").
- Cloudflare sometimes shows a "verify you are human" box. Never click it; ask Shyden.

## Notes
- This is a personal project: not Shyden Ltd, and not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM project 1**, node `PVT_kwHOCQ_jzM4BkhEb`. Assert the title "steadyhand" before writing to it. New issues do NOT auto-add; use `addProjectV2ItemById`.
- Agent git and gh act as the `steadyhand-agent` App (administration: read). An admin write is Shyden's decision.
- The `python3` on this machine is Xcode's 3.9. The code uses uv's Python 3.12 and 3.13, and uv is pinned to 0.12.18.
- **A TestPyPI publish failure is not always ours.** An OIDC or TLS timeout goes away with `gh run rerun <id> --failed`, and `skip-existing` makes that safe.
