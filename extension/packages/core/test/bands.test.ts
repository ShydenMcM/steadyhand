import { expect, test } from "vitest";
import shipped from "../rules/auto_reject.json" with { type: "json" };
import { bandLimits, bandTierFor, parseBands, type BandRow, type BandTier } from "../src/bands.ts";
import { RulesFileError } from "../src/rules-file.ts";

// Ported from Python's tests/idx/test_bands.py, one test per case: the reading cases (#223) and
// the band arithmetic (#224).

type Document = typeof shipped & Record<string, unknown>;

/** A fresh copy of the shipped document, to change one value of. */
const documentCopy = (): Document => structuredClone(shipped);

const firstRow = (document: Document): Record<string, unknown> => {
  const [first] = document.bands;
  if (first === undefined) {
    throw new Error("the shipped band table has no row");
  }
  return first;
};

/** A tier as the file writes it. */
const written = (tier: BandTier): Record<string, string> => {
  const bound = tier.upTo === null ? {} : { up_to: String(tier.upTo) };
  const unit = tier.inRupiah ? "rupiah" : "percent";
  return {
    ...bound,
    [`up_${unit}`]: tier.up.toString(),
    [`down_${unit}`]: tier.down.toString(),
  };
};

test("every row of the shipped bands is read as the file states it", () => {
  const read = parseBands(shipped);
  expect(
    read.entries.map(([from, row]: readonly [string, BandRow]) => ({
      from,
      source: row.source,
      min_price: String(row.minPrice),
      tiers: row.tiers.map(written),
    })),
  ).toEqual(shipped.bands);
});

test("the table is verified from 13 March 2020", () => {
  expect(parseBands(shipped).first).toBe("2020-03-13");
  expect(() => parseBands(shipped).on("2020-03-12")).toThrow(
    /auto_reject\.json \[bands\] has no verified row for 2020-03-12/u,
  );
});

test("the shipped file holds a band in rupiah", () => {
  const tiers = parseBands(shipped).entries.flatMap(([, row]) => row.tiers);
  expect(tiers.some((tier) => tier.inRupiah)).toBe(true);
});

test("a planted changed row goes red: a minimum price above the first tier's end", () => {
  const document = documentCopy();
  firstRow(document).min_price = "201";
  expect(() => parseBands(document)).toThrow(
    new RulesFileError(
      "auto_reject.json [[bands]] row 1: the first tier ends at 200, below the minimum price 201",
    ),
  );
});

const TOP = { up_percent: "20", down_percent: "7" };

test.each([
  [[{ up_to: "200", ...TOP }], "row 1, tier 1: the top tier has no up_to"],
  [[{ up_percent: "20" }, TOP], "row 1, tier 1: missing key 'up_to'"],
  [
    [{ up_to: "200", up_percent: "35", down_rupiah: "1" }, TOP],
    "row 1, tier 1: give the band in percent or in rupiah, not both",
  ],
  [[{ up_to: "200", down_rupiah: "1" }, TOP], "row 1, tier 1: missing key 'up_rupiah'"],
  [
    [{ up_percent: "0", down_percent: "7" }],
    "row 1, tier 1: percentages must be above 0, and down below 100",
  ],
  [
    [{ up_percent: "20", down_percent: "0" }],
    "row 1, tier 1: percentages must be above 0, and down below 100",
  ],
  [
    [{ up_percent: "20", down_percent: "100" }],
    "row 1, tier 1: percentages must be above 0, and down below 100",
  ],
  [[{ up_to: "20", ...TOP }, TOP], "row 1: the first tier ends at 20, below the minimum price 50"],
  [
    [{ up_to: "200", ...TOP }, { up_to: "200", ...TOP }, TOP],
    "row 1: tier bounds must rise, got 200 after 200",
  ],
  [[{ ...TOP, note: "x" }], "row 1, tier 1: unknown key 'note'"],
  [[], "row 1: needs at least one tier"],
])("bad tiers %j are refused", (tiers, message) => {
  const document = documentCopy();
  firstRow(document).tiers = tiers;
  expect(() => parseBands(document)).toThrow(
    new RulesFileError(`auto_reject.json [[bands]] ${message}`),
  );
});

test("bad documents are refused", () => {
  expect(() => parseBands({ ...shipped, x: "1" })).toThrow(
    new RulesFileError("auto_reject.json [top level]: unknown key 'x'"),
  );
  const document = documentCopy();
  firstRow(document).min_price = "0";
  expect(() => parseBands(document)).toThrow(/min_price must be an integer of at least 1/u);
});

/** One tier as the research gives it: inclusive upper reference, up, down, in rupiah. */
type Tier = readonly [bigint | null, string, string, boolean];

const pct = (upTo: bigint | null, up: string, down: string): Tier => [upTo, up, down, false];

const RUPIAH_1: Tier = [10n, "1", "1", true];

// Every period, copied from t-hist.md §4 and t-rules.md §3: (from, minimum price, tiers). A
// literal pin against the research.
const RESEARCH: readonly (readonly [string, bigint, readonly Tier[]])[] = [
  ["2020-03-13", 50n, [pct(200n, "35", "7"), pct(5000n, "25", "7"), pct(null, "20", "7")]],
  ["2023-06-05", 50n, [pct(200n, "35", "15"), pct(5000n, "25", "15"), pct(null, "20", "15")]],
  ["2023-09-04", 50n, [pct(200n, "35", "35"), pct(5000n, "25", "25"), pct(null, "20", "20")]],
  ["2025-04-08", 50n, [pct(200n, "35", "15"), pct(5000n, "25", "15"), pct(null, "20", "15")]],
  [
    "2026-09-28",
    1n,
    [RUPIAH_1, pct(200n, "35", "15"), pct(5000n, "25", "15"), pct(null, "20", "15")],
  ],
  [
    "2027-01-01",
    1n,
    [RUPIAH_1, pct(200n, "35", "35"), pct(5000n, "25", "25"), pct(null, "20", "20")],
  ],
];

test("the periods start where the research says", () => {
  expect(parseBands(shipped).entries.map(([from]) => from)).toEqual(
    RESEARCH.map(([from]) => from),
  );
});

test.each(RESEARCH)("the period from %s matches the research", (from, minPrice, tiers) => {
  const row = parseBands(shipped).on(from);
  expect(row.minPrice).toBe(minPrice);
  expect(
    row.tiers.map((tier) => [tier.upTo, tier.up.toString(), tier.down.toString(), tier.inRupiah]),
  ).toEqual(tiers);
});

test.each([
  ["2025-04-08", 200n, "35"], // 200 is in the LOWER tier here, unlike the tick table
  ["2025-04-08", 201n, "25"],
  ["2025-04-08", 5_000n, "25"],
  ["2025-04-08", 5_001n, "20"],
  ["2026-09-28", 10n, "1"],
  ["2026-09-28", 11n, "35"],
])("on %s a reference of %s moves up by %s: tier edges include the upper bound", (on, reference, up) => {
  expect(bandTierFor(parseBands(shipped).on(on), reference).up.toString()).toBe(up);
});

/** The limits as their digits, to compare with Python's. */
const limits = (on: string, reference: bigint): [string, string] => {
  const [low, high] = bandLimits(parseBands(shipped).on(on), reference);
  return [low.toString(), high.toString()];
};

test("percentage limits are exact: 1,000 on 2025-04-08", () => {
  expect(limits("2025-04-08", 1_000n)).toEqual(["850", "1250"]);
});

test("percentage limits are exact: 155 on 2020-03-13", () => {
  expect(limits("2020-03-13", 155n)).toEqual(["144.15", "209.25"]);
});

test("rupiah limits are one either way", () => {
  expect(limits("2026-09-28", 7n)).toEqual(["6", "8"]);
});

test.each([0n, -1n, true, 200])("a reference of %s is refused: a whole rupiah of at least 1", (reference) => {
  expect(() => bandTierFor(parseBands(shipped).on("2025-04-08"), reference as bigint)).toThrow(
    new RangeError(
      `reference must be a whole number of rupiah of at least 1, got ${String(reference)}`,
    ),
  );
});
