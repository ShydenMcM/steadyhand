# steadyhand

Self-hosted, open-source toolkit for building a **dividend income portfolio**, starting with the Indonesia Stock Exchange (IDX).

> steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.

## Status

**Early development.** The engine library, the IDX rules, the backtester, income reporting, the
lesson catalogue and the command line (`steadyhand-idx`: `init`, `backtest`, `compare`,
`strategies`, `explain`, `learn` and `training`) are built; paper trading comes next. The approved design
for the first sub-project is in
[`docs/superpowers/specs/2026-09-24-steadyhand-core-design.md`](docs/superpowers/specs/2026-09-24-steadyhand-core-design.md).

## What it will be

- `steadyhand`: a market-neutral Python engine library covering strategies, a simulated broker, risk controls, a backtester and income tracking.
- `steadyhand-idx`: the IDX distribution, with IDX trading rules, Yahoo Finance `.JK` data, paper trading, a CLI, and an income goal tracker that shows when dividends could cover a monthly target.
- A course for first-time investors, and plain-English explanations under each command's output at the level you choose, or none. `steadyhand-idx learn` shows the lessons, which ship inside both packages.

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
