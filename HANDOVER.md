# Handover: steadyhand

**Updated:** 2026-11-06 after an unclean shutdown (recovery checked). Current state only. Older history: `git show d66cdce:HANDOVER.md`.

**Direction (#214):** a TypeScript Chrome extension reading the user's broker page; spec `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`. No device or phone work here (desktop extension; phones unavailable anyway).

**Ruling 2026-10-30 (every project):** keep it simple, product work first. Value test before every decision.

**Standing approval (Shyden 2026-11-04, AskUserQuestion):** squash-merge into develop any PR green on every check on its head.

## PARKED for Shyden
1. **#506 (reopened, Todo):** a side agent flagged I closed it on an unproven cause; reopened. Shyden chose "timed CI runs". Done 2026-11-06: 30 CI unit runs (run 42076710915). Disk sync ON: COMMIT max 141.6 ms, p99 up to 36.8 ms, suite 8.9-11.6 s. OFF (develop since PR #507): max 0.10 ms, suite 4.7-7.4 s. Process stalls max 76 ms. Nothing reached 1 s: the original >1 s is NOT reproduced, so its cause is still unproven. His call: close on this evidence (the fix removes the only heavy-tail mechanism measured and halves the suite) or keep open and watch. Results are on #506.

## Branches and heads
- `develop` = 2c7e90002db323a552c15a0b5152783ee5d3d10b (#502, PR #505).
- Checked out: `503/real-side-panel` (PR #509). `probe/503-side-panel` is a throwaway (never merge), head in `.superpowers/sdd/probe503-head.txt`, pushed; workflow `probe-503.yml` screenshots each browser's toolbar under Xvfb with the extension pinned, artifact `probe-503`.
- `probe/506-sync-on-ci` (throwaway, pushed, never merge): the #506 timing probe. Delete local and remote once Shyden rules on #506.
- `238/extension-shell` merged (PR #500); delete locally only after checking its tip equals PR #500's head 3f3dd12.
- Backups (keep 30 days): `377/wip-backup-2026-10-28` (to 2026-11-27); `365/exact-values-backup-2026-10-27` (to 2026-11-26), `-10-28` (to 2026-11-27); `~/.claude/hooks/test-isolation{,.test}.py.bak-2026-10-30-direct-path` (to 2026-11-29).

## Running
- PR #509 head 51006f3 (Edge puzzle picture re-cut at rest; the old one was hovered, grey 222 vs white 255) (in `.superpowers/sdd/503-head.txt`). On fbd3695 Chromium and Chrome PASSED the journey in the real side panel; Edge failed: "screen shows none of these exactly once (tile: 0, Edge's extensions button: 0)". c43ae2d saves the screen on failure and CI uploads `extension/test-results/` as artifact `browser-suite-failure` (fast-path guard widened for `failure() && <skip>` uploads, Shyden 2026-11-06). A local waiter (dies with /clear) downloads it to `.superpowers/sdd/503/fail-c43ae2d/`; else `gh run download <run> -n browser-suite-failure -D .superpowers/sdd/503/fail-c43ae2d`. Then look at `screen-at-failure.png`, fix Edge (test first), push, verdict, mutation on probe branch, merge, ACs, close #503.

## #503 (P0, est 13, In Progress): real side panel by its toolbar button
- Shyden 2026-11-05: an OS mouse click on CI's virtual screen (Xvfb + xdotool) counts as real input (on the ticket).
- Measured before: `sidePanel.open()` refused over CDP even with `userGesture: true`; Playwright cannot click the toolbar.
- Plan: pin the extension via the profile's Preferences (`extensions.pinned_extensions`, id = sha256(path) first 32 hex mapped a-p, checked against loadUnpacked's id); headed browser at 1280x800 under Xvfb; find the button (no icon in the manifest: Chrome draws a letter); xdotool click; find the side panel target over CDP; then the journey runs in it at the panel's width. If a browser cannot, the test fails naming why.
- An extension icon would make the button findable by image; an icon is a brand choice: ask Shyden, do not invent one.
- Measured on CI (probe runs 42077716955, 42080281316, 42081257944; screenshots in `.superpowers/sdd/503/run*`): the computed id equals loadUnpacked's on all three. Chrome and Chromium honour the pin; Edge does not (its extensions menu lists "steadyhand"). Without a window manager screenshots came out blank: Xvfb + openbox, then wait until the screen has >50 colours. With that, an xdotool click on the pinned "S" at (1130, 64) OPENS THE REAL SIDE PANEL on Chrome and Chromium (CDP target `page .../side-panel.html`, rendered in the screenshot); Playwright's own `context.pages()` does not list it. Edge: puzzle (1022, 59) opens the menu; the entry is at (765, 203).
- Iteration 4 (run 42081957659): Edge opens it via its menu; `connectOverCDP` on `--remote-debugging-port=9333` drives the panel on all three (360x660 Chrome/Chromium, 382x666 Edge).
- **PR #509, branch `503/real-side-panel`**, head in `.superpowers/sdd/503-head.txt`: `tests/lib/find-image.ts` (+unit tests, red first, mutation caught), `tests/browser/side-panel.ts` (screenshot, image search, xdotool, connectOverCDP, clock on the CDP context), journey runs in the real panel with width checks, ci.yml screen step (+repo test, red first). Local gate green (unit 3284, 100% cov). Waiting on CI. Still to do once green: mutation on CI (drop `openPanelOnActionClick` on the probe branch: the journey must fail naming no panel page), then merge, ACs, close.

## Waiting
- #308, #400 (main protection) and #348 (SonarCloud): Shyden's.

## Done 2026-11-05
- #501 (PR #504), #502 (PR #505) merged and closed. #506 merged (PR #507) then reopened (above).

## Resume steps
1. `ListAgents`; `git status --short`; `git fetch --prune`; `git rev-parse --abbrev-ref HEAD`.
2. Probe-503 result: `gh run list --workflow probe-503.yml --branch probe/503-side-panel`; `gh run download <id> -n probe-503 -D .superpowers/sdd/503/`; look at each `screen-*.png` and the `PROBE503` log lines.
3. Next ticket after #503: `node ~/Developer/Repos/repo-template/scripts/board-next.ts PVT_kwHOCQ_jzM4BkhEb steadyhand 2>/dev/null`.
4. Core rules (CI-only guards, a hook refusal is final): no `number` declarations or `Number(...)` in core, no index parameters in callbacks, no generic `test.each<...>(`, no identifier named `window`/`document`/`chrome`/`indexedDB` in core, no `%j` titles over bigints; a `?? fallback` never taken fails 100% branch coverage; scratch copies go in `pristine/`, never `*.bak`. Guards (Python and extension), integration and the browser suite are CI's: the hook refuses them locally.
5. Filing a ticket: `gh issue create`, `gh project item-add 1 --owner ShydenMcM --url <issue>`, `gh project item-edit` (project id `PVT_kwHOCQ_jzM4BkhEb`) with Priority `PVTSSF_lAHOCQ_jzM4BkhEbzhn_bYM` (P0 `2f8059d5`, P1 `ec7925c3`, P4 `6e3c5b78`), Estimate `PVTF_lAHOCQ_jzM4BkhEbzhkUeyc`, Status `PVTSSF_lAHOCQ_jzM4BkhEbzhjRYtk` (Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`); read back by repository + issue. Blocked-by: `gh api -X POST repos/ShydenMcM/steadyhand/issues/<n>/dependencies/blocked_by -F issue_id=<blocker database id>`.

## Notes
- pre-push refuses an uncommitted tree: `git stash push HANDOVER.md`, push, `git stash pop`. `git commit --amend` is refused by auto mode: add a commit.
- Throwaway probe files carry a file-level `# ruff: noqa` / `/* eslint-disable */` so pre-push passes.
- A PreToolUse refusal drops the whole command, edits included: re-apply them.
- The editor's TypeScript diagnostics disagree with `tsc --noEmit`; tsc is the authority.
- Test runs queue machine-wide behind other projects: background long runs.
- A CI job's log: `gh run view <run> --log --job <job id>`.
- Wi-Fi is unstable: name the network as a possible cause of a failed fetch or push; no retries.
