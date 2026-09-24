# Handover: steadyhand

**Updated:** 2026-09-24 06:48 UTC
**Local:** `~/Developer/Repos/steadyhand`. `main` and `develop` sit at `a3eb88f`. Branch **`docs/m1-plan`** is three commits ahead of them: the M1 plan with the spec fixes, then the story numbers (`2facf9ad81cc3afb23f6a3fd75e5377659f44080`), then this handover. Read its HEAD with `git rev-parse docs/m1-plan`.
**GitHub:** https://github.com/ShydenMcM/steadyhand. Public, and **still has no branches: nothing has been pushed** (`git ls-remote --heads origin` prints nothing).

## Done this session
- **M1 Foundations plan** written, reviewed to zero in 4 passes, and self-approved: `docs/superpowers/plans/2026-09-24-m1-foundations.md`. Every code block was verified by extracting it into a scratch tree and running the real gates under uv 0.12.18: 216 tests at 100% branch coverage on Python 3.12 and 3.13, ruff, format, `mypy --strict`, build, standalone engine install, and pip-audit. Every red-phase prediction and every mutation prediction was replayed. The review log is at the end of the plan.
- **Spec** passes 4 and 5 (Appendix B): §5 zero volume, §6.2 portfolio value includes unsettled cash, §9.8 exact disclaimer, §13 TestPyPI moved to M1. Status is now "Approved".
- **Board:** ShydenMcM project **#1 "steadyhand"**, node id `PVT_kwHOCQ_jzM4BkhEb`, linked to the repo. Title asserted through the node id.
- **Stories #1 to #8** filed with full acceptance criteria, all on the board and read back: S1 workspace/CI, S2 supply chain, S3 Money, S4 types, S5 Portfolio, S6 protocols, S7 meta-guards, S8 TestPyPI dev publishing (blocked on OP-1).

## Blocked: needs Shyden
1. **The first push.** Run this from a normal terminal tab, not a Claude session:
   `cd ~/Developer/Repos/steadyhand && git push -u origin main develop docs/m1-plan`
2. **How later pushes happen.** M1 is 8 PRs, and the agent cannot push to this repo (`git_credential.py` refuses by design). Either Shyden pushes each branch by hand, or the agent App is installed on `ShydenMcM/steadyhand`. This was asked in-session with `AskUserQuestion`; check the answer before starting S1.
3. **OP-1, before S8 only:** TestPyPI pending publishers for `steadyhand` and `steadyhand-idx` (owner `ShydenMcM`, repo `steadyhand`, workflow `ci.yml`, environment `testpypi`).

## Resume steps (cold session, started inside this folder)
1. `git ls-remote --heads origin` must list `main`, `develop` and `docs/m1-plan`. If not, stop and ask Shyden (Blocked, item 1).
2. Open a PR `docs/m1-plan` into `develop` (`Refs #1`, and never "close"/"fix" next to a number), then merge it. There is no CI yet, so nothing is required.
3. Run plan **Task 0 steps 1 to 4**: default branch `develop`, merge options, secret scanning and push protection, and protection on `main` and `develop`, each read back. Steps 5 and 6 (board and stories) are **already done**; do not repeat them.
4. Execute the plan from **Task 1 (S1, issue #1)**. Recommended: native execution (`superpowers:executing-plans`), because the plan carries verified code and every task needs a push from Shyden anyway.
5. Research tasks before M2: T-RULES, T-TAX, T-LQ45, T-PAY (spec §12).

## Notes
- This is a personal project: not Shyden Ltd, not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM #1**, which is a different owner from Shyden-Ltd's boards. Always resolve it by node id.
- Local `uv` is 0.5.9, and the plan's Task 1 step 1 runs `uv self update 0.12.18`. The scratch prototype used a cached 0.12.18 binary instead.
- `~/CLAUDE.md` (the ShyTalk context) was moved to `~/Developer/Repos/ShyTalk/CLAUDE.md` and is uncommitted there. Committing it is a job for a ShyTalk session.
