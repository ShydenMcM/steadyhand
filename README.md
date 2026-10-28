# steadyhand

Self-hosted, open-source toolkit for building a **dividend income portfolio**, starting with the Indonesia Stock Exchange (IDX).

> steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.

## Status

**Early development, and changing direction.** steadyhand is becoming a Chrome extension: epic #214,
with its approved design in
[`docs/superpowers/specs/2026-10-06-broker-view-extension-design.md`](docs/superpowers/specs/2026-10-06-broker-view-extension-design.md).
The extension's TypeScript workspace, its CI and its dev build are in place in
[`extension/`](extension/). Its advice logic, broker readers and side panel are being built story by
story (#222 to #245), and nothing has been released yet.

The Python packages are built: the engine library, the IDX rules, the backtester, paper trading,
income reporting, the lesson catalogue and the command line (`steadyhand-idx`). They stay in the
repository unchanged and are no longer developed. They are the reference the extension's TypeScript
port is checked against. Their design is in
[`docs/superpowers/specs/2026-09-24-steadyhand-core-design.md`](docs/superpowers/specs/2026-09-24-steadyhand-core-design.md).

## What it will be

- **A Chrome extension beside your broker.** You open your broker's web platform as usual. steadyhand
  reads what the page shows and records it on your own machine. In a side panel beside the broker
  tab, it shows what your chosen strategy implies now: which stock to buy or sell, how many lots, at
  what limit price, what it costs and why. It also shows your progress towards an income goal, and
  any risk alerts. Where it lacks a fact, it names the page to open rather than guessing.
- **You place every order yourself**, by hand or with your broker's own automatic-order feature.
  steadyhand never places, changes or cancels an order, and nothing it reads leaves your machine.
- **Six strategies, one broker and English to start:** buy-and-hold, monthly-savings, dividend-growth,
  high-yield, ma-trend and momentum-rotation; one broker's web platform, with each later broker a
  reader of its own; Indonesian later.
- **Lessons for first-time investors**, carried over from the Python packages and rewritten for the
  extension.
- **Free**, with no ads, broker referral fees or paid tier.
- **The Python packages, kept as they are.** `steadyhand` (the market-neutral engine) and
  `steadyhand-idx` (IDX rules, Yahoo Finance `.JK` data, backtesting, paper trading and the command
  line) remain the reference for the port. Backtesting and paper trading stay there.

## What it will never be

A hosted service, a signal seller, or anything that touches other people's money. Real orders are placed by you, in your own broker app.

## Dev builds

Every merge into `develop` that passes CI deploys to dev: the `deploy-dev` job in
[`.github/workflows/ci.yml`](.github/workflows/ci.yml) builds the Chrome extension, attests and
verifies the zip's build provenance, and keeps the zip with that run for 90 days. There is no hosted
dev site, because steadyhand is [never a hosted service](#what-it-will-never-be).

## Setting up a clone

Run these once, from the repository root, after cloning:

```sh
uv sync --locked
(cd extension && npm ci --ignore-scripts)
git config core.hooksPath .githooks
```

The last line installs the git hooks tracked in `.githooks/`. Its `pre-push` runs ruff's lint
and format checks, mypy, and the extension's lint, format and type checks, and a check that fails
stops the push, named. It runs no test suite: run the unit suites by hand before each push
(`uv run --locked pytest`, and `npm test` in `extension/`); CI runs every other suite.

Its `commit-msg` refuses a message without its `Gaps checked:` section (a `- Before:`, an
`- After:` and a `- New passes:` entry), unless the commit holds only `.md` files. A git hook can
be skipped, so CI's `gaps-checked` job is the gate: it judges every commit of a pull request, and
every commit a push lands on `develop` or `main`.

## Contributing

Every sentence a report says beyond its figures, and every figure it shows, carries a stable key,
and each key is explained by exactly one lesson in `packages/*/src/*/training/lessons/en/`. A pull
request that adds a note key or a term key must add its lesson in the same pull request: CI fails
until it does. A lesson that states an IDX rule value copies it from a research document under
`docs/research/` and names that document in its `sources`.

steadyhand runs the versions every Shyden Labs project runs, the newest any of them uses. Python
is pinned once, to an exact patch version, in `.python-version`: uv reads it locally and in every
CI job, and no workflow names a Python of its own. CI runs on `ubuntu-26.04`, and the extension
needs Chrome 119 or later (`MINIMUM_CHROME` in `extension/build.ts`, which says why). To move
Python, change `.python-version` and follow `tests/guards/test_versions.py`, which names every
place that must follow it.

## Licence

[Apache-2.0](LICENSE)
