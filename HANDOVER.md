# Handover — steadyhand

**Updated:** 2026-09-24 06:05 UTC
**State:** local repo only (nothing on GitHub yet). Branches: `main` (b8820e6, spec commit), `develop` (same commit).

## Done
- Brainstorming for sub-project A is complete and every design section is approved (decisions are recorded in the memory file `project-trading-bot.md`).
- Spec: `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md`, reviewed to zero (3 passes, logged in Appendix B) and committed on `main`.

## Waiting on Shyden
1. Review the spec and approve it or request changes.
2. OP-2: approve creating the public repo `ShydenMcM/steadyhand` plus a Projects board.

## Resume steps (cold session)
1. `cd ~/Developer/Repos/steadyhand && git log --oneline -3` should show b8820e6.
2. If Shyden asked for changes: edit the spec, run review passes to zero again, log them in Appendix B, commit.
3. Once the spec is approved: invoke `superpowers:writing-plans` for **M1 Foundations** (§13). Review that plan to zero, then self-approve it (global rule).
4. Once OP-2 is approved: `gh repo create ShydenMcM/steadyhand --public --license apache-2.0` (**note: the license flag conflicts with an existing local repo**, so add the LICENSE file locally instead and use `--source . --push`). Push `main` and `develop`, set the default branch to `develop`, add branch protection, enable Dependabot alerts and security updates and read them back, and create the Projects board with M1 stories carrying full acceptance criteria.
5. Research-first tasks before M2: T-RULES, T-TAX, T-LQ45, T-PAY (§12).

Research notes (temporary, may be gone): the session scratchpad file `research-indonesia-trading.md`. Its key findings and sources are already in spec §3 and Appendix A.
