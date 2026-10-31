import { expect, test } from "vitest";
import shipped from "../rules/auto_reject.json" with { type: "json" };
import { parseBands, type BandRow, type BandTier } from "../src/bands.ts";
import { RulesFileError } from "../src/rules-file.ts";

// Ported from the reading cases of Python's tests/idx/test_bands.py, one test per case. The band
// arithmetic is EXT S4b's (#224).

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
