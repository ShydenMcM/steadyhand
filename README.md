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

## Contributing

Every sentence a report says beyond its figures, and every figure it shows, carries a stable key,
and each key is explained by exactly one lesson in `packages/*/src/*/training/lessons/en/`. A pull
request that adds a note key or a term key must add its lesson in the same pull request: CI fails
until it does. A lesson that states an IDX rule value copies it from a research document under
`docs/research/` and names that document in its `sources`.

## Licence

[Apache-2.0](LICENSE)
