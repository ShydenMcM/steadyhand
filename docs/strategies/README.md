# Strategy guides

> steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.

The guides have moved into the `steadyhand` package, so they ship with it:
[`packages/steadyhand/src/steadyhand/strategies/guides/`](../../packages/steadyhand/src/steadyhand/strategies/guides/).
Each registered strategy has one, in plain English: what it does, why people use it, when it
tends to do badly, its risks, how often it trades and the settings you can change.

With steadyhand-idx installed, `steadyhand-idx strategies` lists the strategies, and
`steadyhand-idx explain <strategy>` prints one guide.
