/**
 * The broker view (spec §5.1): one shape for what every broker's pages show, whichever broker and
 * whichever route it was read by. Each part carries where it came from and the instant it was
 * read. A part the page does not show is absent from the view, never zero.
 */
import type Decimal from "decimal.js";
import type { Money } from "./money.ts";

/** The kinds of page a reader reads, one part of the view each (the keys of `PartValues`). */
export type PageKind = keyof PartValues;
export const PAGE_KINDS: readonly PageKind[] = [
  "portfolio",
  "watchlist",
  "stock-detail",
  "dividends",
  "cash-movements",
  "corporate-actions",
  "flags",
];

/** How a part reached the reader: the broker's page, text the user pasted, or an export file. */
export type Route = "page" | "paste" | "export";

/** Where a part came from. */
export interface Source {
  readonly broker: string;
  readonly pageKind: PageKind;
  readonly route: Route;
}

/** One part of the view, with its source and the instant it was read. */
export interface Part<T> {
  readonly source: Source;
  readonly readAt: Date;
  readonly value: T;
}

/** A trading day, `YYYY-MM-DD`. */
export type Day = string;

export interface Holding {
  readonly symbol: string;
  readonly lots: bigint;
  readonly averagePrice: Money;
  readonly lastPrice: Money;
}

export interface Portfolio {
  /** What the broker says may be spent on buys now. */
  readonly cashAvailable: Money;
  readonly cashSettled: Money;
  readonly cashUnsettled: Money;
  readonly holdings: readonly Holding[];
}

export interface WatchedStock {
  readonly symbol: string;
  readonly lastPrice: Money;
}

export interface Watchlist {
  readonly stocks: readonly WatchedStock[];
}

/** The first and last day a page's figures cover. */
export interface Covered {
  readonly from: Day;
  readonly to: Day;
}

export interface DailyClose {
  readonly day: Day;
  readonly close: Money;
}

/** A price chart's daily closes and the range it covers. */
export interface StockDetail {
  readonly symbol: string;
  readonly covered: Covered;
  readonly closes: readonly DailyClose[];
}

export interface Dividend {
  readonly symbol: string;
  readonly exDate: Day;
  readonly paymentDate: Day;
  /** Rupiah per share before tax, exact: IDX dividends are often a fraction of a rupiah. */
  readonly grossPerShare: Decimal;
}

/** The dividends a page lists and the period it covers (§7.1: none listed is not "pays none"
 * outside that period). */
export interface Dividends {
  readonly covered: Covered;
  readonly dividends: readonly Dividend[];
}

export interface CashMovement {
  readonly day: Day;
  readonly kind: "deposit" | "withdrawal";
  /** Always positive: `kind` says which way it moved. */
  readonly amount: Money;
}

export interface CashMovements {
  readonly covered: Covered;
  readonly movements: readonly CashMovement[];
}

/** A split: every `from` shares held before `exDate` become `to` shares (a reverse split has
 * `to` below `from`). */
export interface Split {
  readonly symbol: string;
  readonly exDate: Day;
  readonly from: bigint;
  readonly to: bigint;
}

export interface CorporateActions {
  readonly covered: Covered;
  readonly splits: readonly Split[];
}

/** A stock the page marks as suspended, or on the Special Monitoring Board. */
export interface Flag {
  readonly symbol: string;
  readonly flag: "suspended" | "special-monitoring";
}

export interface Flags {
  readonly flags: readonly Flag[];
}

/** What each page kind's part holds. */
export interface PartValues {
  readonly portfolio: Portfolio;
  readonly watchlist: Watchlist;
  readonly "stock-detail": StockDetail;
  readonly dividends: Dividends;
  readonly "cash-movements": CashMovements;
  readonly "corporate-actions": CorporateActions;
  readonly flags: Flags;
}

/** Every part a read found; a part not read is absent. Stock details are kept by symbol. */
export interface BrokerView {
  readonly portfolio?: Part<Portfolio>;
  readonly watchlist?: Part<Watchlist>;
  readonly stockDetails?: ReadonlyMap<string, Part<StockDetail>>;
  readonly dividends?: Part<Dividends>;
  readonly cashMovements?: Part<CashMovements>;
  readonly corporateActions?: Part<CorporateActions>;
  readonly flags?: Part<Flags>;
}
