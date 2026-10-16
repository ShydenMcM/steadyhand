# Handover: steadyhand

**Updated:** 2026-10-16 (UTC date). Current state only. The long history (M3 to M7, T1, research notes) is at `git show 932167c:HANDOVER.md`.

**Direction (#214):** steadyhand becomes a Chrome extension in TypeScript that reads the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. EXT stories #222-#245 follow the clean-up queue below.

## Branches and heads
- `develop`: `a744c01` (the #336 handover, PR #338, all 14 required jobs green on the docs fast path; read with `git rev-parse origin/develop`). Merge green PRs into `develop` without asking; never `main`.
- `docs-handover-339`: this file only, one commit, for a docs PR.

## Done today (2026-10-16)
- **Logs-suite rule** (global, Shyden 2026-10-16, relayed by the yawelo-idle session, checked in `~/.claude/CLAUDE.md` and `reference-engineering-standards.md`): log and audit checks get their own suite, run in CI before each release. Filed **#336** (5, P2): steadyhand's only trails are the three append-only tables of the paper account's `state.sqlite` (`audit`, `runs`, `day_reports`, replayed by `report`). 46 candidate tests sit in 9 files (37 unit, 8 integration, 1 perf). Python never uses `logging`, and the extension keeps no log. #336 is linked as **Blocked by** on #245 (the release), and the link was read back.
- Seen in passing: 39 open tickets name blockers only in their text, with no GitHub link (#222-#258, #272, #214). Filed **#337** (3, P3). Both tickets are on the board (Todo), with Estimate read back.
- Shyden then ruled (global, AskUserQuestion): **every app we build logs, and its logging is tested.** Recorded in `~/.claude/CLAUDE.md` (folded into the logs-suite line, which was at its size ceiling) and in `reference-engineering-standards.md`. Relayed to yawelo-idle-5e (which holds repo-template), shytalk-22 and shyden-co-uk-96. His answers: the extension's log stays **on the user's machine**, viewable and copyable in the side panel. #336 runs **release only** (no steadyhand exception), recorded on #336.
- Filed **#339** (now `EXT later`, 5, P4, `post-launch`): the extension's on-device log, tested in the logs suite. Shyden amended the rule the same day, in the yawelo-idle session: app logging comes **after** each release and is designed **once in repo-template**. So #339 no longer blocks #245, and it will follow the template design (yawelo-idle holds that story). #339 is blocked by #231, #239 and #336; link the template story once it is filed. #336 still blocks #245, because the logs test suite still gates every release. The Python CLI's log is its paper `audit`/`runs` trail (#336), and the frozen packages get no new logging.
- Shyden then ruled (global, amended the same day): **personal data is left out of logs, or anonymised, by default.** It is kept only where it is needed (ShyTalk's moderation records) and where the privacy policy states why, what is done with it and when, and how long it is kept. steadyhand needs none. It is recorded in `~/.claude/CLAUDE.md` line 38 and in the reference, and relayed to all three sessions (yawelo-idle builds it into the template design). #339's criteria now use an allow-list of non-private codes, and the copy button goes through the same check. Filed **#341** (2, P2): the Python paper audit log drops `, by <login name>` from resume and switch lines (Shyden: "Drop the login name"), and core spec line 199 changes to match. Order lines stay.
- Priorities are written in each ticket's body until #315 adds the board field.

## Resume steps
1. Run `ListAgents`; no subagents were started.
2. If this file's docs PR (`docs-handover-339`) is still open, read its run by job name and merge it when green.
3. Next: **#288** (5, mutations in CI). It unblocks #282 and #292, which wait only on their integration-half mutations (`.superpowers/sdd/282/`, `.superpowers/sdd/292/`). Then #287 (Node 26).

## Next on the clean-up queue (all before #222)
- **#288** (5, mutations in CI, with #282's and #292's), **#287** (3, Node 26), **#272** (5, Python floors, including #323's five), **#315** (2, board Priority, blocked by repo-template#6), **#317** (5, orphan check in the PR gate), **#320** (2, README for the extension direction), **#337** (3, blocker links), **#336** (5, logs suite, before #245). **#341** (2, login name out of the paper audit). #339 (extension log) is post-release.

## Raised with Shyden
- Three global hook false positives, for a dedicated `~/.claude` session (his choice, 2026-10-12): `~/.claude/hook-false-positives-2026-10-13.md`.
- The test-lock hook treats a `python3 -` edit script that names a `.test.ts` path as a heavy test run; edits went through the Edit tool instead.

## Progress (2026-10-16, `uv run --locked python .superpowers/sdd/estimates/progress.py`; `post-launch` tickets left out)
- **Measured:** EXT first release 4 of 28 stories closed (21 of 184 points). Board open: 37 tickets, 209 points (epic #214 unscored). Closed 2026-10-09 to 2026-10-16: 7 tickets, 35 points.
- **By tickets: 14% complete (4 of 28 stories). ETA 2026-11-21, low confidence:** 36 open scored tickets at 1.0 a day is 36 days.
- **By effort: 209 points remaining across 36 scored open tickets. ETA 2026-11-27, low confidence:** 5.0 points a day is about 42 days.
- **Assumed:** last week's pace (test work) holds for feature stories. **Outside waits:** a broker account (#242), Chrome Web Store review, repo-template#6 for #315.
