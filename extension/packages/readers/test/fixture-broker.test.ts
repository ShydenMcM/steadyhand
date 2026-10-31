import { readFileSync } from "node:fs";
import Decimal from "decimal.js";
import { IDR, Money, PAGE_KINDS, type PageKind, type PartValues } from "@steadyhand/core";
import { expect, test } from "vitest";
import {
  FIXTURE_BROKER,
  FIXTURE_PAGES,
  FIXTURE_READERS,
  fixturePagePath,
} from "../src/fixture-broker.ts";
import type { Snapshot } from "../src/reader.ts";

// The fixture broker (#226 AC5): a page of every kind and its reader, standing in for a real
// broker in core, history and shell tests until the first one (spec §5.3).

const READ_AT = new Date("2026-10-29T10:00:00Z");
const rp = (amount: bigint): Money => new Money(amount, IDR);

const page = (kind: PageKind): string =>
  readFileSync(new URL(fixturePagePath(kind), FIXTURE_PAGES), "utf8");
const html = (text: string): Snapshot => ({ route: "page", text });

const EXPECTED: { readonly [K in PageKind]: PartValues[K] } = {
  portfolio: {
    cashAvailable: rp(12_500_000n),
    cashSettled: rp(10_000_000n),
    cashUnsettled: rp(-1_250_000n),
    holdings: [
      { symbol: "BBCA", lots: 12n, averagePrice: rp(9875n), lastPrice: rp(10_150n) },
      { symbol: "TLKM", lots: 1000n, averagePrice: rp(3210n), lastPrice: rp(2980n) },
    ],
  },
  watchlist: {
    stocks: [
      { symbol: "BBRI", lastPrice: rp(4560n) },
      { symbol: "UNVR", lastPrice: rp(1885n) },
    ],
  },
  "stock-detail": {
    symbol: "BBCA",
    covered: { from: "2026-10-27", to: "2026-10-29" },
    closes: [
      { day: "2026-10-27", close: rp(10_050n) },
      { day: "2026-10-28", close: rp(10_100n) },
      { day: "2026-10-29", close: rp(10_150n) },
    ],
  },
  dividends: {
    covered: { from: "2025-01-01", to: "2026-10-31" },
    dividends: [
      {
        symbol: "BBCA",
        exDate: "2026-03-20",
        paymentDate: "2026-04-10",
        grossPerShare: new Decimal("227.5"),
      },
      {
        symbol: "TLKM",
        exDate: "2026-06-02",
        paymentDate: "2026-06-25",
        grossPerShare: new Decimal("214"),
      },
    ],
  },
  "cash-movements": {
    covered: { from: "2026-10-01", to: "2026-10-31" },
    movements: [
      { day: "2026-10-05", kind: "deposit", amount: rp(5_000_000n) },
      { day: "2026-10-20", kind: "withdrawal", amount: rp(750_000n) },
    ],
  },
  "corporate-actions": {
    covered: { from: "2021-01-01", to: "2026-10-31" },
    splits: [
      { symbol: "BBCA", exDate: "2021-10-13", from: 1n, to: 5n },
      { symbol: "GOTO", exDate: "2026-07-15", from: 10n, to: 1n },
    ],
  },
  flags: {
    flags: [
      { symbol: "SRIL", flag: "suspended" },
      { symbol: "BUMI", flag: "special-monitoring" },
    ],
  },
};

test("the fixture broker has a page and a reader for every page kind", () => {
  expect(Object.keys(FIXTURE_READERS).sort()).toEqual([...PAGE_KINDS].sort());
  expect(PAGE_KINDS).toHaveLength(7);
});

test.each(PAGE_KINDS.map((kind) => [kind]))(
  "the %s page is read exactly, with its source",
  (kind) => {
    expect(FIXTURE_READERS[kind](html(page(kind)), READ_AT)).toEqual({
      part: {
        source: { broker: FIXTURE_BROKER, pageKind: kind, route: "page" },
        readAt: READ_AT,
        value: EXPECTED[kind],
      },
    });
  },
);

test.each(PAGE_KINDS.map((kind) => [kind]))(
  "the %s reader refuses another kind of page",
  (kind) => {
    const other = kind === "flags" ? "portfolio" : "flags";
    expect(FIXTURE_READERS[kind](html(page(other)), READ_AT)).toEqual({
      refused: `expected a ${kind} page, got a ${other} page`,
    });
  },
);

test.each([
  [{ route: "paste", text: "BBCA 12" }],
  [{ route: "export", bytes: new Uint8Array([1, 2]) }],
] as const)("the fixture broker reads pages only: %#", (snapshot) => {
  expect(FIXTURE_READERS.portfolio(snapshot, READ_AT)).toEqual({
    refused: `the fixture broker has no ${snapshot.route} format`,
  });
});

test("a page naming no kind is refused", () => {
  expect(FIXTURE_READERS.watchlist(html("<main></main>"), READ_AT)).toEqual({
    refused: "the page names no page kind",
  });
});

/** The `kind` page with `from` replaced by `to`, exactly once. White space between tags in the
 * saved page is ignored, as the pages are formatted with one element to a line. */
const changed = (kind: PageKind, from: string, to: string): Snapshot => {
  const text = page(kind);
  const pattern = new RegExp(
    from.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&").replaceAll("><", ">\\s*<"),
    "gu",
  );
  expect(text.match(pattern)).toHaveLength(1);
  return html(text.replace(pattern, to));
};

// Each way a page can change, refused by name (#226 AC2).
test.each([
  ["portfolio", "<th>Lot</th>", "<th>Jumlah</th>", 'table "portofolio": unknown label "Jumlah"'],
  [
    "portfolio",
    "<th>Dana Siap Beli</th>",
    "<th>Dana Beli</th>",
    'table "kas": unknown label "Dana Beli"',
  ],
  [
    "portfolio",
    "<td>12</td>",
    "<td>12,5</td>",
    'table "portofolio" row 1 "Lot": "12,5" has a fraction where a whole number is needed',
  ],
  [
    "portfolio",
    "<td>9.875</td>",
    "<td>9,875</td>",
    'table "portofolio" row 1 "Harga Rata-rata": "9,875" is ambiguous: a comma before exactly three digits could be a thousands separator',
  ],
  [
    "portfolio",
    "<td>BBCA</td>",
    "<td>bbca</td>",
    'table "portofolio" row 1 "Kode": "bbca" is not a stock code',
  ],
  ["portfolio", '<table id="kas">', '<table id="dana">', 'no table "kas"'],
  [
    "watchlist",
    "<td>4.560</td>",
    "<td>4.56</td>",
    'table "watchlist" row 1 "Harga Terakhir": "4.56" is not a number in Indonesian format',
  ],
  ["watchlist", '<table id="watchlist">', '<table id="pantau">', 'no table "watchlist"'],
  [
    "stock-detail",
    "<td>BBCA</td>",
    "<td>BBCA1</td>",
    'table "saham" "Kode": "BBCA1" is not a stock code',
  ],
  [
    "stock-detail",
    "<td>27/10/2026</td><td>10.050</td>",
    "<td>27-10-2026</td><td>10.050</td>",
    'table "harga" row 1 "Tanggal": "27-10-2026" is not a date DD/MM/YYYY',
  ],
  [
    "stock-detail",
    "<td>28/10/2026</td>",
    "<td>31/02/2026</td>",
    'table "harga" row 2 "Tanggal": "31/02/2026" is not a date DD/MM/YYYY',
  ],
  [
    "stock-detail",
    "<th>Sampai</th><td>29/10/2026</td>",
    "<th>Sampai</th><td>26/10/2026</td>",
    'table "periode": the period ends before it starts',
  ],
  [
    "stock-detail",
    "<td>10.100</td>",
    "<td>-10.100</td>",
    'table "harga" row 2 "Penutupan": "-10.100" is not a positive price',
  ],
  ["stock-detail", '<table id="harga">', '<table id="grafik">', 'no table "harga"'],
  ["stock-detail", '<table id="saham">', '<table id="kode">', 'no table "saham"'],
  ["stock-detail", '<table id="periode">', '<table id="rentang">', 'no table "periode"'],
  [
    "dividends",
    "<td>227,5</td>",
    "<td>227.5</td>",
    'table "dividen" row 1 "Dividen per Saham": "227.5" is not a number in Indonesian format',
  ],
  [
    "dividends",
    "<td>214</td>",
    "<td>0</td>",
    'table "dividen" row 2 "Dividen per Saham": "0" is not a positive amount',
  ],
  [
    "dividends",
    "<td>10/04/2026</td>",
    "<td>10/04/26</td>",
    'table "dividen" row 1 "Tanggal Bayar": "10/04/26" is not a date DD/MM/YYYY',
  ],
  ["dividends", '<table id="dividen">', '<table id="d">', 'no table "dividen"'],
  ["dividends", '<table id="periode">', '<table id="p">', 'no table "periode"'],
  [
    "cash-movements",
    "<td>Tarik</td>",
    "<td>Transfer</td>",
    'table "mutasi" row 2 "Jenis": unknown kind "Transfer"',
  ],
  [
    "cash-movements",
    "<td>750.000</td>",
    "<td>-750.000</td>",
    'table "mutasi" row 2 "Jumlah": "-750.000" is not a positive amount',
  ],
  [
    "cash-movements",
    "<td>05/10/2026</td>",
    "<td>5/10/2026</td>",
    'table "mutasi" row 1 "Tanggal": "5/10/2026" is not a date DD/MM/YYYY',
  ],
  ["cash-movements", '<table id="mutasi">', '<table id="m">', 'no table "mutasi"'],
  ["cash-movements", '<table id="periode">', '<table id="p">', 'no table "periode"'],
  [
    "corporate-actions",
    "<td>1:5</td>",
    "<td>1/5</td>",
    'table "aksi" row 1 "Rasio": "1/5" is not a ratio N:M',
  ],
  [
    "corporate-actions",
    "<td>10:1</td>",
    "<td>0:1</td>",
    'table "aksi" row 2 "Rasio": "0:1" is not a ratio N:M',
  ],
  [
    "corporate-actions",
    "<td>Stock Split</td>",
    "<td>Rights Issue</td>",
    'table "aksi" row 1 "Jenis": unknown kind "Rights Issue"',
  ],
  [
    "corporate-actions",
    "<td>Reverse Stock Split</td><td>10:1</td>",
    "<td>Reverse Stock Split</td><td>1:10</td>",
    'table "aksi" row 2: a reverse split must leave fewer shares, got 1:10',
  ],
  [
    "corporate-actions",
    "<td>Stock Split</td><td>1:5</td>",
    "<td>Stock Split</td><td>5:1</td>",
    'table "aksi" row 1: a split must leave more shares, got 5:1',
  ],
  [
    "corporate-actions",
    "<td>13/10/2021</td>",
    "<td>13/13/2021</td>",
    'table "aksi" row 1 "Tanggal Ex": "13/13/2021" is not a date DD/MM/YYYY',
  ],
  ["corporate-actions", '<table id="aksi">', '<table id="a">', 'no table "aksi"'],
  ["corporate-actions", '<table id="periode">', '<table id="p">', 'no table "periode"'],
  [
    "flags",
    "<td>Suspensi</td>",
    "<td>Delisting</td>",
    'table "status" row 1 "Status": unknown status "Delisting"',
  ],
  ["flags", "<td>SRIL</td>", "<td></td>", 'table "status" row 1 "Kode": "" is not a stock code'],
  ["flags", '<table id="status">', '<table id="s">', 'no table "status"'],
] as const)("the %s page with %j as %j is refused: %s", (kind, from, to, refused) => {
  expect(FIXTURE_READERS[kind](changed(kind, from, to), READ_AT)).toEqual({ refused });
});

test("a holding whose price is not positive is refused", () => {
  const snapshot = changed("portfolio", "<td>10.150</td>", "<td>0</td>");
  expect(FIXTURE_READERS.portfolio(snapshot, READ_AT)).toEqual({
    refused: 'table "portofolio" row 1 "Harga Terakhir": "0" is not a positive price',
  });
});

test("a holding of no lots is refused", () => {
  const snapshot = changed("portfolio", "<td>12</td>", "<td>0</td>");
  expect(FIXTURE_READERS.portfolio(snapshot, READ_AT)).toEqual({
    refused: 'table "portofolio" row 1 "Lot": "0" is not a positive number of lots',
  });
});

test("a cash figure that is not a whole rupiah is refused", () => {
  const snapshot = changed("portfolio", "<td>12.500.000</td>", "<td>12.500.000,50</td>");
  expect(FIXTURE_READERS.portfolio(snapshot, READ_AT)).toEqual({
    refused:
      'table "kas" "Dana Siap Beli": "12.500.000,50" has a fraction where a whole number is needed',
  });
});

test("a close outside the range the chart covers is refused", () => {
  const snapshot = changed(
    "stock-detail",
    "<td>29/10/2026</td><td>10.150</td>",
    "<td>30/10/2026</td><td>10.150</td>",
  );
  expect(FIXTURE_READERS["stock-detail"](snapshot, READ_AT)).toEqual({
    refused: 'table "harga" row 3 "Tanggal": 30/10/2026 is outside the period covered',
  });
});

test("a holding listed twice is refused", () => {
  const snapshot = changed("portfolio", "<td>TLKM</td>", "<td>BBCA</td>");
  expect(FIXTURE_READERS.portfolio(snapshot, READ_AT)).toEqual({
    refused: 'table "portofolio" row 2 "Kode": BBCA is listed twice',
  });
});
