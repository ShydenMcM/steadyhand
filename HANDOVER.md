# Handover: steadyhand

**Updated:** 2026-09-25 00:13 UTC
**Local:** `~/Developer/Repos/steadyhand`. `develop` is at `58d5b559fd532935264e0befbaca36a832c21520` (story #10, merged as PR #11), plus this handover's PR once it merges. Read the current value with `git rev-parse origin/develop` and never retype it. `main` is at `a3eb88f`.
**GitHub:** https://github.com/ShydenMcM/steadyhand. `develop` is the default branch.

## Done in the 2026-09-25 session
- **First push** by Shyden. **Plan PR #9** was squash-merged into `develop` (`5d36233`).
- **Task 0 steps 1 to 4:** `develop` is the default branch. Squash and merge-commit merges are allowed, rebase merges are off, and merged branches are deleted. Secret scanning, push protection, Dependabot alerts and Dependabot security updates are all on. `main` and `develop` are protected (admins enforced, no force pushes, no deletion, a PR required with 0 approvals, conversations must be resolved). Every setting was read back.
- **Story #10, closed:** agent sessions now act as the **`steadyhand-agent`** GitHub App (App id 5067374, installation 164630038). It is owned by ShydenMcM and installed on this repository only. `git push`, PRs, merges and issues from an agent session run as the App, and commits stay authored as Shyden. PR #11 was the App's first push and merge.
  - The App can **read** administration but **not write** it. So Task 1 step 13 (required checks) and Task 8 step 1 (the `testpypi` environment) are Shyden's to run. Write the step's commands to a file, print its path, and ask him to run `! env -u CLAUDECODE bash <path>`. The agent then reads the result back.
  - **The board stays on the operator's login**, because GitHub gives an App no permission for a board a user owns. `gh project` calls on board number 1 run as ShydenMcM.
  - The shared tooling in `~/.claude/scripts/github-app` now supports an App owned by a user and an App with no board. All suites and mutation matrices are green where it is installed.
- **Plan execution ledger:** `.superpowers/sdd/2026-09-24-m1-foundations/progress.md`, which is git-ignored. Task 0 is complete, and it records every ruling made so far.

## Blocked: needs Shyden
- **OP-1, before S8 only:** TestPyPI pending publishers for `steadyhand` and `steadyhand-idx` (owner `ShydenMcM`, repo `steadyhand`, workflow `ci.yml`, environment `testpypi`).

## Resume steps (cold session, started inside this folder)
1. `git switch develop && git pull --ff-only`, then run `git rev-parse origin/develop` and check it is `58d5b55` or later.
2. Invoke `superpowers:executing-plans` on `docs/superpowers/plans/2026-09-24-m1-foundations.md`. The ledger shows Task 0 complete, so resume at **Task 1 (S1, issue #1)** on branch `m1/s1-workspace-ci`. Load `superpowers:test-driven-development` before starting.
3. Task 1 step 1 runs `uv self update 0.12.18`. The local uv is 0.5.9, from the standalone installer at `~/.local/bin/uv`, so a self-update works.
4. At Task 1 step 13, stop and hand Shyden the protection-write script, as described above.
5. Research tasks before M2: T-RULES, T-TAX, T-LQ45, T-PAY (spec §12).

## Notes
- This is a personal project: not Shyden Ltd, and not ShyTalk. Never touch the ShyTalk board or roadmap. The steadyhand board is **ShydenMcM project 1**, node `PVT_kwHOCQ_jzM4BkhEb`. Always resolve it by node id and assert the title before writing to it.
- The `python3` on this machine is Xcode's 3.9, and the App tooling runs on it. The steadyhand code itself uses uv's Python 3.12 and 3.13.
- `~/CLAUDE.md` (the ShyTalk context) was moved to `~/Developer/Repos/ShyTalk/CLAUDE.md` and is uncommitted there. Committing it is a job for a ShyTalk session.
