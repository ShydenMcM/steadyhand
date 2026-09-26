# Supplying your own LQ45 list

> steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.

steadyhand-idx picks stocks from the **LQ45**, IDX's list of 45 large, liquid stocks, as it stood on each date. It does **not** ship those lists. IDX's Terms of Use bar redistributing its data for a commercial purpose without written permission, and steadyhand's Apache-2.0 licence would pass on rights the project does not hold (`docs/research/t-lq45.md` §5). So you build the file yourself, from IDX's own documents, and it stays on your machine. steadyhand never downloads anything from idx.co.id.

## Where the file goes

Put it in your steadyhand data directory and point the config at it:

```toml
[universe]
lq45_members = "lq45_members.toml"   # relative to the data directory
```

If the file is missing, steadyhand stops and names this key.

## The format

One record per IDX document, each carrying the **full** list of 45 in force from its `effective` date. Membership on a date is the latest record whose `effective` is on or before it, so a record ends where the next begins and two records can never overlap.

```toml
schema = 1

[[record]]
effective = 2026-05-04              # the first trading day the list applies
announced = 2026-04-24              # the date on IDX's announcement
source = "Peng-00067/BEI.POP/04-2026"
kind = "review"                     # "review", or "replacement" for a mid-period change
members = ["AADI", "ADMR", "ADRO"]  # all 45 four-letter codes; shortened here
```

The loader refuses a record that does not have exactly 45 different four-letter codes, whose `announced` date is after its `effective` date, or that is out of order.

## Where IDX publishes each list

- **Reviews from 2024 on:** IDX announces each review as an announcement numbered `Peng-…/BEI.POP/…`, titled *Evaluasi Mayor* or *Evaluasi Minor Indeks LQ45*, on the announcements page of idx.co.id. The announcement gives the exact effective day.
- **Earlier reviews:** the same announcements (`Peng-…/BEI.OPP/…` before 2019), and IDX's *IDX LQ45* fact-sheet booklets for each period. `docs/research/t-lq45.md` §3 lists the document for every review from February 2016 to November 2025, and which ones were found.
- Before 2024 the documents name the month, not the day: use the first IDX trading day of that month.
- IDX's Terms ask that you cite the source and the date you accessed it when you quote a list. The `source` field is there for that.

## Gaps and survivorship bias

A backtest refuses to start before your first record, and names the first date it can start on. One that runs across two records more than one review apart prints a **survivorship-bias warning**. Reviews were every six months until January 2024 and every three months from May 2024. A gap means stocks that joined and left the LQ45 inside it never appear in the backtest, so its results look better than a real investor's would have. Five reviews between 2016 and 2025 have no primary list anyone has found (`t-lq45.md` §3).

## Exclusions

`exclusions.csv`, also in the data directory and also yours, lists stocks steadyhand must never buy, and freezes them if held. Use it for stocks on IDX's Special Monitoring Board (Papan Pemantauan Khusus), which Yahoo cannot report, or any stock you choose to avoid:

```csv
symbol,from,to,reason
ABCD,2024-01-02,2024-06-28,Special Monitoring Board
WXYZ,2025-01-02,,I do not want to own it
```

`to` is inclusive and may be left empty. Every row needs a reason, which the daily report shows. No file means no exclusions.
