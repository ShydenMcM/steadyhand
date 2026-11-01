/** Corporate actions found by price (spec §6.4). Self-recorded closes are not adjusted (the #203
 * lesson), so a move no market could make between two of them means a split or the like.
 *
 * Between closes on consecutive trading days, the most a market can move is the auto-reject band
 * of the earlier close's tier. Across n trading days the band is stepped n times, each step from
 * the price the last one reached (up for a rise, down for a fall), since a tier can be a
 * percentage or a fixed number of rupiah, and each step reads the band rows effective on its own
 * day. A false alarm costs the user one chart read; a missed action would corrupt the series. */

import type { DailyClose } from "./broker-view.ts";
import type { IdxCalendar } from "./calendar.ts";
import type { Money } from "./money.ts";
import type { IdxMarketRules } from "./rules.ts";
import { instrument } from "./sizing.ts";

/** The furthest `from` can move by `to`'s trading day, rising or falling, stepping the band. */
const reach = (
  symbol: string,
  earlier: DailyClose,
  to: string,
  rising: boolean,
  rules: IdxMarketRules,
  calendar: IdxCalendar,
): Money => {
  const stock = instrument(symbol, rules);
  let price = earlier.close;
  let day = earlier.day;
  while (day < to) {
    day = calendar.nextTradingDay(day);
    const [low, high] = rules.priceBand(stock, price, day);
    price = rising ? high : low;
  }
  return price;
};

/** Whether the move from `earlier` to `later`, both self-recorded closes of `symbol`, is beyond
 * what the market's bands allow, so a corporate action happened between them. */
export const actionBetween = (
  symbol: string,
  earlier: DailyClose,
  later: DailyClose,
  rules: IdxMarketRules,
  calendar: IdxCalendar,
): boolean => {
  if (later.close.gt(earlier.close)) {
    return later.close.gt(reach(symbol, earlier, later.day, true, rules, calendar));
  }
  return later.close.lt(reach(symbol, earlier, later.day, false, rules, calendar));
};
