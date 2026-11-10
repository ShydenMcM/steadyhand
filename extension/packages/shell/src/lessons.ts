/** The lesson catalogue the Lessons tab renders (spec §13, #244): the course's modules in order,
 * each with its lessons in order. Each lesson ships as it is written, a Markdown file in
 * `../lessons/`, read by lessonFrom; the build bundles each file as its text. */

import brokerReading from "../lessons/broker.reading.md";
import costsSaleTax from "../lessons/costs.sale_tax.md";
import costsStampDuty from "../lessons/costs.stamp_duty.md";
import costsTrading from "../lessons/costs.trading.md";
import dividendsBasics from "../lessons/dividends.basics.md";
import idxAutoReject from "../lessons/idx.auto_reject.md";
import idxLots from "../lessons/idx.lots.md";
import idxSessions from "../lessons/idx.sessions.md";
import idxSettlement from "../lessons/idx.settlement.md";
import idxSpecialMonitoring from "../lessons/idx.special_monitoring.md";
import idxTicks from "../lessons/idx.ticks.md";
import idxUniverse from "../lessons/idx.universe.md";
import incomeCalendar from "../lessons/income.calendar.md";
import incomeGoal from "../lessons/income.goal.md";
import incomeGrowth from "../lessons/income.growth.md";
import incomeProjection from "../lessons/income.projection.md";
import incomeRunRate from "../lessons/income.run_rate.md";
import ordersLimitPrices from "../lessons/orders.limit_prices.md";
import ordersNotTradable from "../lessons/orders.not_tradable.md";
import riskDrawdown from "../lessons/risk.drawdown.md";
import riskLimits from "../lessons/risk.limits.md";
import riskReturns from "../lessons/risk.returns.md";
import sharesBasics from "../lessons/shares.basics.md";
import sharesCostBasis from "../lessons/shares.cost_basis.md";
import sharesPrices from "../lessons/shares.prices.md";
import sharesSplits from "../lessons/shares.splits.md";
import startExplanations from "../lessons/start.explanations.md";
import startWelcome from "../lessons/start.welcome.md";
import strategiesBuyAndHold from "../lessons/strategies.buy_and_hold.md";
import strategiesDividendGrowth from "../lessons/strategies.dividend_growth.md";
import strategiesExDate from "../lessons/strategies.ex_date.md";
import strategiesHighYield from "../lessons/strategies.high_yield.md";
import strategiesHoldingCash from "../lessons/strategies.holding_cash.md";
import strategiesLowVolatility from "../lessons/strategies.low_volatility.md";
import strategiesMaTrend from "../lessons/strategies.ma_trend.md";
import strategiesMomentumRotation from "../lessons/strategies.momentum_rotation.md";
import strategiesMonthlySavings from "../lessons/strategies.monthly_savings.md";
import strategiesTotalReturn from "../lessons/strategies.total_return.md";
import taxDividend from "../lessons/tax.dividend.md";
import { lessonFrom, type Lesson } from "./lesson-text.ts";

export interface LessonModule {
  readonly title: string;
  readonly lessons: readonly Lesson[];
}

/** The course's modules, in order: each lesson names its module by slug. */
const COURSE = [
  ["start-here", "Start here"],
  ["shares-and-dividends", "Shares and dividends"],
  ["how-idx-works", "How IDX works"],
  ["costs-and-tax", "Costs and tax"],
  ["risk", "Risk"],
  ["using-steadyhand", "Using steadyhand"],
  ["income-goal", "The income goal"],
  ["strategies", "Strategies"],
] as const;

/** Every lesson written, read. */
const WRITTEN: readonly Lesson[] = [
  brokerReading,
  costsSaleTax,
  costsStampDuty,
  costsTrading,
  dividendsBasics,
  idxAutoReject,
  idxLots,
  idxSessions,
  idxSettlement,
  idxSpecialMonitoring,
  idxTicks,
  idxUniverse,
  incomeCalendar,
  incomeGoal,
  incomeGrowth,
  incomeProjection,
  incomeRunRate,
  ordersLimitPrices,
  ordersNotTradable,
  riskDrawdown,
  riskLimits,
  riskReturns,
  sharesBasics,
  sharesCostBasis,
  sharesPrices,
  sharesSplits,
  startExplanations,
  startWelcome,
  strategiesBuyAndHold,
  strategiesDividendGrowth,
  strategiesExDate,
  strategiesHighYield,
  strategiesHoldingCash,
  strategiesLowVolatility,
  strategiesMaTrend,
  strategiesMomentumRotation,
  strategiesMonthlySavings,
  strategiesTotalReturn,
  taxDividend,
].map(lessonFrom);

/** The modules of `lessons`, in the course's order, each with its lessons by place; a lesson in a
 * module the course does not have is refused, naming both. */
export const catalogue = (lessons: readonly Lesson[]): readonly LessonModule[] => {
  const slugs = new Set<string>(COURSE.map(([slug]) => slug));
  const stray = lessons.find((lesson) => !slugs.has(lesson.module));
  if (stray !== undefined) {
    throw new RangeError(
      `${stray.id} is in the module ${stray.module}, which the course does not have`,
    );
  }
  return COURSE.map(([slug, title]) => ({
    title,
    lessons: lessons
      .filter((lesson) => lesson.module === slug)
      .sort((one, other) => one.position - other.position),
  })).filter((module) => module.lessons.length > 0);
};

/** The lessons this release ships. */
export const LESSONS: readonly LessonModule[] = catalogue(WRITTEN);
