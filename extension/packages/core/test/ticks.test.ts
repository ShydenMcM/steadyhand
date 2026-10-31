import { expect, test } from "vitest";
import shipped from "../rules/tick_sizes.json" with { type: "json" };
import { RulesFileError, UnsupportedDateError } from "../src/rules-file.ts";
import {
  isValidPrice,
  parseSettlement,
  parseTicks,
  roundDown,
  roundUp,
  tickFor,
  type TickRow,
} from "../src/ticks.ts";

// Ported from Python's tests/idx/test_ticks.py, one test per case: the reading cases (#223) and
// the tick arithmetic (#224).

type Document = typeof shipped & Record<string, unknown>;

/** A fresh copy of the shipped document, to change one value of. */
const documentCopy = (): Document => structuredClone(shipped);

/** The first ticks row of `document`, with its tiers as plain values to change. */
const firstRow = (document: Document): Record<string, unknown> & { tiers: unknown[] } => {
  const [first] = document.ticks;
  if (first === undefined) {
    throw new Error("the shipped tick table has no row");
  }
  return first;
};

test("every row of the shipped ticks is read as the file states it", () => {
  const read = parseTicks(shipped);
  expect(
    read.entries.map(([from, row]: readonly [string, TickRow]) => ({
      from,
      source: row.source,
      lot_size: String(row.lotSize),
      tiers: row.tiers.map((tier) => ({
        from_price: String(tier.fromPrice),
        tick: String(tier.tick),
      })),
    })),
  ).toEqual(shipped.ticks);
});

test("every row of the shipped settlement is read as the file states it", () => {
  const read = parseSettlement(shipped);
  expect(read.entries.map(([from, days]) => [from, String(days)])).toEqual(
    shipped.settlement.map((row) => [row.from, row.trading_days]),
  );
});

test("the table is verified from 13 March 2020", () => {
  expect(parseTicks(shipped).first).toBe("2020-03-13");
  expect(() => parseTicks(shipped).on("2020-03-12")).toThrow(
    /tick_sizes\.json \[ticks\] has no verified row for 2020-03-12/u,
  );
});

test("the lot is 100 shares", () => {
  expect(parseTicks(shipped).on("2026-10-30").lotSize).toBe(100n);
});

test("settlement is T+2 from 26 November 2018", () => {
  const settlement = parseSettlement(shipped);
  expect(settlement.on("2018-11-26")).toBe(2n);
  expect(() => settlement.on("2018-11-25")).toThrow(UnsupportedDateError);
});

test("a planted changed row goes red: a tier boundary off its ticks", () => {
  const document = documentCopy();
  firstRow(document).tiers[2] = { from_price: "501", tick: "5" };
  expect(() => parseTicks(document)).toThrow(
    new RulesFileError(
      "tick_sizes.json [[ticks]] row 1: the tier boundary 501 must be a multiple of both " +
        "ticks around it (2 and 5)",
    ),
  );
});

test.each([
  [[], "the first tier must start at a price of 1"],
  [[{ from_price: "2", tick: "1" }], "the first tier must start at a price of 1"],
  [
    [
      { from_price: "1", tick: "1" },
      { from_price: "1", tick: "1" },
    ],
    "tiers must rise, got 1 after 1",
  ],
  [
    [
      { from_price: "1", tick: "2" },
      { from_price: "201", tick: "1" },
    ],
    "the tier boundary 201 must be a multiple of both ticks around it (2 and 1)",
  ],
])("bad tiers %j are refused", (tiers, message) => {
  const document = documentCopy();
  firstRow(document).tiers = tiers;
  expect(() => parseTicks(document)).toThrow(
    new RulesFileError(`tick_sizes.json [[ticks]] row 1: ${message}`),
  );
});

test("a tier with an unknown key or a zero tick is refused, naming the tier", () => {
  const document = documentCopy();
  firstRow(document).tiers[0] = { from_price: "1", tick: "1", note: "x" };
  expect(() => parseTicks(document)).toThrow(
    new RulesFileError("tick_sizes.json [[ticks]] row 1, tier 1: unknown key 'note'"),
  );
  firstRow(document).tiers[0] = { from_price: "1", tick: "0" };
  expect(() => parseTicks(document)).toThrow(
    /row 1, tier 1: tick must be an integer of at least 1/u,
  );
});

test("bad rows and documents are refused", () => {
  const document = documentCopy();
  firstRow(document).lot_size = "0";
  expect(() => parseTicks(document)).toThrow(/lot_size must be an integer of at least 1/u);
  expect(() => parseTicks({ ...shipped, other: "1" })).toThrow(
    new RulesFileError("tick_sizes.json [top level]: unknown key 'other'"),
  );
  expect(() => parseTicks({ ...shipped, schema: "2" })).toThrow(/schema must be 1/u);
});

test("bad settlement rows are refused", () => {
  const [row] = shipped.settlement;
  expect(() =>
    parseSettlement({ ...shipped, settlement: [{ ...row, trading_days: "0" }] }),
  ).toThrow(/trading_days must be an integer of at least 1/u);
  expect(() => parseSettlement({ ...shipped, settlement: [{ ...row, note: "x" }] })).toThrow(
    new RulesFileError("tick_sizes.json [[settlement]] row 1: unknown key 'note'"),
  );
});

test("a file read by hand uses its own name", () => {
  expect(() => parseSettlement({ schema: "1" }, "mine.json")).toThrow(
    new RulesFileError("mine.json [settlement] must be a non-empty array of tables"),
  );
});

/** The tick row in force on a recent trading day. */
const current = (): TickRow => parseTicks(shipped).on("2026-09-25");

test.each([
  [1n, 1n], [199n, 1n], [200n, 2n], [499n, 2n], [500n, 5n], [1_995n, 5n],
  [1_999n, 5n], [2_000n, 10n], [4_990n, 10n], [4_999n, 10n], [5_000n, 25n], [1_000_000n, 25n],
])("the tick of %s is %s: every tier boundary on both sides", (price, tick) => {
  expect(tickFor(current(), price)).toBe(tick);
});

test.each([
  [199n, true], [200n, true], [201n, false], [4_990n, true], [4_995n, false], [5_000n, true],
  [5_010n, false], [5_025n, true],
])("validity of %s is %s: the tier of the price itself", (price, valid) => {
  expect(isValidPrice(current(), price)).toBe(valid);
});

test.each([
  [1n, 1n, 1n], [199n, 199n, 199n], [200n, 200n, 200n], [201n, 200n, 202n], [499n, 498n, 500n],
  [501n, 500n, 505n], [1_999n, 1_995n, 2_000n], [2_001n, 2_000n, 2_010n],
  [4_999n, 4_990n, 5_000n], [5_000n, 5_000n, 5_000n], [5_001n, 5_000n, 5_025n],
  [5_024n, 5_000n, 5_025n], [2_000_000n, 2_000_000n, 2_000_000n],
])("%s rounds down to %s and up to %s, on the grid", (price, down, up) => {
  expect(roundDown(current(), price)).toBe(down);
  expect(roundUp(current(), price)).toBe(up);
});

test.each([1n, 199n, 200n, 201n, 499n, 501n, 1_999n, 2_001n, 4_999n, 5_000n, 5_001n, 2_000_000n])(
  "rounding %s is tight: the only valid prices between its pair are the pair",
  (price) => {
    const row = current();
    const low = roundDown(row, price);
    const high = roundUp(row, price);
    expect([low, price, high].toSorted((a, b) => (a < b ? -1 : a > b ? 1 : 0))).toEqual([
      low,
      price,
      high,
    ]);
    const valid: bigint[] = [];
    for (let candidate = low; candidate <= high; candidate += 1n) {
      if (isValidPrice(row, candidate)) {
        valid.push(candidate);
      }
    }
    expect(valid).toEqual(low === high ? [low] : [low, high]);
  },
);

test.each([0n, -5n, true, "200", 200])("a price of %s is refused: a whole rupiah of at least 1", (price) => {
  expect(() => tickFor(current(), price as bigint)).toThrow(
    new RangeError(
      `price must be a whole number of rupiah of at least 1, got ${String(price)}`,
    ),
  );
});
