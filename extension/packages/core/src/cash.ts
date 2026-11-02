/** Whether a cash-movement read is whole (#474, #477): its rows of each kind must add up to the
 * total its page shows. A page cut short to one of two equal deposits would otherwise record a
 * deposit too few, and the risk halt's unit value would read the missing deposit as a gain. */

import type { CashMovement, CashMovements } from "./broker-view.ts";

const KINDS = [
  ["deposit", "deposits"],
  ["withdrawal", "withdrawals"],
] as const satisfies readonly (readonly [CashMovement["kind"], keyof CashMovements["totals"]])[];

/** Why `read`'s rows do not add up to its totals, the first kind that misses; `undefined` when
 * both do. */
export const totalsMismatch = (read: CashMovements): string | undefined => {
  for (const [kind, total] of KINDS) {
    const shown = read.totals[total].amount;
    const sum = read.movements
      .filter((movement) => movement.kind === kind)
      .reduce((running, movement) => running + movement.amount.amount, 0n);
    if (sum !== shown) {
      return `${total}: the page shows ${shown.toString()}, its rows add up to ${sum.toString()}`;
    }
  }
  return undefined;
};
