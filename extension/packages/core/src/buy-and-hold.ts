/** `buy-and-hold`, the baseline every other strategy is measured against (M3 spec §6.6), ported
 * from Python's `strategies.buy_and_hold`.
 *
 * On its first advice day it fixes its set: the stocks buyable that day. It never sells. Each day
 * it keeps every holding at its current weight, so nothing is traded against it, and splits the
 * cash it may spend equally across the stocks of its set buyable that day. A stock that leaves
 * the universe stays held. */

import type Decimal from "decimal.js";
import { ratioDown } from "./ratio.ts";
import { plus, readSet, weightOf, writeSet, type Strategy } from "./strategy.ts";

const SET = "set";
const NAME = "buy-and-hold";

export const buyAndHold: Strategy = {
  name: NAME,
  decide(view, portfolio, memory) {
    const recalled = memory.get(SET);
    const chosen = recalled === undefined ? [...view.tradable.buyable] : readSet(recalled, NAME);
    const weights = new Map<string, Decimal>();
    const reasons = new Map<string, string>();
    for (const symbol of portfolio.holdings.keys()) {
      weights.set(symbol, weightOf(portfolio, symbol));
      reasons.set(symbol, `${NAME}: held, never sold`);
    }
    const buying = chosen.filter((symbol) => view.tradable.buyable.has(symbol));
    if (buying.length > 0) {
      const each = ratioDown(
        portfolio.spendable.amount / BigInt(buying.length),
        portfolio.value.amount,
      );
      for (const symbol of buying) {
        weights.set(symbol, plus(weights.get(symbol), each));
        reasons.set(
          symbol,
          `${NAME}: part of its day-one set, bought with an equal share of the cash`,
        );
      }
    }
    return { weights, reasons, missing: [], memory: new Map([[SET, writeSet(chosen)]]), notes: [] };
  },
};
