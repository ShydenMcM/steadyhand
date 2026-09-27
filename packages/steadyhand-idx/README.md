# steadyhand-idx

The Indonesia Stock Exchange (IDX) distribution of steadyhand: IDX trading rules, Yahoo Finance `.JK` data, paper trading and a CLI.

> steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.

It ships a course for first-time investors, with lessons on how IDX works, its costs and its
taxes.

## Getting started

```sh
steadyhand-idx init                  # accept the disclaimer, choose how much is explained
steadyhand-idx learn                 # list the course
steadyhand-idx learn start.welcome   # read one lesson
steadyhand-idx training some         # explain less: off, new, some or experienced
```

`init` writes `steadyhand.toml` into the data directory, which is `--data-dir`, else
`$STEADYHAND_HOME`, else `$XDG_DATA_HOME/steadyhand-idx`, else `~/.local/share/steadyhand-idx`.
Each setting in it has a comment saying what it does. A script answers `init`'s questions with
`--training` and `--exemption`, and pipes in the words `I understand`.

## Backtesting

Set your starting cash, your income goal and your LQ45 file in `steadyhand.toml` first.
steadyhand ships no LQ45 lists: [docs/lq45-members.md](https://github.com/ShydenMcM/steadyhand/blob/develop/docs/lq45-members.md)
says where IDX publishes each one. An `exclusions.csv` beside it, if you keep one, lists stocks
you never want held.

```sh
steadyhand-idx backtest --from 2021-02-01 --to 2022-01-31              # your strategy beside buy-and-hold
steadyhand-idx compare --from 2021-02-01 --to 2022-01-31 buy-and-hold  # several strategies, one table
```

Each writes a Markdown summary and a CSV into `reports/` in the data directory, replacing the
files of an earlier run over the same dates. Exit codes: 0 success, 2 a usage or configuration
error, 3 stopped safely because data was missing or stale, 1 anything unexpected (run again with
`--debug` for the details).

Early development. See the [project repository](https://github.com/ShydenMcM/steadyhand).
