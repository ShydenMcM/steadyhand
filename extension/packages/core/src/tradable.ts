/** The advice day's buyable and sellable stocks, and why a stock is neither (spec §4.4).
 *
 * Ported from Python's `engine._tradable` and `view.Tradable.why_not`. A stock the broker flags
 * (suspended, or on the Special Monitoring Board) is frozen; one Settings excludes is excluded.
 * Either is neither bought nor sold, so frozen beats a strategy's sell. Frozen is set first, so it
 * wins over excluded, as Python's `setdefault` order gives. */

import type { Day, Flag } from "./broker-view.ts";
import { Side } from "./costs.ts";
import { NOTE_CODES, note, type Note } from "./notes.ts";

export interface Tradable {
  readonly day: Day;
  readonly buyable: ReadonlySet<string>;
  readonly sellable: ReadonlySet<string>;
  /** Why a stock is kept out for a cause (frozen, excluded). */
  readonly reasons: ReadonlyMap<string, Note>;
  /** The universe on `day`; every buyable stock is a member. */
  readonly members: ReadonlySet<string>;
}

export interface TradableInputs {
  readonly day: Day;
  readonly members: ReadonlySet<string>;
  readonly held: ReadonlySet<string>;
  /** The broker's flags, in the order its page lists them. */
  readonly flags: readonly Flag[];
  /** Each stock Settings excludes, with the user's reason. */
  readonly excluded: ReadonlyMap<string, string>;
}

const FLAG_TEXT: Readonly<Record<Flag["flag"], string>> = {
  suspended: "suspended",
  "special-monitoring": "on the Special Monitoring Board",
};

export const tradableOn = (inputs: TradableInputs): Tradable => {
  const reasons = new Map<string, Note>();
  for (const flagged of inputs.flags) {
    if (!reasons.has(flagged.symbol)) {
      reasons.set(
        flagged.symbol,
        note(NOTE_CODES.TRADE_FROZEN, `frozen: ${FLAG_TEXT[flagged.flag]}`),
      );
    }
  }
  for (const [symbol, reason] of inputs.excluded) {
    if (!reasons.has(symbol)) {
      reasons.set(symbol, note(NOTE_CODES.TRADE_EXCLUDED, `excluded: ${reason}`));
    }
  }
  const free = (symbol: string): boolean => !reasons.has(symbol);
  return {
    day: inputs.day,
    buyable: new Set([...inputs.members].filter(free)),
    sellable: new Set([...inputs.held].filter(free)),
    reasons,
    members: inputs.members,
  };
};

/** Why `symbol` cannot be traded on `side` on the tradable set's day, or `null` when it can. */
export const whyNot = (tradable: Tradable, symbol: string, side: Side): Note | null => {
  const allowed = side === Side.BUY ? tradable.buyable : tradable.sellable;
  if (allowed.has(symbol)) {
    return null;
  }
  const reason = tradable.reasons.get(symbol);
  if (reason !== undefined) {
    return reason;
  }
  if (side === Side.BUY) {
    return note(NOTE_CODES.TRADE_NOT_IN_UNIVERSE, `not in the universe on ${tradable.day}`);
  }
  return note(NOTE_CODES.TRADE_NOT_HELD, "not held");
};
