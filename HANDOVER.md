# Handover: steadyhand

**Updated:** 2026-09-24 06:11 UTC
**Local:** `~/Developer/Repos/steadyhand`, branches `main` and `develop` at the same commit (licence + README on top of the spec).
**GitHub:** https://github.com/ShydenMcM/steadyhand. Public, created 2026-09-24, **still empty: nothing has been pushed yet** (see step 1).

## Done
- Brainstorming for sub-project A is complete. Every design section is approved, and the decisions are recorded in the memory file `project-trading-bot.md` (steadyhand's own memory folder).
- Spec `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md` was reviewed to zero (Appendix B). **Operator approved it on 2026-09-24** ("yes do it").
- Apache-2.0 `LICENSE` and a design-phase `README.md` are committed.
- The GitHub repo is created. Dependabot alerts are ON, automated security fixes are enabled=true paused=false, and private vulnerability reporting is ON. All three were read back after enabling.

## Blocked: needs Shyden
**The agent cannot push.** `~/.claude/scripts/github-app/git_credential.py` only lets an agent session push to repos that have the agent App installed, and it refuses by design (`quit=1`, never a fallback). Do not work around it. Either:
- **(a)** Shyden pushes from a normal terminal tab, not a Claude session:
  `cd ~/Developer/Repos/steadyhand && git push -u origin main develop`
- **(b)** Shyden installs the agent App on `ShydenMcM/steadyhand`, if that App can be installed on a personal account.

## Resume steps (cold session, started INSIDE this folder)
1. Check the push landed: `git ls-remote --heads origin` should list `main` and `develop`. If not, stop and ask Shyden (see Blocked above).
2. Set the default branch to `develop`: `gh repo edit ShydenMcM/steadyhand --default-branch develop`, then read it back.
3. Branch protection on `main` and `develop`: require a PR, no force pushes, no deletions. **Do not add required status checks yet.** A CI job must exist on `develop` before it can be required, so add them in M1 after the CI PR merges, with `strict: true`, then re-read the protection.
4. Create the Projects board on the ShydenMcM account (`gh project create --owner ShydenMcM --title steadyhand`), link it to the repo, and **assert the board's TITLE before any write**.
5. Invoke `superpowers:writing-plans` for **M1 Foundations** (spec §13). Review that plan to zero, then self-approve it. Then file M1 stories on the board, each with full acceptance criteria, before any code.
6. Research tasks before M2: T-RULES, T-TAX, T-LQ45, T-PAY (spec §12).

## Notes
- This is a personal project: not Shyden Ltd, not ShyTalk. Never touch the ShyTalk board or roadmap.
- Separately, `~/CLAUDE.md` (the ShyTalk context) was moved to `~/Developer/Repos/ShyTalk/CLAUDE.md`. It is uncommitted there, and committing it is a job for a ShyTalk session. Nothing to do here.
