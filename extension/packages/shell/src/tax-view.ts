/** The Tax tab's claims list as text (spec §9.2): what core's claims report says, in the lines the
 * panel writes, in English like the Advice tab's lines (#553 translates them). Pure: the panel
 * only puts each line on the page. */

import {
  NOTE_CODES,
  type ClaimRow,
  type ClaimsRead,
  type NotExemptable,
  type Note,
  type Reinvestment,
} from "@steadyhand/core";
import { sentence, type Section } from "./advice-view.ts";

/** Every figure assumes the yearly realisation reports are filed (docs/research/t-tax.md §7). */
export const ESTIMATE_LINE =
  "Every figure here is an estimate: it assumes the yearly realisation reports are filed.";

const noteLines = (notes: readonly Note[]): string[] => notes.map((each) => sentence(each.text));

const claimLine = (row: ClaimRow): string => {
  const head =
    `${row.symbol}, received ${row.received}: gross ${row.gross.toString()}, reinvested ` +
    row.reinvested.toString();
  if (row.toReinvest.amount === 0n) {
    return `${head}, nothing left to reinvest.`;
  }
  if (row.missed) {
    return (
      `${head}, ${row.toReinvest.toString()} not reinvested by ${row.deadline}, so the tax of ` +
      `${row.tax.toString()} is owed.`
    );
  }
  return (
    `${head}, still to reinvest ${row.toReinvest.toString()} by ${row.deadline}; if not, the ` +
    `tax owed is ${row.tax.toString()}.`
  );
};

/** A claim still held, as a line; a claim holding nothing has no day and no line. */
const heldLines = (row: ClaimRow): string[] =>
  row.heldUntil === null
    ? []
    : [
        `${row.symbol}, received ${row.received}: ${row.held.toString()} reinvested must stay ` +
          `invested until ${row.heldUntil}.`,
      ];

const notExemptableLine = (entry: NotExemptable): string =>
  `${entry.symbol}, received ${entry.received}: no exemption on that day, so the tax of ` +
  `${entry.tax.toString()} is owed.`;

const idleLine = (purchase: Reinvestment): string =>
  `The purchase of ${purchase.symbol} on ${purchase.day} for ${purchase.amount.toString()} ` +
  "covered no claim: no dividend was open before it, or every deadline had passed.";

/** The Tax tab's sections: the estimate line, the claims, what is still held (#256, the report
 * below the claims list) and the tax owed when a deadline is missed or a part breaks. With no
 * dividend entered, the claims say so and show no figure (#255 AC2). The cost basis named as
 * missing goes with what is held, not the tax owed. */
export const taxView = (read: ClaimsRead): readonly Section[] => {
  const estimate: Section = { heading: "Estimate", lines: [ESTIMATE_LINE] };
  const { report } = read;
  if (report === null) {
    return [estimate, { heading: "Claims", lines: noteLines(read.missing) }];
  }
  const claims: Section = {
    heading: "Claims",
    lines: [
      ...report.rows.map(claimLine),
      ...report.notExemptable.map(notExemptableLine),
      ...report.idle.map(idleLine),
    ],
  };
  const missing = report.notes.filter((each) => each.code === NOTE_CODES.MISSING_COST_BASIS);
  const said = report.notes.filter((each) => each.code !== NOTE_CODES.MISSING_COST_BASIS);
  const heldNow = report.rows.flatMap(heldLines);
  const held: Section[] =
    heldNow.length === 0 ? [] : [{ heading: "Held", lines: [...heldNow, ...noteLines(missing)] }];
  const owed: Section[] =
    report.owed.amount === 0n
      ? []
      : [{ heading: "Tax owed", lines: [`${report.owed.toString()} in all.`, ...noteLines(said)] }];
  return [estimate, claims, ...held, ...owed];
};
