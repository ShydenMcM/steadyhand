import { expect, test } from "vitest";
import { cellText, columnsTable, fieldsTable, pageKindOf } from "../src/html-table.ts";

const page = (body: string): string =>
  `<html><body><main data-page-kind="watchlist">${body}</main></body></html>`;

const HOLDINGS = `
<table id="portofolio">
  <thead><tr><th>Kode</th><th>Lot</th></tr></thead>
  <tbody>
    <tr><td>BBCA</td><td>1.000</td></tr>
    <tr><td><a href="/s/TLKM">TLKM</a></td><td> 2 </td></tr>
  </tbody>
</table>`;

test("a columns table is read as rows keyed by its labels", () => {
  expect(columnsTable(page(HOLDINGS), "portofolio", ["Kode", "Lot"])).toEqual({
    rows: [
      { Kode: "BBCA", Lot: "1.000" },
      { Kode: "TLKM", Lot: "2" },
    ],
  });
});

test("a columns table with no rows is read as none", () => {
  const html = page(`<table id="t"><tr><th>Kode</th></tr></table>`);
  expect(columnsTable(html, "t", ["Kode"])).toEqual({ rows: [] });
});

test.each([
  ["<p>nothing</p>", 'no table "portofolio"'],
  [HOLDINGS + HOLDINGS, 'two tables "portofolio"'],
  [`<table id="portofolio"></table>`, 'table "portofolio" has no label row'],
  [
    `<table id="portofolio"><tr><th>Kode</th><th>Lot</th><th>Nilai</th></tr></table>`,
    'table "portofolio": unknown label "Nilai"',
  ],
  [
    `<table id="portofolio"><tr><th>Kode</th></tr></table>`,
    'table "portofolio": missing column "Lot"',
  ],
  [
    `<table id="portofolio"><tr><th>Lot</th><th>Kode</th></tr></table>`,
    'table "portofolio": columns out of order, expected "Kode", "Lot"',
  ],
  [
    `<table id="portofolio"><tr><th>Kode</th><th>Lot</th></tr><tr><td>BBCA</td></tr></table>`,
    'table "portofolio" row 1 has 1 cells, expected 2',
  ],
])("a changed table is refused by name: %#", (body, refused) => {
  expect(columnsTable(page(body), "portofolio", ["Kode", "Lot"])).toEqual({ refused });
});

const CASH = `
<table id="kas">
  <tr><th>Dana Siap Beli</th><td>1.500.000</td></tr>
  <tr><th>Saldo Kas</th><td>2.000.000</td></tr>
</table>`;

test("a fields table is read as values keyed by label", () => {
  expect(fieldsTable(page(CASH), "kas", ["Dana Siap Beli", "Saldo Kas"])).toEqual({
    fields: { "Dana Siap Beli": "1.500.000", "Saldo Kas": "2.000.000" },
  });
});

test.each([
  [
    CASH,
    ["Dana Siap Beli", "Saldo Kas", "Saldo Unsettled"],
    'table "kas": missing field "Saldo Unsettled"',
  ],
  [CASH, ["Dana Siap Beli"], 'table "kas": unknown label "Saldo Kas"'],
  [
    `<table id="kas"><tr><th>Saldo Kas</th><td>1</td></tr><tr><th>Saldo Kas</th><td>2</td></tr></table>`,
    ["Saldo Kas"],
    'table "kas": two fields "Saldo Kas"',
  ],
  [
    `<table id="kas"><tr><th>Saldo Kas</th><td>1</td><td>2</td></tr></table>`,
    ["Saldo Kas"],
    'table "kas" row 1 is not one label and one value',
  ],
  [`<p></p>`, ["Saldo Kas"], 'no table "kas"'],
])("a changed fields table is refused by name: %#", (body, labels, refused) => {
  expect(fieldsTable(page(body), "kas", labels)).toEqual({ refused });
});

test.each([
  ["  BBCA  ", "BBCA"],
  ["<b>Bank</b>\n  Central", "Bank Central"],
  ["A &amp; B &lt;x&gt; &quot;q&quot; &#39;s&#39;&nbsp;t", `A & B <x> "q" 's' t`],
  ["&copy;", "&copy;"],
])("a cell's text is %j read as %j", (html, text) => {
  expect(cellText(html)).toBe(text);
});

test.each([
  [`<main data-page-kind="portfolio">`, { kind: "portfolio" }],
  [`<main data-page-kind="stock-detail">x</main>`, { kind: "stock-detail" }],
  [`<main>`, { refused: "the page names no page kind" }],
  [`<main data-page-kind="news">`, { refused: 'unknown page kind "news"' }],
  [
    `<main data-page-kind="portfolio"><main data-page-kind="flags">`,
    { refused: "the page names more than one page kind" },
  ],
])("the page kind of %j", (html, kind) => {
  expect(pageKindOf(html)).toEqual(kind);
});
