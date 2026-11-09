/** Total return (spec §6.5, decision 17): a stock's series (§6.3) with every cash dividend in its
 * window reinvested on its ex-date, as ma-trend, momentum-rotation and low-volatility judge it.
 *
 * Each dividend is restated in the series' share basis, today's (§6.6), and the standard factor
 * `1 - dividend / close the trading day before the ex-date` applies to every earlier close. A
 * chart already adjusted for dividends is not adjusted again. A stock whose dividends for the
 * window are unread, or whose series asks for its chart again, is listed missing. */

import type { Day, Dividends, Split } from "./broker-view.ts";
import { missingPage, type Note } from "./notes.ts";
import { RuleDecimal } from "./ratio.ts";
import { restatedPerShare } from "./restated.ts";
import type { SeriesClose, StockSeries } from "./series.ts";

export interface TotalReturn {
  readonly closes: readonly SeriesClose[];
  readonly missing: readonly Note[];
}

/** `series` of `symbol` as a total-return series in the shares of `today`. */
export const totalReturn = (
  symbol: string,
  series: StockSeries,
  dividends: Dividends | undefined,
  splits: readonly Split[],
  today: Day,
): TotalReturn => {
  const first = series.closes[0];
  const last = series.closes.at(-1);
  if (series.missing.length > 0 || first === undefined || last === undefined) {
    return { closes: series.closes, missing: series.missing };
  }
  const adjustedTo = series.dividendsAdjustedTo;
  const from = adjustedTo !== null && adjustedTo > first.day ? adjustedTo : first.day;
  if (from >= last.day) {
    return { closes: series.closes, missing: [] };
  }
  const covers =
    dividends !== undefined && dividends.covered.from <= from && dividends.covered.to >= last.day;
  if (!covers) {
    return { closes: series.closes, missing: [missingPage("dividends", symbol)] };
  }
  let closes = series.closes;
  for (const dividend of dividends.dividends) {
    const inWindow =
      dividend.symbol === symbol && dividend.exDate > from && dividend.exDate <= last.day;
    // The close before the ex-date as the series gives it, not as earlier dividends adjusted it.
    const before = series.closes.filter((daily) => daily.day < dividend.exDate).at(-1);
    if (inWindow && before !== undefined) {
      const factor = new RuleDecimal(1).minus(
        restatedPerShare(dividend, splits, today).div(before.close),
      );
      closes = closes.map((daily) =>
        daily.day < dividend.exDate ? { day: daily.day, close: daily.close.times(factor) } : daily,
      );
    }
  }
  return { closes, missing: [] };
};
