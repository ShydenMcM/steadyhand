# steadyhand

Self-hosted, open-source toolkit for building a **dividend income portfolio**, starting with the Indonesia Stock Exchange (IDX).

> steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.

## Status

**Design phase. There is no usable code yet.** The approved design for the first sub-project is in
[`docs/superpowers/specs/2026-09-24-steadyhand-core-design.md`](docs/superpowers/specs/2026-09-24-steadyhand-core-design.md).

## What it will be

- `steadyhand`: a market-neutral Python engine library covering strategies, a simulated broker, risk controls, a backtester and income tracking.
- `steadyhand-idx`: the IDX distribution, with IDX trading rules, Yahoo Finance `.JK` data, paper trading, a CLI, and an income goal tracker that shows when dividends could cover a monthly target.

## What it will never be

A hosted service, a signal seller, or anything that touches other people's money. Real orders are placed by you, in your own broker app.

## Licence

[Apache-2.0](LICENSE)
