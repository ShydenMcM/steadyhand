import { expect, test } from "vitest";
import { RuleDecimal } from "../src/ratio.ts";
import { restatedGross } from "../src/restated.ts";
import fixture from "./parity-restated.json" with { type: "json" };

// The parity harness for dividends restated in today's shares (#232 AC4, spec §6.6): seeded
// dividends, splits of the stock and of another, and days read for, that Python's
// `_restated_gross` answered (`scripts/core_fixtures.py`). Core's must give the same rupiah.

interface Case {
  readonly name: string;
  readonly exDate: string;
  readonly grossPerShare: string;
  readonly shares: string;
  readonly splits: readonly { symbol: string; exDate: string; from: string; to: string }[];
  readonly asOf: string;
  readonly gross: string;
}

const CASES: readonly Case[] = fixture.cases;

test(`the harness compares ${CASES.length.toString()} restated dividends from seed ${fixture.seed}`, () => {
  expect(CASES.length).toBeGreaterThan(0);
});

test.each(CASES)("core restates $name as Python does", (parity) => {
  const gross = restatedGross(
    {
      symbol: "BBCA",
      exDate: parity.exDate,
      paymentDate: parity.exDate,
      grossPerShare: new RuleDecimal(parity.grossPerShare),
    },
    BigInt(parity.shares),
    parity.splits.map((split) => ({ ...split, from: BigInt(split.from), to: BigInt(split.to) })),
    parity.asOf,
  );
  expect(gross.amount.toString(), `seed ${fixture.seed}, ${parity.name}: ${JSON.stringify(parity)}`).toBe(
    parity.gross,
  );
});
