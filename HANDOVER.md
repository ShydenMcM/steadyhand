# Handover: steadyhand

**Updated:** 2026-09-25 (session end, UTC time in the commit)
**Local:** `~/Developer/Repos/steadyhand`. Read `develop` with `git rev-parse origin/develop` and never retype it. `main` is at `a3eb88f` (no release yet).
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## M1 Foundations: complete
- **All eight stories merged and closed:** S1 #13, S2 #14, S3 #15, S4 #16, S5 #17, S6 #18, S7 #19, S8 #20. Every run was read job by job against its PR head SHA.
- **Final-review fixes, story #21 (PR #22):** `require_type` now guards every value-type field, and `set_dev_version.py` refuses non-ASCII digits. Before this, `Order(side="buy")` was booked as a sell and `OrderAck(accepted="no")` read as an acceptance.
- **Dev publishing is live:** every merge into `develop` publishes `0.1.0.devN` of both packages to TestPyPI and checks that both install. The first deploy (run 36083908255) is at `0.1.0.dev17`; #21's deploy (run 36084657195) is at `0.1.0.dev19`.
- **A red `publish-dev` is not always ours:** #21's first attempt died minting the OIDC token (TLS handshake timeout to test.pypi.org). Read the log before anything else; if it is a timeout, check `curl https://test.pypi.org/simple/steadyhand/` and `gh run rerun <id> --failed`. `skip-existing` makes a re-run safe.
- **Required checks:** `develop` and `main` require `lint`, `test (py3.12)`, `test (py3.13)`, `audit` and `build`, with `strict: true`. The `testpypi` environment deploys only from `develop`. Shyden set these in the GitHub web UI, and they were read back through the API.
- **TestPyPI:** the `steadyhand` and `steadyhand-idx` trusted publishers are active (ShydenMcM/steadyhand, `ci.yml`, `testpypi`). The account has 2FA on.

## Rulings made (the full list is in the git-ignored plan ledger, now deleted, and summarised here)
- Ruff 0.16 formats Python blocks inside Markdown, so `docs/superpowers` is excluded from ruff. READMEs stay checked.
- The S7 mutation runs used `.venv/bin/python -m pytest`, because `uv run` re-syncs and would have installed M4's `requests`.
- S5's squash commit carries the commit subject, not the plan's wording. This is cosmetic.
- **TestPyPI allows one pending publisher per (repo, workflow, environment).** The bootstrap was: `skip-existing: true` on the publish step, a first run that uploaded `steadyhand` and failed on idx, registering idx, then re-running the job. Any future new package from the same workflow needs the same two-step bootstrap.
- Final review was a self-review, because review agents are refused by hook. Its findings were fixed as #21 rather than deferred, under the operator's rule that every defect is P0.

## Next
1. `git switch develop && git pull --ff-only`, then `git rev-parse origin/develop`.
2. Research tasks before M2 (spec §12): T-RULES, T-TAX, T-LQ45, T-PAY.
3. Write the M2 plan with `superpowers:writing-plans`. It covers the IDX data source (Yahoo `.JK`), and "Carried forward to later plans" in the M1 plan lists what M2 and M3 inherit. Review it to zero findings, then self-approve.

## Notes
- This is a personal project: not Shyden Ltd, and not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM project 1**, node `PVT_kwHOCQ_jzM4BkhEb`. Resolve it by node id and assert the title "steadyhand" before writing to it.
- Agent git and gh act as the `steadyhand-agent` App, which has administration **read** only. An admin write is Shyden's decision: ask him, and if he says to go ahead, do it in the GitHub web UI through `browser_batch`, never by stepping round the router.
- The `python3` on this machine is Xcode's 3.9. The steadyhand code uses uv's Python 3.12 and 3.13, and uv is pinned to 0.12.18.
