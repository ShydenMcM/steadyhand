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

Early development. See the [project repository](https://github.com/ShydenMcM/steadyhand).
