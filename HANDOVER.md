# Handover: steadyhand

**Updated:** 2026-10-20 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: read with `git rev-parse origin/develop` (`383dd3d` when written, PR #355). Merge green PRs into `develop` without asking; never `main`.
- `docs-handover-2026-10-20b`: this file, one docs commit, PR into `develop`.
- Local branches kept by choice: `203/spec-amendment-wip` (also on GitHub, no PR), `ext/s3b-guards` (#222 WIP, 1 commit). `349/dependabot-groups` and `350/typescript-major` are at their merged PR heads (#352, #355) and can go.

## Done this session (2026-10-20)
- **#349 closed.** Dependabot does not take the first matching group, whatever its docs say: dependabot-core scores groups (#13098), and a group with no patterns (500) outranks any wildcard (`@vitest/*` 94). PR #352: each catch-all excludes the pattern groups' patterns; the guard models `DependencyGroup#contains?`; `mutations/349.toml` 10 of 10. Proven by #353 (vitest pair moved together, merged). #354 (six packages) merged. #329 and #333 closed with comments.
- **#350, PR #355 merged (`383dd3d`).** General rule, Shyden's choice: the guard reads every peer range in the lock (npm range reader, 0 disagreements with node-semver over 1,890 pairs) and requires exactly the holds they call for: `typescript`, `eslint`, `vite` majors and `esbuild` `>=0.29.0` (0.x counts as minor to Dependabot). It turns red when a peer widens, and then the hold goes. `mutations/350.toml` 13 of 13. #334 closed. Estimate raised to 3.
- **Global fix (Shyden: "global fix please"):** the `actions/cache*` "above the patch group" rule had the same flaw. Amended in `~/.claude/CLAUDE.md` (the line was later shortened to fit the size ceiling, by another session), in `reference-supply-chain.md`, and in a new row "Tool modelled from its docs" in `reference-guard-forms-and-floors.md`. `global-rules/pending-dependabot-group-exclusions.md` asks each project and repo-template to apply it in its own repo.
- Asked Dependabot to rebase #330, #331, #332 and #335 (they predate the required mutations check).

## Resume steps
1. Run `ListAgents`. No subagents were started.
2. Merge this handover PR when green (docs fast path).
3. **Close #350 by hand** once `develop`'s ci run 39353384209 (`383dd3d`) is green with `deploy-dev` success. AC 1: registry read 2026-10-20T00:02Z, 8.72.0 `>=4.8.4 <6.1.0`. AC 2: PR #355, C1 red, #334 closed. AC 3 does not apply. AC 4: the guard turns red when the range widens.
4. #330, #331, #332, #335: merge each when all 15 required checks are green on its rebased head (`pr-verdict.sh`, then `wait-run.sh`). Merge one, then `@dependabot rebase` the next (strict).
5. Next: **#287** (3, Node 26; worked example yawelo-idle #501 / PR #507), then the queue below.
6. When Shyden has made #308's key: build the daily workflow (environment allowing `main` only, `--ref main` dispatch, a pin test, a planted mismatch that opens an issue).

## Waiting on Shyden / to do
- **#308's read-only key** (branch-protection read).
- Ticket-filing procedure (global, 2026-10-16): steadyhand has no `.github/ISSUE_TEMPLATE`. File a story (search first) to bring the form and the open board up to yawelo-idle's `story.yml` and repo-template#20.

## Next on the clean-up queue (all before #222)
- **#287** (3, Node 26), **#272** (5, Python floors, including #323's five), **#348** (5, P1, SonarCloud blocking, waits on repo-template#27), **#308** (2, waits on the key), **#315** (2, board Priority, blocked by repo-template#6), **#317** (5, orphan check in the PR gate), **#320** (2, README for the extension direction), **#337** (3, blocker links), **#336** (5, logs suite, before #245), **#341** (2, login name out of the paper audit). #339 and #345 are post-release.

## Raised with Shyden
- Global hook false positives, for a dedicated `~/.claude` session: `~/.claude/hook-false-positives-2026-10-13.md`. Item 1 (the test lock reading "pytest" or a test path inside a heredoc) recurred 2026-10-20: a Python edit of `~/.claude` rule files was queued behind another project's heavy run.

## Progress (2026-10-20, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` tickets left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points), none in the last 7 days. Board open: 36 tickets, 200 points across 35 scored (epic #214 unscored). Closed 2026-10-13 to 2026-10-20: 6 tickets, 29 points (#350 still open until step 3).
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-30, low confidence:** 35 open scored tickets at 0.86 a day is about 41 days.
- **By effort: 200 points remaining across 35 scored open tickets. ETA 2026-12-07, low confidence:** 4.1 points a day is about 48 days.
- **Assumed:** this week's pace (clean-up, CI and test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315, repo-template#27 for #348, Shyden's key for #308.
