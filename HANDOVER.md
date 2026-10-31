# Handover: steadyhand

**Updated:** 2026-10-31 (UTC). Current state only. Older history: `git show d66cdce:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`.

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision. Do not edit the global layer: send global cuts to repo-template-af.

## Branches and heads
- `develop` = d72f7f0. Merge green PRs into develop without asking; never `main`.
- Required checks: develop 11 (incl. `coverage`), main 10.
- #224 and #225 closed 2026-10-31 (PRs #452, #455, #454), each after every criterion was checked against merged develop, case by case.
- `../steadyhand-272` still holds 2 uncommitted files (#272 closed as not needed).
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (to 2026-11-27); `365/exact-values-backup-2026-10-27` (to 2026-11-26), `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29).

## Next ticket
The board's `Priority` field picks it, never this file. Every open ticket is scored (2026-10-31); run:

```sh
git -C ../repo-template fetch -q origin develop
mkdir -p .superpowers/sdd/rt
for f in board-next board-setup board-progress cli; do git -C ../repo-template show origin/develop:scripts/$f.ts > .superpowers/sdd/rt/$f.ts; done
node .superpowers/sdd/rt/board-next.ts PVT_kwHOCQ_jzM4BkhEb "steadyhand"
```

A new ticket gets its `Priority` when filed, or board-next refuses.

## Waiting on Shyden
- Delete the scratch branches `coverage/336/logs-suite` and `coverage/444/check-name-clash` on origin (auto mode refused the delete).
- Keep or revert the test-isolation hook change (recommended keep).

## Resume steps
1. `ListAgents`; `git status --short`; `git fetch`.
2. board-next said #226 (EXT S5: the broker view, exact Indonesian numbers, freshness, the fixture broker and the scrubber, P1). Read its criteria; a criterion still asking for a recorded red phase or predicted mutations goes to Shyden first (as #223-#225). Branch `226-...` from develop; tests first.
3. Extension guards are CI-only; a hook refusal is final (never re-run them by another route). Write core to their rules: no `number` declarations or `Number(...)`, no generic `test.each<...>(`. Stash HANDOVER.md before a push (pre-push refuses a dirty tree).
4. Before closing any ticket: check EVERY criterion against the merged code and tests, case by case, and say exactly what was checked.

## Running
Nothing.

## Notes
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
- Copied comments cite `owner/repo#N` in full.
