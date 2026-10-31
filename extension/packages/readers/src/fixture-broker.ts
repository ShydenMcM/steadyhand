/**
 * The fixture broker (spec §5.3, #226 AC5): made-up pages of every page kind, saved in
 * `fixtures/fixture-broker/`, and their readers. Core, history and shell tests build on it until
 * the first real broker; browser tests serve its pages locally in place of a broker's site.
 * Its labels are Indonesian, as a broker's are, and its numbers are written the Indonesian way.
 */
import type { CashMovement, Flag, Holding, PageKind, PartValues, Split } from "@steadyhand/core";
import {
  amount,
  covered,
  day,
  lots,
  orRefuse,
  perShare,
  price,
  ratio,
  refusing,
  Refusal,
  rupiah,
  symbol,
} from "./cells.ts";
import { columnsTable, fieldsTable, pageKindOf } from "./html-table.ts";
import type { Reader, Snapshot } from "./reader.ts";

/** The name every fixture part's source gives as its broker. */
export const FIXTURE_BROKER = "fixture";

/** The folder of the fixture broker's pages, one `<page kind>.html` each. */
export const FIXTURE_PAGES = new URL("../fixtures/fixture-broker/", import.meta.url);

/** The file name of the fixture page of `kind`, under `FIXTURE_PAGES`. */
export const fixturePagePath = (kind: PageKind): string => `${kind}.html`;

const at = (table: string, row: number, column: string): string =>
  `table ${JSON.stringify(table)} row ${String(row + 1)} ${JSON.stringify(column)}`;
const field = (table: string, label: string): string =>
  `table ${JSON.stringify(table)} ${JSON.stringify(label)}`;

/** The rows' symbols, each once. */
const unique = <T extends { readonly symbol: string }>(
  rows: readonly T[],
  table: string,
): readonly T[] => {
  rows.forEach((row, index) => {
    if (rows.findIndex((other) => other.symbol === row.symbol) !== index) {
      throw new Refusal(`${at(table, index, "Kode")}: ${row.symbol} is listed twice`);
    }
  });
  return rows;
};

const period = (html: string): PartValues["dividends"]["covered"] => {
  const { fields } = orRefuse(fieldsTable(html, "periode", ["Dari", "Sampai"]));
  return covered(fields.Dari, fields.Sampai, 'table "periode"');
};

/** Whether each kind of split the page names leaves fewer shares. */
const REVERSE: Readonly<Record<string, boolean>> = {
  "Stock Split": false,
  "Reverse Stock Split": true,
};

const READ: { readonly [K in PageKind]: (html: string) => PartValues[K] } = {
  portfolio: (html) => {
    const cash = orRefuse(
      fieldsTable(html, "kas", ["Dana Siap Beli", "Saldo Kas Settled", "Saldo Kas Unsettled"]),
    ).fields;
    const table = "portofolio";
    const { rows } = orRefuse(
      columnsTable(html, table, ["Kode", "Lot", "Harga Rata-rata", "Harga Terakhir"]),
    );
    const holdings = rows.map((row, index): Holding => ({
      symbol: symbol(row.Kode, at(table, index, "Kode")),
      lots: lots(row.Lot, at(table, index, "Lot")),
      averagePrice: price(row["Harga Rata-rata"], at(table, index, "Harga Rata-rata")),
      lastPrice: price(row["Harga Terakhir"], at(table, index, "Harga Terakhir")),
    }));
    return {
      cashAvailable: rupiah(cash["Dana Siap Beli"], field("kas", "Dana Siap Beli")),
      cashSettled: rupiah(cash["Saldo Kas Settled"], field("kas", "Saldo Kas Settled")),
      cashUnsettled: rupiah(cash["Saldo Kas Unsettled"], field("kas", "Saldo Kas Unsettled")),
      holdings: unique(holdings, table),
    };
  },
  watchlist: (html) => {
    const table = "watchlist";
    const { rows } = orRefuse(columnsTable(html, table, ["Kode", "Harga Terakhir"]));
    const stocks = rows.map((row, index) => ({
      symbol: symbol(row.Kode, at(table, index, "Kode")),
      lastPrice: price(row["Harga Terakhir"], at(table, index, "Harga Terakhir")),
    }));
    return { stocks: unique(stocks, table) };
  },
  "stock-detail": (html) => {
    const code = orRefuse(fieldsTable(html, "saham", ["Kode"])).fields.Kode;
    const range = period(html);
    const table = "harga";
    const { rows } = orRefuse(columnsTable(html, table, ["Tanggal", "Penutupan"]));
    const closes = rows.map((row, index) => {
      const where = at(table, index, "Tanggal");
      const on = day(row.Tanggal, where);
      if (on < range.from || on > range.to) {
        throw new Refusal(`${where}: ${row.Tanggal} is outside the period covered`);
      }
      return { day: on, close: price(row.Penutupan, at(table, index, "Penutupan")) };
    });
    return { symbol: symbol(code, field("saham", "Kode")), covered: range, closes };
  },
  dividends: (html) => {
    const range = period(html);
    const table = "dividen";
    const labels = ["Kode", "Tanggal Ex", "Tanggal Bayar", "Dividen per Saham"] as const;
    const { rows } = orRefuse(columnsTable(html, table, labels));
    const dividends = rows.map((row, index) => ({
      symbol: symbol(row.Kode, at(table, index, "Kode")),
      exDate: day(row["Tanggal Ex"], at(table, index, "Tanggal Ex")),
      paymentDate: day(row["Tanggal Bayar"], at(table, index, "Tanggal Bayar")),
      grossPerShare: perShare(row["Dividen per Saham"], at(table, index, "Dividen per Saham")),
    }));
    return { covered: range, dividends };
  },
  "cash-movements": (html) => {
    const range = period(html);
    const table = "mutasi";
    const { rows } = orRefuse(columnsTable(html, table, ["Tanggal", "Jenis", "Jumlah"]));
    const kinds: Readonly<Record<string, CashMovement["kind"]>> = {
      Setor: "deposit",
      Tarik: "withdrawal",
    };
    const movements = rows.map((row, index): CashMovement => {
      const kind = kinds[row.Jenis];
      if (kind === undefined) {
        throw new Refusal(
          `${at(table, index, "Jenis")}: unknown kind ${JSON.stringify(row.Jenis)}`,
        );
      }
      return {
        day: day(row.Tanggal, at(table, index, "Tanggal")),
        kind,
        amount: amount(row.Jumlah, at(table, index, "Jumlah")),
      };
    });
    return { covered: range, movements };
  },
  "corporate-actions": (html) => {
    const range = period(html);
    const table = "aksi";
    const { rows } = orRefuse(columnsTable(html, table, ["Kode", "Tanggal Ex", "Jenis", "Rasio"]));
    const splits = rows.map((row, index): Split => {
      const reverse = REVERSE[row.Jenis];
      if (reverse === undefined) {
        throw new Refusal(
          `${at(table, index, "Jenis")}: unknown kind ${JSON.stringify(row.Jenis)}`,
        );
      }
      const { from, to } = ratio(row.Rasio, at(table, index, "Rasio"));
      if (reverse ? to >= from : to <= from) {
        const which = reverse ? "a reverse split must leave fewer" : "a split must leave more";
        throw new Refusal(
          `table ${JSON.stringify(table)} row ${String(index + 1)}: ${which} shares, got ${row.Rasio}`,
        );
      }
      return {
        symbol: symbol(row.Kode, at(table, index, "Kode")),
        exDate: day(row["Tanggal Ex"], at(table, index, "Tanggal Ex")),
        from,
        to,
      };
    });
    return { covered: range, splits };
  },
  flags: (html) => {
    const table = "status";
    const { rows } = orRefuse(columnsTable(html, table, ["Kode", "Status"]));
    const statuses: Readonly<Record<string, Flag["flag"]>> = {
      Suspensi: "suspended",
      "Papan Pemantauan Khusus": "special-monitoring",
    };
    const flags = rows.map((row, index): Flag => {
      const flag = statuses[row.Status];
      if (flag === undefined) {
        throw new Refusal(
          `${at(table, index, "Status")}: unknown status ${JSON.stringify(row.Status)}`,
        );
      }
      return { symbol: symbol(row.Kode, at(table, index, "Kode")), flag };
    });
    return { flags };
  },
};

const readerOf =
  <K extends PageKind>(kind: K): Reader<K> =>
  (snapshot: Snapshot, readAt: Date) =>
    refusing(() => {
      if (snapshot.route !== "page") {
        throw new Refusal(`the fixture broker has no ${snapshot.route} format`);
      }
      const { kind: shown } = orRefuse(pageKindOf(snapshot.text));
      if (shown !== kind) {
        throw new Refusal(`expected a ${kind} page, got a ${shown} page`);
      }
      const value = READ[kind](snapshot.text);
      return {
        part: {
          source: { broker: FIXTURE_BROKER, pageKind: kind, route: snapshot.route },
          readAt,
          value,
        },
      };
    });

/** The fixture broker's reader of each page kind. */
export const FIXTURE_READERS: { readonly [K in PageKind]: Reader<K> } = {
  portfolio: readerOf("portfolio"),
  watchlist: readerOf("watchlist"),
  "stock-detail": readerOf("stock-detail"),
  dividends: readerOf("dividends"),
  "cash-movements": readerOf("cash-movements"),
  "corporate-actions": readerOf("corporate-actions"),
  flags: readerOf("flags"),
};
