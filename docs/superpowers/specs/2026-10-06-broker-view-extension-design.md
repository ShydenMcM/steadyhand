# steadyhand: advice from what the user's broker shows (#214)

**Status:** draft for Shyden's review. Written from decisions 1-19 and the design approved on 2026-10-06 (sections 1-4, #214 issuecomment-6008393878, cited here as "design §n"), all on #214. The review loop is logged at the end.
**Ticket:** #214 (epic). **Replaces:** the M7-M10 plan of the core spec (§13: item 6's strategy waves 2-4 and item 7, the first release) and the backtest-data tickets #160, #161, #162, #200, #203 and #207 (§15).
**Parent spec:** `2026-09-24-steadyhand-core-design.md` (the "core spec"). This spec amends it in the places the scope decisions at the end list.

## 1. What this delivers

steadyhand becomes a Chrome extension. The user opens their broker's web platform as usual. steadyhand reads what that page shows, records it on the user's own machine, and tells the user, in a side panel beside the broker tab, what their chosen strategy implies now: which stock to buy or sell, how many lots, at what limit price, what it costs and why. It also shows progress towards their income goal and any risk alerts. Where it lacks a fact a figure needs, it names the exact page to open rather than guessing. The user places the orders themselves, by hand or with the broker's own automatic-order feature. steadyhand never places, changes or cancels an order, and nothing it reads leaves the machine.

The advice logic is rewritten in TypeScript. The Python packages stay in the repository, unchanged, as the reference the port is checked against (§14.4).

### 1.1 Out of scope (first release)
- **Placing orders** of any kind, and any action on the broker page (decision 2's survey found no broker with a retail order API; decision 12 makes the extension read-only).
- **Reading the broker's phone app.** An extension reads only a web page (decision 11).
- **Screenshots.** A later story, only after OCR accuracy is measured on real broker screenshots (decision 8).
- **A shared price store.** History is local only (decision 10).
- **Income received, the income projection and the dividend tax-exemption claims.** Later stories (decision 19).
- **Indonesian.** English only in the first release; Indonesian is a later story (design §4).
- **Backtesting and paper trading.** They stay in the Python packages, untouched and no longer developed (design §4).
- **Brokers other than the first.** Each later broker is its own reader story (§5).

## 2. Decisions

All are Shyden's, through AskUserQuestion, each with its reasoning shown; the full texts are on #214.

| # | Decision |
|---|---|
| 1 | steadyhand says what to trade, and places orders where possible (no broker makes that possible: decision 2). |
| 2 | Make it work for all brokers. The survey found no retail order or account API for IDX stocks. |
| 3 | Read what the user's broker shows; no own data source, no price downloads. |
| 4 | Two input routes: what the user shares (pasted text, exports) and a read-only browser helper. |
| 5-6 | Broker data only; no Yahoo (comments of 2026-10-06 01:30 and 01:35 UTC). |
| 7 | Output: orders (stock, lots, limit price on a valid tick, fees, reason), goal progress, risk alerts; a missing figure is named. |
| 8 | First-release inputs: the broker's web page, pasted text, export files. Screenshots later. |
| 9 | The user shares one broker watchlist of their candidates; a candidate missing from it is named. |
| 10 | History is local only, recorded from what the user's broker shows. |
| 11 | A browser extension only; the advice logic rewritten in TypeScript. |
| 12 | Security is binding: least permission, read only, nothing leaves, a hijacked update guarded against; each rule with a test that goes red (§11). |
| 13 | First broker: whichever of POEMS (Phillip Sekuritas) or BIONS (BNI Sekuritas) opens first and whose account agreement allows a read-only extension. |
| 14 | First release: all six strategies (buy-and-hold, monthly-savings, dividend-growth, high-yield, ma-trend, momentum-rotation) and the income goal. |
| 15 | Advice appears in Chrome's side panel. |
| 16 | Free forever, never "we recommend"; no lawyer's opinion (§12.3). |
| 17 | ma-trend and momentum-rotation keep total return: the broker's chart series adjusted by the dividends read (§6.5). |
| 18 | Deposits and withdrawals come from the broker's cash-movement page, else the user types them; a halt that cannot be judged stops buy advice (§8). |
| 19 | Income goal: progress and the payment calendar only (§9). |

## 3. Structure

A new TypeScript workspace `extension/` at the repository root, an npm workspace with four packages whose dependencies run one way only (shell, then readers and history, then core):

```
extension/
  package.json            npm workspaces; engines.node ">=24"; engine-strict
  packages/
    core/                 pure logic, no browser API, no I/O
    readers/              one module per broker, plus paste and export readers
    history/              the IndexedDB store and the series built from it
    shell/                the Manifest V3 extension: content script, side panel, settings
  rules/                  JSON generated from the Python rule files at build time (§4.2)
  tests/                  meta-guards, parity harness, Playwright specs
```

- **Language and checks:** TypeScript in `strict` mode with `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`; ESLint with typescript-eslint's strict, type-checked rules; Prettier. `tsc --noEmit` runs in CI, because the bundler strips types without checking them.
- **Tests:** Vitest for core, readers and history; Playwright loading the built extension in Chromium (§14).
- **Bundler:** esbuild, one bundle per entry point (content script, side panel, service worker). A test builds twice and compares the zips byte for byte (§12.2).
- **Dependencies:** as few as possible, each pinned exactly in `package-lock.json`. Core takes one runtime dependency, `decimal.js` (MIT), for decimal arithmetic matching Python's `Decimal` (§4.1). Dependabot gains the `npm` ecosystem for `extension/`, targeting `develop`.
- **The dependency rule is a test:** a meta-guard reads every import in each package and refuses one that points upstream (core importing history, readers or shell; any package importing shell), and refuses any browser global (`window`, `document`, `chrome`, `indexedDB`) in core.

Flow: broker page → content script snapshot → reader → broker view → history records it → core advises → side panel shows it.

## 4. Core

### 4.1 Money and arithmetic
- Money is integer minor units held as `bigint`, with a currency; IDR has 0 minor units, as Python's `IDR = Currency("IDR", 0)` says. `number` never holds money; a meta-guard refuses `number` in core's money and rules modules, as the Python guard refuses `float`.
- Ratios use `decimal.js` configured to 50 significant digits, rounding half-even where Python's `RATIO_PLACES` rounding is half-even, down where Python rounds down (`ratio_down`), so a ported function gives the identical digits (§14.4).
- Every rounding direction is explicit and carried over from the Python function it ports: income rounds down, tax rounds up, and a trade's costs are rounded once to the rupiah against the trader (`fees.py`).

### 4.2 IDX rules
- Lots, ticks, auto-reject bands, the minimum price, holidays, fees and taxes are read from the existing effective-dated files in `packages/steadyhand-idx/src/steadyhand_idx/data/` (`tick_sizes.toml`, `auto_reject.toml`, `holidays.toml`, `fees.toml`). They stay the single source: a build step converts each to JSON in `extension/rules/`, which the bundler embeds in the code (so nothing is fetched at run time, §11), and a test parses every TOML file with Python's reader and the JSON with core's reader and compares every row.
- **New rule file `sessions.toml`**, from `docs/research/t-rules.md` §5 (effective-dated, as the research table gives it). Core reads two facts from it: when a trading day's closing price is final, which is the end of the closing-price matching (16:01:59 WIB in the current table), so a price read from 16:02:00 WIB is that day's close; and when the next trading day's pre-opening starts, after which a page no longer shows that close (§6.2).
- A year with no holiday data refuses, as `is_trading_day` refuses in Python: the extension names the missing year and gives no advice until a release carries it.
- **Fees:** the user picks a preset in Settings. A preset ships for a broker only when the broker's own page states what its quoted rate includes (the existing rule in `fees.toml`); otherwise the user sets `custom`. Each order's fee is an estimate, labelled as one.

### 4.3 The advice day and strategy memory
- Advice is computed for an **advice day**: the trading day whose close the portfolio and watchlist reads show (§6.2). A read during a session gives intraday prices, so it never makes an advice day: the panel shows the last advice day's advice and says when the next close is.
- A strategy keeps memory between advice days, as in Python (buy-and-hold's fixed set, monthly-savings' instalment and months bought, a review strategy's last review). Memory is stored in the extension's storage with the advice day it was written for. Advising again on the same day starts from the memory that day began with, so the advice for a day is the same however often it is asked for (core §6.1 idempotency).
- **Review days** become "the first advice day on or after" the rule's day: dividend-growth's first trading day of the year, high-yield's first trading day of January, April, July and October, momentum-rotation's first trading day of the month. A strategy's first advice day is also a review day, as a run's first day is in Python.
- Unspent cash is never lost: if the user does not follow an order, the next advice day starts from the cash and holdings the broker then shows.

### 4.4 From weights to orders
- Strategies return target weights (core §4.3), ported unchanged in meaning. The sizer and the risk manager turn them into orders, as `CompoundingSizer` and `RiskManager` do: value is cash plus holdings at the advice day's close; buys are sized in whole lots, cut to the cash available to buy (§5.1), cut to the 10% weight cap, and dropped below one lot. Every cut or drop carries the note Python gives it (`limit.cash.cut`, `limit.weight.cut`, `limit.min_lots` and the rest).
- **Flagged holdings:** a held stock the broker marks as suspended or on the Special Monitoring Board, or that Settings excludes, is neither bought nor sold (core §6.1: frozen and flagged), with Python's `trade.frozen` or `trade.excluded` note. Frozen takes precedence over a strategy's sell (ma-trend's, for one leaving the universe).
- **Limit price:** the advice day's close, which is always on a valid tick and, on an ordinary day, inside the next day's auto-reject band, since that close is the band's reference (the exception is in §17). The panel says that a limit at the close may not fill if the price moves.
- **Fees** per order from §4.2, shown beside it, with the stamp duty once for the day's orders as Python charges it.

### 4.5 Notes and the missing list
Every warning is a note with a dotted code, as in Python. Codes that described simulated fills (`fill.*`) are not ported. New codes name what is missing: `missing.page` (with the exact page to open: "open the dividend page for BBRI"), `missing.history` (with the window and how many closes it has), `missing.deposits`, `missing.rules_year`. **A strategy that lacks data for a stock it must judge gives no orders at all**, never advice on partial data (design §4), and lists every gap, not only the first.

## 5. Readers

### 5.1 The broker view
One shape for every broker and every input route:
- **portfolio:** cash available to buy; cash balance (settled and unsettled); per holding: symbol, lots, average price, last price;
- **watchlist:** per stock: symbol, last price;
- **stock detail:** a price chart's series of daily closes and the range it covers, where the page shows one;
- **dividends:** per stock: ex-date, payment date and gross amount per share, and the period the page covers (§7.1), where a page shows them;
- **cash movements:** dated deposits and withdrawals, where a page shows them (decision 18);
- **corporate actions:** splits and their ratios, where a page shows them;
- **flags:** a stock the page marks as suspended or on the Special Monitoring Board.

Every part carries its source (broker, page kind, route) and the instant it was read. A part the page does not show is absent, never zero.

### 5.2 Rules every reader follows
- A reader is a pure function from a snapshot (HTML text, pasted text or file bytes) to one part of the broker view, or a refusal naming what it did not recognise.
- **Fail closed:** an unknown label, a missing column, a changed layout or a number it cannot parse exactly is refused by name. Indonesian formats are parsed exactly (`1.234.567` is one million and more; `1.234,50` is one thousand and more with a decimal comma), and a number whose format is ambiguous in that broker's locale is refused.
- **One test per saved real page**, using pages Shyden saves from his own account, with personal details replaced by a scrubber that a test proves leaves no account number, name or email in the fixture.
- **Each broker reader declares its chart's adjustment** (none, splits, or splits and dividends), established from the broker's documentation or measured on saved pages around a known split and ex-date. A reader whose adjustment is not established refuses its chart (§6.5).
- **Pasted text and export files** go through the reader for that broker's format; each format is its own module with its own saved fixtures.

### 5.3 The first broker (decision 13)
The first reader waits on three things, all outside engineering: an account at POEMS or BIONS, its agreement read for any term on automated reading (the reader is built only if it allows a read-only extension), and saved sample pages of every page kind in §5.1. Nothing else in this spec waits on them: core, history and shell are built against the broker view and a fixture broker. Paste and export formats are each broker's own (§5.2), so they come with that broker's readers.

### 5.4 Freshness
Advice needs the portfolio and the watchlist read on the same advice day (§4.3) and within 30 minutes of each other; otherwise the panel names the one to read again (design §3).

## 6. History

### 6.1 The store
IndexedDB in the extension's own origin, with one object store per kind: closes (stock, day, price, source), chart series (stock, read instant, adjustment, closes), dividends, cash movements, corporate actions, strategy memory, settings. Everything is local; "forget everything" deletes the database and the extension's storage and reads back that both are empty (§11).

### 6.2 What a read records
- A watchlist or portfolio read from 16:02:00 WIB on a trading day until the next trading day's pre-opening records that day's close for each stock (`sessions.toml`, §4.2). A read during a session records nothing as a close.
- A stock detail read records the chart series as shown, with the reader's declared adjustment.
- Dividend, cash-movement and corporate-action reads record each row once, keyed by its own fields, so reading a page twice changes nothing.

### 6.3 A stock's series
A strategy reads a stock's daily closes as one series: the latest chart series read for it, which wins on every day it holds, then the self-recorded closes after the chart's last day. An adjusted chart legitimately differs from raw closes before its latest action, so only the chart's last day is compared: its close must equal the self-recorded close for that day, if one exists; a disagreement drops the self-recorded part and asks for the chart again.

### 6.4 Corporate actions found by price
Self-recorded closes are not adjusted (the #203 lesson). For each pair of self-recorded closes on consecutive trading days, a move larger than the auto-reject band for the earlier close's price tier cannot be a market move. Across a gap of n trading days, the band is applied n times in succession, each step from the price the previous step reached (up for a rise, down for a fall), because a tier can be a percentage or a fixed number of rupiah. A move beyond the band marks a corporate action: that stock's self-recorded closes before it are dropped, and the panel asks the user to open its chart once. The check reads the band rows effective on each day it steps through. A false alarm costs the user one chart read; a missed action would corrupt the series, so the check errs that way.

### 6.5 Total return (decision 17)
ma-trend and momentum-rotation judge a total-return series: the stock's series (§6.3) with every cash dividend in the window, restated in the series' share basis (§6.6), reinvested on its ex-date, the standard factor `1 - dividend / close the trading day before the ex-date` applied to every earlier close. A chart already adjusted for dividends is not adjusted again (§5.2). A stock whose dividends for the window have not been read, or whose series crosses a corporate action without a known ratio, is listed as missing for that strategy.

### 6.6 Dividends restated in today's shares
high-yield, dividend-growth and the income figures read dividends per share in today's shares, restated by every split since (as Python's `_restated_gross` does). Splits come from a broker page that shows them (§5.1). A stock with a corporate action found by price (§6.4) and no known ratio is listed as missing for any figure that crosses it.

## 7. The six strategies

Each keeps its Python or M7 rule; this section states what it reads in the broker view and what it names when it lacks it. The universe is the user's list of symbols in Settings (their LQ45 list, entered or pasted; only today's membership matters for live advice), less the exclusions in Settings and any stock the broker flags (§5.1). Every member must be in the watchlist read; a member missing from it is listed (decision 9).

| Strategy | Rule (unchanged) | Reads | Look-back it needs |
|---|---|---|---|
| buy-and-hold | Fixes its set on its first advice day; never sells; spends cash equally across its set (M3 §6.6). | portfolio, watchlist | none |
| monthly-savings | `instalments` (12, 1-120): spends cash less a reserve for the instalments still due, first advice day of each month (M6 §5). | portfolio, watchlist | none |
| dividend-growth | `min_stocks` 15, `max_stocks` 25, `growth_years` 5; yearly review (M6 §6). | + dividends | `growth_years` + 1 calendar years of dividends per universe stock |
| high-yield | `yield_stocks` 10, `paid_years` 3; quarterly reviews; equal 1/10; too few: cash and `strategy.too_few_qualified` (M7 decision 5). | + dividends | the `paid_years` calendar years before this one, and this year to date, of dividends per universe stock |
| ma-trend | `fast_days` 50 < `slow_days` 200; daily; a slot of 1/N per uptrend stock (M7 decisions 2, 6). | + series, dividends | `slow_days` total-return closes per universe stock |
| momentum-rotation | `momentum_stocks` 10, `momentum_months` 12, `skip_months` 1; monthly reviews (M7 decision 7). | + series, dividends | 23 × `momentum_months` + 1 trading days of total-return closes per universe stock |

The default strategy stays `dividend-growth` (core §8).

### 7.1 Missing versus ineligible
Two different absences, never confused:
- **Missing:** the facts exist at the broker but have not been read (no chart read for the stock, or no dividend read covering the window). The stock is listed with the page to open, and the strategy gives **no orders** until every universe stock it must judge is read, or the user removes the stock from the universe.
- **Ineligible** (M7 decision 4, per window): the facts have been read and show the stock cannot pass, such as a chart whose range starts before the window but whose first close comes after the window's start (the stock was not trading then), or a dividend read covering a year with no dividend. The stock is simply not picked, as in Python.
So every chart and dividend read records the period it covers (the chart's range; the dividend page's date filter or "all history"); a reader that cannot establish the period refuses (§5.2).

### 7.2 The M7 rules, restated
M7 was decided on 2026-10-04 (decisions in git-ignored `.superpowers/sdd/m7-lq45/decisions.md`) but never specified or built, so this section is their home in the repository. "Total-return closes" are §6.5's.
- **high-yield** (`yield_stocks` 10, `paid_years` 3). A stock passes on a review day when it paid a cash dividend, by ex-date, in each of the `paid_years` calendar years before this one. Its yield is its dividends per share with an ex-date in the 365 days up to the advice day, restated in today's shares (§6.6), divided by the advice day's close. At a review it targets the `yield_stocks` passers with the highest yield, ties broken by market and symbol, at 1/`yield_stocks` each, and sells everything else; with fewer passers, the rest stays cash with `strategy.too_few_qualified`. Between reviews it keeps its holdings and puts new cash into its picks, never above 1/`yield_stocks`. Reviews: the first advice day on or after the first trading day of January, April, July and October, and its first advice day.
- **ma-trend** (`fast_days` 50, `slow_days` 200, `fast_days` < `slow_days`). Every advice day, a stock is in an uptrend when the simple average of its last `fast_days` total-return closes is strictly above the average of its last `slow_days` (core §8). N is the number of universe members that day. An uptrend stock not held is targeted at 1/N; a held stock keeps its current weight while its uptrend lasts; new cash goes to uptrend stocks below 1/N, up to 1/N. A downtrend or leaving the universe sells the whole holding. The rest is cash.
- **momentum-rotation** (`momentum_stocks` 10, `momentum_months` 12, `skip_months` 1, `skip_months` < `momentum_months`). A stock's momentum is its total-return change from the close on the last trading day on or before the date `momentum_months` calendar months before the advice day, to the close on the last trading day on or before the date `skip_months` calendar months before it. At a review it targets the `momentum_stocks` highest, ties broken by market and symbol, at 1/`momentum_stocks` each, and sells everything else; with fewer judgeable stocks, the rest stays cash with `strategy.too_few_qualified`, as high-yield gives. Between reviews it keeps its holdings and puts new cash into its picks, never above 1/`momentum_stocks`. Reviews: the first advice day of each calendar month, and its first advice day.
- **No Python reference exists for these three**: their tests are hand-computed examples, one test per case, written from this section before the code.

## 8. Risk and halts (decision 18)

- **The limits stay core §6.1's:** cash only, 10% per stock, one lot minimum, the 5% daily loss limit and the 25% drawdown kill switch, measured on the fund-style unit value (`risk.UnitValue`), so a deposit buys units and never looks like a gain.
- **Deposits and withdrawals** come from the broker's cash-movement page where the reader supports one; otherwise the user types each one into the panel (date and amount). A typed entry is shown as typed.
- **The unit value is taken only from after-close reads** (§6.2), so intraday swings never trigger a halt.
- **Daily loss:** judged against the previous trading day's unit value when it was read. When the previous trading day has no read, the fall since the latest earlier read is judged against the same 5% limit and the note gives the span. That is stricter than one day, never looser. (A default for Shyden to confirm, listed at the end.)
- **The first after-close read opens the unit value**, as a run's first day does in Python; no halt is judged before it.
- **A halt that cannot be judged stops buy advice:** until the cash-movement record covers the time since the last read, the panel lists `missing.deposits` and gives sell orders only. The record covers it when the broker's cash-movement page has been read for that span, or, on the typed route, when the user has entered every deposit and withdrawal since that read or answered "none" to the panel's question naming the span.
- **A halt** stops all buy advice until the user resumes it in the panel by typing the strategy's name, as `resume` requires in Python; the resume and its time are recorded. Resume is refused while a fact the halt needs is missing (such as `missing.deposits`), as core §6.1 refuses to resume over stale data.

## 9. Income goal (decision 19)

- **Progress:** the holdings' monthly run rate after the 10% final dividend tax (`fees.toml` `dividend_tax`), against the target the user sets, as Python's `run_rate` and `goal_progress` compute it: each holding's dividends per share over the trailing 365 days, restated in today's shares (§6.6), times the shares held.
- **Payment calendar:** which months the holdings paid in over the trailing year, as `payment_calendar` gives it.
- A holding whose dividends for the window have not been read is listed as missing, and the goal shows no figure until every holding is covered.
- Later stories, filed now: income received; the projection ("projection, not a promise"); the dividend tax-exemption claims.

## 10. The extension

### 10.1 Manifest V3
- **Permissions:** `sidePanel` and `storage`, nothing else. **Host access:** the first broker's exact web-platform origins, declared as the content script's `matches`, and nowhere else.
- **Content security policy** for extension pages: `script-src 'self'; object-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`. Chrome refuses to load an extension whose policy it rejects, so the Playwright load (§14.3) proves Chrome accepts this one.
- No remote code, no `eval`, no `externally_connectable`, no web-accessible resources.

### 10.2 The content script
Its whole job: when the page loads, and when the panel asks, it sends the panel a snapshot (the URL and `document.documentElement.outerHTML`) through `chrome.runtime` messaging. It parses nothing, changes nothing, listens to no input and holds no state. All reading happens in the panel (§5), so the code that runs inside the logged-in broker page stays as small as it can be.

Readers need `DOMParser`, which an extension service worker does not have, so pages are read and recorded only while the side panel is open beside the broker tab (decision 15). A snapshot sent with no panel open has no receiver; the content script expects that case and drops it, and the panel's History tab says recording happens only while it is open.

### 10.3 The side panel
- **Advice:** each order (buy or sell, stock, lots, limit price, estimated fees, the strategy's reason), income-goal progress, warnings, and the missing list with the exact page to open; the advice day it is for; "Read this page" for a single-page broker app that changes page without reloading.
- **Settings:** strategy and its settings, income goal, risk limits, fee preset, the universe list, exclusions, typed deposits and withdrawals.
- **History:** what is recorded per stock (days, chart reads, dividends) and "forget everything".
- **Lessons:** §13.
- **The disclaimer** is always visible: core §9.8's text, written once as a constant, and the line "steadyhand computes what the strategy you chose implies; the choice and the orders are yours" (§12.3).
- **Paste and import:** a text box and a file picker feeding §5.2's readers; the file never leaves the panel.

## 11. Security (decision 12)

Every rule has a check that goes red, and every check is proved by planting the forbidden thing and watching it fail.

| Rule | Check |
|---|---|
| Least permission | A test compares the built `manifest.json`'s permissions, host matches and CSP to the exact lists in §10.1. |
| Nothing leaves | A scan of every built bundle refuses `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, `sendBeacon`, `RTCPeerConnection`, `importScripts`, dynamic `import(` and `new Worker(`; the CSP's `connect-src 'none'` backs it at run time; a Playwright test opens the panel with request logging on and finds no request beyond the extension's own files, with a liveness control proving the logger saw those. |
| Read only | The scan also refuses, in the content script bundle: `click`, `submit`, `requestSubmit`, `dispatchEvent`, `focus`, `blur`, any assignment to `value`, `innerHTML`, `outerHTML`, `textContent` or `checked`, and `addEventListener` for input events. A Playwright test loads a fake broker page that records every event and DOM mutation and asserts zero after a read, with a planted mutation proving the recorder works. |
| No remote code | The scan refuses `eval`, `new Function`, `setTimeout` or `setInterval` with a string, and any `http:` or `https:` URL in a script `src`. |
| Local data only | "Forget everything" is tested by writing every store, pressing it, and reading back empty. |
| Supply chain | Every `uses:` pinned to a SHA with its version comment, Dependabot covering `npm` and `github-actions`, both asserted by the supply-chain test as the Python one does; `npm audit` with no findings in CI. |

The scan reads the built JavaScript through a tokenizer, not a regex, so a forbidden name inside a string or comment is not mistaken for code and a forbidden call written another way (`el["click"]()`) is caught. Its liveness counts the call sites it judged, with a recorded floor (§14.2).

## 12. CI and release

### 12.1 CI
- The `ci.yml` jobs gain `extension`: install, lint, `tsc --noEmit`, Vitest with coverage, the meta-guards, the build, the security scan, Playwright with the built extension, the parity harness (§14.4).
- **Develop's deploy** becomes: build the extension zip and attest its build provenance (GitHub's `actions/attest-build-provenance`). The Python TestPyPI `publish-dev` job is retired (design §4).
- **The docs-only fast path** (Shyden's global rule): steadyhand's CI has none. Its own ticket measures the current CI first (jobs per PR, minutes per run) and adds it before other CI work in this epic.
- The scheduled `yahoo-shape.yml` checks a data source the extension no longer uses: it is disabled with the retirement of `publish-dev`. (A default for Shyden to confirm.)

### 12.2 Release
- **Reproducible:** the same source builds a byte-identical zip; CI builds twice and compares.
- **Chrome Web Store verified uploads:** uploads signed with our key (developer.chrome.com/blog/verified-uploads-cws, from 7 May 2025). Signing and upload happen only in a GitHub release environment that needs Shyden's approval, from a reviewed tag on `main`, with provenance attested.
- **A pinned GitHub release zip** for users who want no automatic update.
- **Shyden's admin part:** the Chrome Web Store developer account, hardware-key two-factor on its Google account, the signing key held only in the release environment, and the release environment's required reviewer.

### 12.3 Free, and never "we recommend" (decision 16)
steadyhand earns nothing: no ads, no broker referral or affiliate fees, no paid tier, no donations linked to its use. The user chooses the strategy and its settings; steadyhand computes what that strategy implies. The words "recommend", "recommendation" and "we suggest" never appear in shipped text, and a test refuses them in every bundle and lesson.

## 13. Lessons

The existing lessons are carried over as written, except:
- **Left out**, because they describe what the extension does not do: `backtest.basics`, `backtest.data_gaps`, `backtest.report`, `risk.backtests_mislead`, `idx.restored_prices`, `idx.survivorship`, `orders.at_the_open`, `paper.daily_run`, `paper.halts_and_switching`, `paper.settings`, `paper.status_and_reports`; and, until their later stories, `income.received`, `income.projection`, `income.growth`, `tax.exemption`.
- **Rewritten** for the extension: the 13 kept lessons whose text names backtests, paper trading, Yahoo, the CLI or `steadyhand.toml` (a case-insensitive search of every lesson on 2026-10-06): `costs.trading`, `idx.sessions`, `idx.universe`, `orders.not_tradable`, `risk.drawdown`, `risk.returns`, `shares.prices`, `start.explanations`, `start.welcome`, `strategies.buy_and_hold`, `strategies.dividend_growth`, `strategies.holding_cash`, `strategies.monthly_savings`.
- **New:** high-yield, ma-trend and momentum-rotation (M7's story S5), "reading your broker" (pages, freshness, the missing list, recording only while the panel is open), "total return", and "limit prices" (why the limit is the close, and when the broker may refuse it).

A test refuses any shipped lesson whose text names backtests, paper trading, Yahoo, a CLI command or `steadyhand.toml`, and every note code the core can raise has a lesson that explains it.

## 14. Testing

### 14.1 Discipline
TDD throughout: each story's tests are written first and seen to fail on their own assertions. One test per case (`test.each`, never a population looped inside one test). No retries anywhere: Playwright's `retries` is 0 and a test asserts it. 100% branch coverage for core, readers and history.

### 14.2 Meta-guards for TypeScript
Re-established from Shyden's global rules before the first feature story:
- **one-test-per-case:** refuses a loop inside a test body that renders, navigates or changes state;
- **floorless-searches:** every absence assertion over a discovered population checks that population's recorded floor in the same test;
- **floors:** one recorded file, checked for equality, raised only by a recorder that never runs in CI;
- **source text:** every guard reading source strips comments with one shared tokenizer first;
- **import direction** (§3) and **no `number` for money** (§4.1).
Each guard carries the population it judged inside its verdict, a floor at the measured figure, an independent cross-check, and a mutation per form that goes red.

### 14.3 Browser tests
Playwright launches Chromium with the built extension. Fixture broker pages, served locally, stand in for the broker; the real saved pages feed reader unit tests only. Journeys: read portfolio and watchlist, get orders; a missing page named; paste a portfolio; type a deposit; a halt and its resume; forget everything.

### 14.4 Parity with Python
Until the port is done, a CI step generates cases from a fixed seed (universe, closes, dividends, holdings, cash, memory, settings), runs Python's strategy, sizer and risk manager and TypeScript's on each, and requires identical orders, notes and memory. It covers buy-and-hold, monthly-savings, dividend-growth, sizing, risk and the income run rate. The step is removed when the port is finished, with Shyden's agreement.

## 15. Old code and tickets

- The Python packages stay in the repository untouched; the backtester, paper trading and the Yahoo layer are no longer developed.
- After this spec is approved: #160, #161, #162, #200, #203 and #207 are closed as not planned, each pointing to #214; #203's WIP branch stays local and unpushed; `publish-dev` is retired as §12.1 says.
- `main` still has no release; the first release is the extension's.

## 16. Stories

Each is filed with full acceptance criteria and an Estimate scored against closed work when this spec is approved. The points below are a guess, labelled as one: 105 in all.

| # | Story | Sections | Guess |
|---|---|---|---|
| 1 | Docs-only CI fast path, measured first | §12.1 | 3 |
| 2 | Workspace, toolchain, the extension CI job, develop's deploy (zip and attestation), `publish-dev` and `yahoo-shape.yml` retired | §3, §12.1 | 8 |
| 3 | TypeScript meta-guards and floors | §14.1, §14.2 | 8 |
| 4 | Core money, IDX rules with the TOML-to-JSON check, `sessions.toml`, the advice day | §4.1, §4.2, §4.3 | 8 |
| 5 | Broker view, Indonesian number parsing, freshness, the fixture broker, the scrubber | §5.1, §5.2, §5.4 | 5 |
| 6 | Sizing, risk limits, flagged holdings, notes and the missing list, and the parity harness | §4.4, §4.5, §14.4 | 5 |
| 7 | Strategy memory; buy-and-hold, monthly-savings and dividend-growth with parity; missing versus ineligible | §4.3, §7, §7.1 | 8 |
| 8 | History store, closes, series, corporate actions found by price, total return, restated dividends | §6 | 8 |
| 9 | high-yield | §7.2 | 5 |
| 10 | ma-trend | §7.2 | 5 |
| 11 | momentum-rotation | §7.2 | 5 |
| 12 | Halts with deposits, typed entry and resume | §8 | 5 |
| 13 | Income goal progress and calendar | §9 | 3 |
| 14 | Shell: manifest, content script, side panel, settings, forget everything | §10 | 8 |
| 15 | Security scan, the "recommend" wording test, the fake-broker browser tests | §11, §12.3, §14.3 | 5 |
| 16 | First broker readers: every page kind, paste and export | §5.2, §5.3 | 8 |
| 17 | Lessons | §13 | 3 |
| 18 | Release: verified upload, release environment, provenance, reproducible build, pinned zip | §12.2 | 5 |

Later stories, filed now without a release date: Indonesian; screenshots; income received; the projection; the exemption claims; each further broker.

## 17. Risks

- **The broker page may draw its chart on a canvas**, with no numbers in the HTML. Then ma-trend and momentum-rotation can only use self-recorded closes: ma-trend's 200 trading days take about ten months of after-close reads, and momentum-rotation's 277 (23 × 12 + 1) about thirteen. The first sample pages settle it; if so, Shyden is asked before the strategies ship.
- **The broker's agreement may forbid automated reading.** Then that broker gets the paste and export route only (decision 4), and the other broker is tried.
- **The broker may show only one cash figure**, not both cash available to buy and cash balance. The reader then refuses until Shyden decides what that figure stands for.
- **The broker may show no split ratios.** Then a stock with a split inside a window stays missing for every figure that crosses it (§6.6), and Shyden is asked how to supply ratios.
- **OJK's view of a free tool that computes specific orders is unsettled** (decision 16, accepted).
- **A limit at the close can be rejected** on a day whose reference is not the previous close, such as a rights issue's ex-date (#203's finding). The broker refuses the order and nothing fills; steadyhand does not know rights ex-dates (#203 is closed with this spec), so the "limit prices" lesson says so (§13).
- **Pace:** every closed story so far was Python; the TypeScript stack's pace is unmeasured until the first stories close.

## Defaults for Shyden to confirm

These were not asked in the brainstorm. Each points to the section that gives its reason, and each is one line to change.
1. **The limit price is the advice day's close** (§4.4).
2. **Daily loss across a gap in reads** is judged on the whole gap against the 5% limit (§8).
3. **`yahoo-shape.yml` is disabled** with `publish-dev` (§12.1).
4. **Freshness:** 30 minutes between portfolio and watchlist reads (design §3, accepted then as a default).
5. **Three details the M7 decisions left unstated** (§7.2), each filled from how `dividend-growth` already works in Python: high-yield breaks ties by market and symbol; high-yield and momentum-rotation sell what they no longer pick at a review; between reviews, both put new cash into their picks up to their equal share.

## Scope decisions (amending the core spec)

- **SD1, core §1.3 "No unofficial broker access":** the extension reads the page the user has open, read-only, as decisions 4 and 11 chose. It never automates, clicks, submits or calls a broker's private interfaces, which keeps the boundary's purpose. The line becomes "never automates a broker's app or web page, and never calls its private interfaces; it may read the page the user has open".
- **SD2, core §6.1:** "until `steadyhand-idx resume`" becomes "until resumed in the side panel" (§8).
- **SD3, core §7:** the first release carries goal progress and the payment calendar only (decision 19).
- **SD4, core §8 and §13:** the first release's strategy library is the six of §7 (decision 14); M7-M10 are replaced by this spec's stories. Core §8's waves 3 and 4 (strategies 7-11: dual-momentum, low-volatility, breakout, rsi-reversion, dividend-capture) are outside the first release; whether they come back as later stories is Shyden's call, asked with this spec.
- **SD5, core §9.2-§9.6:** Yahoo, the cache, `steadyhand.toml` and the CLI are not used by the extension; the Python packages keep them.

When this spec is approved, the core spec is edited to match, with a line in its review log.

## Spec review log

- **Pass 1 (2026-10-06):** mechanical: every section the spec cites exists (internal and core, M3, M6); every Python name it ports was read in the code (`UnitValue`, `RiskLimits` defaults, `ratio_down`, `RATIO_PLACES`, `_restated_gross`, `run_rate`, `goal_progress`, `payment_calendar`, `is_trading_day` raising for a year with no holiday data, `IDR`, the note codes, the registry's settings and defaults); the rule files exist except `sessions.toml`, which the research named but nobody built; the story points were summed. 8 findings, all fixed: IDR's minor units are a constant, not a rule; costs round once against the trader, not "up"; high-yield's look-back misstated; the gap band must step through tiers (percent or fixed rupiah); the points total 100, not 99; the rewrite list of lessons was guessed, now derived from a search of every lesson (13, not 4); the M7 rules lived only in a git-ignored file, so §7.2 now states them in full, with three gaps listed as defaults; M7's per-window eligibility had been turned into a blocker, so §7.1 separates missing from ineligible. Also: core §8's waves 3-4 were unaccounted for (SD4).
- **Pass 2 (2026-10-06):** full read. 8 findings, all fixed: `sessions.toml` must also give the pre-opening start (§4.2); comparing a chart with raw closes on every shared day would refuse every dividend-adjusted chart, so only the chart's last day is compared (§6.3); dividends must be restated in the series' share basis before reinvesting (§6.5); nothing opened the unit value (§8); "the record covers the span" was undefined for typed deposits (§8); "resume refused while the cause is present" misread core §6.1, which refuses over stale data, not over the drawdown itself; flagged holdings (core §6.1 frozen) were missing (§4.4); readers need `DOMParser`, which a service worker lacks, so recording happens only with the panel open (§10.2). Also a new risk: a limit at the close is rejected on a rights ex-date (§17).
- **Pass 3 (2026-10-06):** mechanical: every section mapped to a story (§16 gains a Sections column). 4 findings, all fixed: the broker view, number parsing, freshness, the fixture broker and the scrubber had no story (new story 5; the total becomes 105); the parity harness and the "recommend" wording test had no owner (stories 6 and 15); §5.3 said the paste reader comes before the broker, though §5.2 makes paste formats per broker; §17 cited a "limit prices" lesson that §13 did not list.
- **Pass 4 (2026-10-06):** full read. 3 findings, all fixed: the panel's disclaimer line said "it does not recommend", which §12.3's wording test would refuse; frozen holdings against ma-trend's sell on leaving the universe had no precedence (§4.4); a broker with no split-ratio page left §6.6 with no route, now a named risk (§17).
- **Pass 5 (2026-10-06):** mechanical (every section reference resolves; no placeholder; the points total 105) and a full read. 2 findings, fixed: the canvas risk gave ma-trend's record time only, not momentum-rotation's 277 trading days; nothing said how rule data reaches the code without a fetch, which §11's scan refuses (§4.2, now embedded at build). Python's `MarketView` is built directly in four existing test files, so the parity harness (§14.4) can call strategies without the engine.
- **Pass 6 (2026-10-06):** mechanical (references, placeholders, 18 stories totalling 105, all Fibonacci) and a full read. 3 findings, fixed: "core §13 items 6-10" named items that do not exist (core §13 has 7: item 6 is the strategy waves, item 7 the release); §1.1 credited the order-API survey to decision 1, not 2; §4.4 said the limit is "always" inside the band, against §17's rights-issue exception.
- **Pass 7 (2026-10-06):** mechanical (as pass 6) and a full read. 1 finding, fixed: momentum-rotation's "too few" note was unnamed; it is `strategy.too_few_qualified`, as M7 decision 7's "cash + note" and high-yield's.
- **Pass 8 (2026-10-06):** mechanical (as pass 6) and a full read. 1 finding, fixed: the defaults' preamble called every default "the most cautious reading", which is untrue of disabling `yahoo-shape.yml` and of the M7 gaps filled from `dividend-growth`.
- **Pass 9 (2026-10-06):** mechanical (as pass 6: no dangling reference, no placeholder, 18 stories totalling 105, all Fibonacci) and a full read. **0 findings. Loop closed.**
