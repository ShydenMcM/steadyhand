import { expect, test } from "vitest";
import type { CashMovement, Covered } from "../src/broker-view.ts";
import { IdxCalendar } from "../src/calendar.ts";
import { IDR, Money } from "../src/money.ts";
import { missingDeposits, missingReread, NOTE_CODES } from "../src/notes.ts";
import { RuleDecimal } from "../src/ratio.ts";
import {
  buyStops,
  resume,
  riskState,
  type Resumed,
  type RiskRecord,
  type RiskState,
  type TypedMovement,
  type MovementRead,
  type Valuation,
} from "../src/risk-state.ts";
import { RiskLimits, UnitValue } from "../src/risk.ts";

// EXT S12 (#236, spec §8): the unit value taken from after-close reads, deposits and
// withdrawals from the cash-movement page or typed, the daily loss and drawdown halts, and
// resume. July 2025's trading days run 1-4, 7-11, 14-18 and 21-22.

const CALENDAR = IdxCalendar.shipped();
const LIMITS = new RiskLimits();

const rp = (amount: bigint): Money => new Money(amount, IDR);

/** A read after the close on `day`: 17:00 in Jakarta. */
const read = (day: string, value: bigint): Valuation => ({
  day,
  readAt: new Date(`${day}T10:00:00Z`),
  value: rp(value),
});

const span = (from: string, to: string): Covered => ({ from, to });

const deposit = (day: string, amount: bigint): CashMovement => ({
  day,
  kind: "deposit",
  amount: rp(amount),
});

const withdrawal = (day: string, amount: bigint): CashMovement => ({
  day,
  kind: "withdrawal",
  amount: rp(amount),
});

/** `at` is a time in Jakarta (WIB, UTC+7) on `day`, such as "20:00". */
const wib = (day: string, at: string): Date => new Date(`${day}T${at}:00+07:00`);

/** An entry typed at 16:00 in Jakarta on its own day, before that day's read at 17:00. */
const typed = (movement: CashMovement, at = "16:00"): TypedMovement => ({
  ...movement,
  typedAt: wib(movement.day, at),
});

/** A cash-movement page read covering `from` to `to`, read at `at` in Jakarta on `to`. */
const pageRead = (from: string, to: string, at: string): MovementRead => ({
  from,
  to,
  readAt: wib(to, at),
});

/** A record whose cash movements are answered for all of July. */
const record = (values: Partial<RiskRecord>): RiskRecord => ({
  valuations: [],
  movements: [],
  movementReads: [],
  typed: [],
  answered: [span("2025-07-01", "2025-07-31")],
  resumes: [],
  ...values,
});

const state = (values: Partial<RiskRecord>): RiskState =>
  riskState(LIMITS, CALENDAR, record(values));

const reads = (...pairs: (readonly [string, bigint])[]): Valuation[] =>
  pairs.map(([day, value]) => read(day, value));

const priced = (result: RiskState): string[] => [
  result.unitValue.units.toString(),
  result.unitValue.price.toString(),
  result.unitValue.highWater.toString(),
];

test("no read yet: no unit value, nothing judged and nothing stopped", () => {
  const result = state({});
  expect(result).toEqual({
    unitValue: new UnitValue(),
    judgedTo: null,
    halt: null,
    missing: [],
    unrecorded: null,
    superseded: [],
  });
  expect(buyStops(result)).toEqual([]);
});

test("the first after-close read opens the unit value at 1, with no halt judged", () => {
  const result = state({ valuations: reads(["2025-07-01", 100_000_000n]) });
  expect(priced(result)).toEqual(["100000000", "1", "1"]);
  expect([result.judgedTo, result.halt]).toEqual(["2025-07-01", null]);
});

test("the first read needs no cash-movement record: what came before is in its value", () => {
  const result = state({ valuations: reads(["2025-07-01", 100_000_000n]), answered: [] });
  expect(result.missing).toEqual([]);
});

test("an empty account opens with no units, and its first deposit buys them at 1", () => {
  const result = state({
    valuations: reads(["2025-07-01", 0n], ["2025-07-02", 5_000_000n]),
    movements: [deposit("2025-07-02", 5_000_000n)],
  });
  expect(priced(result)).toEqual(["5000000", "1", "1"]);
});

test("a later read revalues the units", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 102_000_000n]),
  });
  expect(priced(result)).toEqual(["100000000", "1.02", "1.02"]);
});

test("reads are taken in day order, whatever order they come in", () => {
  const result = state({
    valuations: reads(["2025-07-02", 102_000_000n], ["2025-07-01", 100_000_000n]),
  });
  expect(priced(result)).toEqual(["100000000", "1.02", "1.02"]);
});

test("two reads for one day are refused", () => {
  expect(() => state({ valuations: reads(["2025-07-01", 1n], ["2025-07-01", 2n]) })).toThrow(
    /^two after-close reads for 2025-07-01$/,
  );
});

test("a read for a day that is not a trading day is refused", () => {
  expect(() => state({ valuations: reads(["2025-07-05", 1n]) })).toThrow(
    /^2025-07-05 is not a trading day: an after-close read shows a trading day's close$/,
  );
});

test("a deposit buys units at the price, so it is never a gain", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 110_000_000n]),
    movements: [deposit("2025-07-02", 10_000_000n)],
  });
  expect(priced(result)).toEqual(["110000000", "1", "1"]);
});

test("a deposit and a market move on one day: the move moves the price, the deposit buys units", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 112_000_000n]),
    movements: [deposit("2025-07-02", 10_000_000n)],
  });
  expect(priced(result)).toEqual(["109803921.5686274509803921569", "1.02", "1.02"]);
});

test("a deposit dated on the previous read's day is in that read, not counted again", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 100_000_000n]),
    movements: [deposit("2025-07-01", 10_000_000n)],
  });
  expect(priced(result)).toEqual(["100000000", "1", "1"]);
});

test("a deposit over a weekend counts in the next read", () => {
  const result = state({
    valuations: reads(["2025-07-04", 100_000_000n], ["2025-07-07", 105_000_000n]),
    movements: [deposit("2025-07-05", 5_000_000n)],
  });
  expect(priced(result)).toEqual(["105000000", "1", "1"]);
});

test("a withdrawal sells units at the price, so it is never a loss", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 80_000_000n]),
    movements: [withdrawal("2025-07-02", 20_000_000n)],
  });
  expect(priced(result)).toEqual(["80000000", "1", "1"]);
  expect(result.halt).toBeNull();
});

test("withdrawing everything leaves no units and no halt", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 0n]),
    movements: [withdrawal("2025-07-02", 100_000_000n)],
  });
  expect(priced(result)).toEqual(["0", "1", "1"]);
  expect(result.halt).toBeNull();
});

test("deposits larger than the value read are refused, naming both", () => {
  expect(() =>
    state({
      valuations: reads(["2025-07-01", 1_000_000n], ["2025-07-02", 2_000_000n]),
      movements: [deposit("2025-07-02", 50_000_000n)],
    }),
  ).toThrow(
    "the value read on 2025-07-02, IDR 2,000,000, is less than the deposits less withdrawals " +
      "recorded after 2025-07-01, IDR 50,000,000: is a deposit dated wrongly?",
  );
});

test("a typed deposit counts on a day no cash-movement read covers", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 110_000_000n]),
    typed: [typed(deposit("2025-07-02", 10_000_000n))],
  });
  expect(priced(result)).toEqual(["110000000", "1", "1"]);
  expect(result.superseded).toEqual([]);
});

test("a typed entry on a day a cash-movement read covers is superseded by the read", () => {
  const entry = typed(deposit("2025-07-02", 10_000_000n));
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 110_000_000n]),
    movements: [deposit("2025-07-02", 10_000_000n)],
    movementReads: [span("2025-07-02", "2025-07-02")],
    typed: [entry],
    answered: [],
  });
  expect(priced(result)).toEqual(["110000000", "1", "1"]);
  expect(result.superseded).toEqual([entry]);
});

test("a typed entry outside every judged span is neither counted nor superseded", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n]),
    typed: [typed(deposit("2025-07-01", 10_000_000n))],
  });
  expect(priced(result)).toEqual(["100000000", "1", "1"]);
  expect(result.superseded).toEqual([]);
});

// #499 (Shyden 2026-11-07, option 1): a same-day deposit or withdrawal counts in that day's read
// only if it was recorded before the read; one recorded after it asks for the portfolio to be
// read again, and no halt is judged from that read until a later read of the day replaces it.
// The case from the ticket: a read at 17:00 WIB, then Rp 10,000,000 deposited at 20:00.

/** Asked to read 2025-07-02 again, judged up to 2025-07-01, nothing halted or bought. */
const askedToReread = (result: RiskState): void => {
  expect(result.missing).toEqual([missingReread("2025-07-02")]);
  expect([result.judgedTo, result.halt, result.unrecorded]).toEqual(["2025-07-01", null, null]);
  expect(priced(result)).toEqual(["100000000", "1", "1"]);
  expect(buyStops(result)).toEqual([missingReread("2025-07-02")]);
};

test("a deposit typed after its day's read asks for the portfolio to be read again", () => {
  askedToReread(
    state({
      valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 100_000_000n]),
      typed: [typed(deposit("2025-07-02", 10_000_000n), "20:00")],
    }),
  );
});

test("a withdrawal typed after its day's read asks the same way", () => {
  askedToReread(
    state({
      valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 100_000_000n]),
      typed: [typed(withdrawal("2025-07-02", 10_000_000n), "20:00")],
    }),
  );
});

test("a cash-movement page read after the day's read, listing that day, asks the same way", () => {
  askedToReread(
    state({
      valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 100_000_000n]),
      movements: [deposit("2025-07-02", 10_000_000n)],
      movementReads: [pageRead("2025-07-01", "2025-07-02", "21:00")],
      answered: [],
    }),
  );
});

test("a later read of the same day replaces the early one: the deposit buys units", () => {
  const result = state({
    valuations: [
      read("2025-07-01", 100_000_000n),
      { day: "2025-07-02", readAt: wib("2025-07-02", "21:00"), value: rp(110_000_000n) },
    ],
    typed: [typed(deposit("2025-07-02", 10_000_000n), "20:00")],
  });
  expect([result.missing, result.judgedTo, result.halt]).toEqual([[], "2025-07-02", null]);
  expect(priced(result)).toEqual(["110000000", "1", "1"]);
});

test("a deposit typed before its day's read counts in it, with no question", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 110_000_000n]),
    typed: [typed(deposit("2025-07-02", 10_000_000n), "16:00")],
  });
  expect([result.missing, result.judgedTo]).toEqual([[], "2025-07-02"]);
  expect(priced(result)).toEqual(["110000000", "1", "1"]);
});

test("a cash-movement page read before the day's read counts in it, with no question", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 110_000_000n]),
    movements: [deposit("2025-07-02", 10_000_000n)],
    movementReads: [pageRead("2025-07-01", "2025-07-02", "16:30")],
    answered: [],
  });
  expect([result.missing, result.judgedTo]).toEqual([[], "2025-07-02"]);
});

test("a late typed entry superseded by an earlier page read raises no question", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 110_000_000n]),
    movements: [deposit("2025-07-02", 10_000_000n)],
    movementReads: [pageRead("2025-07-01", "2025-07-02", "16:30")],
    typed: [typed(deposit("2025-07-02", 10_000_000n), "20:00")],
    answered: [],
  });
  expect([result.missing, result.judgedTo]).toEqual([[], "2025-07-02"]);
});

test("a page read after the day's read with no row on that day raises no question", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 100_000_000n]),
    movements: [deposit("2025-07-01", 10_000_000n)],
    movementReads: [pageRead("2025-07-01", "2025-07-02", "21:00")],
    answered: [],
  });
  expect([result.missing, result.judgedTo]).toEqual([[], "2025-07-02"]);
});

test("an entry dated before the read's day, typed after the read, raises no question", () => {
  const result = state({
    valuations: reads(["2025-07-04", 100_000_000n], ["2025-07-07", 105_000_000n]),
    typed: [{ ...deposit("2025-07-05", 5_000_000n), typedAt: wib("2025-07-07", "20:00") }],
  });
  expect([result.missing, result.judgedTo]).toEqual([[], "2025-07-07"]);
  expect(priced(result)).toEqual(["105000000", "1", "1"]);
});

test("a page read stored before #499 has no read time and raises no question", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 110_000_000n]),
    movements: [deposit("2025-07-02", 10_000_000n)],
    movementReads: [span("2025-07-01", "2025-07-02")],
    answered: [],
  });
  expect([result.missing, result.judgedTo]).toEqual([[], "2025-07-02"]);
});

test("a halt raised before the late deposit's day stays in force while the panel asks", () => {
  const result = state({
    valuations: reads(
      ["2025-07-01", 100_000_000n],
      ["2025-07-02", 90_000_000n],
      ["2025-07-03", 90_000_000n],
    ),
    typed: [typed(deposit("2025-07-03", 10_000_000n), "20:00")],
  });
  expect(result.missing).toEqual([missingReread("2025-07-03")]);
  expect(result.judgedTo).toBe("2025-07-02");
  expect(result.halt?.cause.code).toBe(NOTE_CODES.RISK_HALT_DAILY_LOSS);
});

test("no cash-movement record since the last read: missing.deposits, judged up to that read", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 50_000_000n]),
    answered: [],
  });
  expect(result.missing).toEqual([missingDeposits("2025-07-01")]);
  expect(result.unrecorded).toEqual(span("2025-07-02", "2025-07-02"));
  expect([result.judgedTo, result.halt]).toEqual(["2025-07-01", null]);
  expect(priced(result)).toEqual(["100000000", "1", "1"]);
  expect(buyStops(result)).toEqual([missingDeposits("2025-07-01")]);
});

test("the span asked about runs from the day after the last judged read to the latest read", () => {
  const result = state({
    valuations: reads(
      ["2025-07-01", 100_000_000n],
      ["2025-07-04", 100_000_000n],
      ["2025-07-08", 100_000_000n],
    ),
    answered: [span("2025-07-02", "2025-07-04")],
  });
  expect(result.judgedTo).toBe("2025-07-04");
  expect(result.unrecorded).toEqual(span("2025-07-05", "2025-07-08"));
});

test("a cash-movement read covering the span records it", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 100_000_000n]),
    movementReads: [span("2025-06-01", "2025-07-02")],
    answered: [],
  });
  expect([result.missing, result.judgedTo]).toEqual([[], "2025-07-02"]);
});

test("a read and an answer together cover the span, end to end", () => {
  const result = state({
    valuations: reads(["2025-07-04", 100_000_000n], ["2025-07-07", 100_000_000n]),
    movementReads: [span("2025-07-05", "2025-07-05")],
    answered: [span("2025-07-06", "2025-07-07")],
  });
  expect(result.missing).toEqual([]);
});

test("one day left uncovered inside the span is missing deposits", () => {
  const result = state({
    valuations: reads(["2025-07-04", 100_000_000n], ["2025-07-07", 100_000_000n]),
    movementReads: [span("2025-07-05", "2025-07-05")],
    answered: [span("2025-07-07", "2025-07-07")],
  });
  expect(result.missing).toEqual([missingDeposits("2025-07-04")]);
});

test("a cover that starts after the span's first day leaves it missing", () => {
  const result = state({
    valuations: reads(["2025-07-04", 100_000_000n], ["2025-07-07", 100_000_000n]),
    answered: [span("2025-07-06", "2025-07-07")],
  });
  expect(result.missing).toEqual([missingDeposits("2025-07-04")]);
});

test.each([
  ["exactly 5%", true, 95_000_000n],
  ["one rupiah less than 5%", false, 95_000_001n],
  ["one rupiah more than 5%", true, 94_999_999n],
])("a daily fall of %s: halted %s", (_case, halted, value) => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", value]),
  });
  expect(result.halt?.cause.code ?? null).toBe(halted ? NOTE_CODES.RISK_HALT_DAILY_LOSS : null);
});

test("the daily loss halt is dated on its read and quotes the fall", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 95_000_000n]),
  });
  expect(result.halt).toEqual({
    day: "2025-07-02",
    cause: {
      code: NOTE_CODES.RISK_HALT_DAILY_LOSS,
      text: "daily loss limit: the unit value fell 5.00%, the limit is 5.00%",
    },
  });
  expect(buyStops(result)).toEqual([result.halt?.cause]);
});

/** Falls of under 5% a day, from 100,000,000 down to 77,000,000, then `last` on 2025-07-10. */
const slide = (last: bigint): Valuation[] =>
  reads(
    ["2025-07-01", 100_000_000n],
    ["2025-07-02", 96_000_000n],
    ["2025-07-03", 92_000_000n],
    ["2025-07-04", 88_000_000n],
    ["2025-07-07", 84_000_000n],
    ["2025-07-08", 80_500_000n],
    ["2025-07-09", 77_000_000n],
    ["2025-07-10", last],
  );

test.each([
  ["exactly 25%", true, 75_000_000n],
  ["one rupiah less than 25%", false, 75_000_001n],
  ["one rupiah more than 25%", true, 74_999_999n],
])("a drawdown of %s: halted %s", (_case, halted, value) => {
  const result = state({ valuations: slide(value) });
  expect(result.halt?.cause.code ?? null).toBe(halted ? NOTE_CODES.RISK_HALT_DRAWDOWN : null);
});

test("the drawdown halt quotes the drawdown and the limit", () => {
  expect(state({ valuations: slide(75_000_000n) }).halt?.cause.text).toBe(
    "drawdown kill switch: the unit value is 25.00% below its high-water mark, the limit is 25.00%",
  );
});

test("a fall over trading days with no read is judged against 5%, naming the span", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-03", 94_000_000n]),
  });
  expect(result.halt?.cause.text).toBe(
    "daily loss limit: the unit value fell 6.00% from 2025-07-01 to 2025-07-03, with no read " +
      "on the trading days between; the limit is 5.00%",
  );
});

test("a fall under 5% over trading days with no read does not halt", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-03", 95_100_000n]),
  });
  expect(result.halt).toBeNull();
});

test("a weekend between two reads is no gap: Friday to Monday is one trading day", () => {
  const result = state({
    valuations: reads(["2025-07-04", 100_000_000n], ["2025-07-07", 94_000_000n]),
  });
  expect(result.halt?.cause.text).toBe(
    "daily loss limit: the unit value fell 6.00%, the limit is 5.00%",
  );
});

test("a halt lasts through later reads, even a recovery, and keeps its first cause", () => {
  const result = state({
    valuations: reads(
      ["2025-07-01", 100_000_000n],
      ["2025-07-02", 90_000_000n],
      ["2025-07-03", 80_000_000n],
      ["2025-07-04", 100_000_000n],
    ),
  });
  expect(result.halt?.day).toBe("2025-07-02");
  expect(priced(result)).toEqual(["100000000", "1", "1"]);
  expect(result.judgedTo).toBe("2025-07-04");
});

const resumed = (haltDay: string, at: string): Resumed => ({
  haltDay,
  at: new Date(at),
  strategy: "buy-and-hold",
});

test("a resume clears its halt, and the reads after it are judged again", () => {
  const result = state({
    valuations: reads(
      ["2025-07-01", 100_000_000n],
      ["2025-07-02", 94_000_000n],
      ["2025-07-03", 95_000_000n],
      ["2025-07-04", 89_000_000n],
    ),
    resumes: [resumed("2025-07-02", "2025-07-03T01:00:00Z")],
  });
  expect(result.halt?.day).toBe("2025-07-04");
});

test("a resume after the latest read clears the halt", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 94_000_000n]),
    resumes: [resumed("2025-07-02", "2025-07-02T23:00:00Z")],
  });
  expect(result.halt).toBeNull();
  expect(buyStops(result)).toEqual([]);
});

test("a resume of another day's halt does not clear this one", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 94_000_000n]),
    resumes: [resumed("2025-07-01", "2025-07-02T23:00:00Z")],
  });
  expect(result.halt?.day).toBe("2025-07-02");
});

test("a resume dated before its halt's read does not clear it", () => {
  const result = state({
    valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 94_000_000n]),
    resumes: [resumed("2025-07-02", "2025-07-02T09:00:00Z")],
  });
  expect(result.halt?.day).toBe("2025-07-02");
});

const halted = (): RiskState =>
  state({ valuations: reads(["2025-07-01", 100_000_000n], ["2025-07-02", 94_000_000n]) });

const AT = new Date("2025-07-02T23:00:00Z");

test("typing the strategy's name resumes the halt, recording its day and the time", () => {
  expect(resume(LIMITS, halted(), "buy-and-hold", "buy-and-hold", AT)).toEqual({
    resumed: { haltDay: "2025-07-02", at: AT, strategy: "buy-and-hold" },
  });
});

test("anything else typed changes nothing", () => {
  expect(resume(LIMITS, halted(), "buy-and-hold", "resume", AT)).toEqual({
    refused: "you typed 'resume', not 'buy-and-hold'; nothing was changed",
  });
});

test("resume when nothing is halted says so", () => {
  const result = state({ valuations: reads(["2025-07-01", 100_000_000n]) });
  expect(resume(LIMITS, result, "buy-and-hold", "buy-and-hold", AT)).toEqual({
    refused: "nothing is halted; there is nothing to resume",
  });
});

test("resume is refused while the deposits a halt needs are missing", () => {
  const result = state({
    valuations: reads(
      ["2025-07-01", 100_000_000n],
      ["2025-07-02", 94_000_000n],
      ["2025-07-03", 94_000_000n],
    ),
    answered: [span("2025-07-02", "2025-07-02")],
  });
  expect(result.halt?.day).toBe("2025-07-02");
  expect(resume(LIMITS, result, "buy-and-hold", "buy-and-hold", AT)).toEqual({
    refused:
      "the halt stays while a fact it needs is missing: deposits and withdrawals since " +
      "2025-07-02 are not recorded: open the cash movement page, or enter each one (or none)",
  });
});

test("resume is refused while the drawdown is at its limit", () => {
  expect(resume(LIMITS, state({ valuations: slide(75_000_000n) }), "x", "x", AT)).toEqual({
    refused:
      "the unit value is still 25.00% below its high-water mark, at or past the 25.00% " +
      "drawdown limit; the halt stays until it recovers",
  });
});

test("resume is allowed once the drawdown is just inside the limit", () => {
  const halts = new RiskLimits({ maxDrawdown: new RuleDecimal("0.26") });
  const drawn = riskState(halts, CALENDAR, record({ valuations: slide(74_000_000n) }));
  expect(drawn.halt?.cause.code).toBe(NOTE_CODES.RISK_HALT_DRAWDOWN);
  const raised = new RiskLimits({ maxDrawdown: new RuleDecimal("0.2600000001") });
  expect(resume(raised, drawn, "x", "x", AT)).toEqual({
    resumed: { haltDay: "2025-07-10", at: AT, strategy: "x" },
  });
});
