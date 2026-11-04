import { expect, test } from "vitest";
import { IdxCalendar } from "../src/calendar.ts";
import { IDR, Money } from "../src/money.ts";
import { RuleDecimal } from "../src/ratio.ts";
import { riskState, type RiskRecord } from "../src/risk-state.ts";
import { RiskLimits } from "../src/risk.ts";
import fixture from "./parity-halts.json" with { type: "json" };

// The parity harness for the unit value and the halts (#236 AC6, spec §8, §14.4): seeded runs of
// after-close reads, some trading days skipped, with deposits and withdrawals on calendar days
// between them, that Python's `UnitValue` and `RiskManager.halt` answered
// (`scripts/core_fixtures.py`). Core's `riskState` must give the same unit value and the same
// first halt: its day and code, and its text where no trading day was skipped (Python has no
// span to name).

interface Case {
  readonly name: string;
  readonly dailyLoss: string;
  readonly maxDrawdown: string;
  readonly reads: readonly { readonly day: string; readonly value: string }[];
  readonly movements: readonly {
    readonly day: string;
    readonly kind: string;
    readonly amount: string;
  }[];
  readonly units: string;
  readonly price: string;
  readonly highWater: string;
  readonly halt: { readonly day: string; readonly code: string; readonly text?: string } | null;
}

const CALENDAR = IdxCalendar.shipped();
const CASES: readonly Case[] = fixture.cases;

const rp = (amount: string): Money => new Money(BigInt(amount), IDR);

const kindOf = (text: string): "deposit" | "withdrawal" => {
  if (text === "deposit" || text === "withdrawal") {
    return text;
  }
  throw new Error(`the halt parity fixture has a movement of kind ${text}`);
};

const recordOf = (parity: Case): RiskRecord => ({
  valuations: parity.reads.map((read) => ({
    day: read.day,
    readAt: new Date(`${read.day}T10:00:00Z`),
    value: rp(read.value),
  })),
  movements: parity.movements.map((movement) => ({
    day: movement.day,
    kind: kindOf(movement.kind),
    amount: rp(movement.amount),
  })),
  movementReads: [],
  typed: [],
  answered: [{ from: "2023-01-01", to: "2026-12-31" }],
  resumes: [],
});

test(`the harness compares ${CASES.length.toString()} runs of reads from seed ${fixture.seed}`, () => {
  expect(CASES.length).toBeGreaterThan(0);
});

test.each(CASES)("core judges $name as Python does", (parity) => {
  const limits = new RiskLimits({
    dailyLoss: new RuleDecimal(parity.dailyLoss),
    maxDrawdown: new RuleDecimal(parity.maxDrawdown),
  });
  const state = riskState(limits, CALENDAR, recordOf(parity));
  const halt =
    state.halt === null
      ? null
      : {
          day: state.halt.day,
          code: state.halt.cause.code,
          ...(parity.halt?.text === undefined ? {} : { text: state.halt.cause.text }),
        };
  expect(
    {
      units: state.unitValue.units.toString(),
      price: state.unitValue.price.toString(),
      highWater: state.unitValue.highWater.toString(),
      halt,
    },
    `seed ${fixture.seed}, ${parity.name}`,
  ).toEqual({
    units: new RuleDecimal(parity.units).toString(),
    price: new RuleDecimal(parity.price).toString(),
    highWater: new RuleDecimal(parity.highWater).toString(),
    halt: parity.halt,
  });
});
