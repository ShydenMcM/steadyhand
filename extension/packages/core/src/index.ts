/** The package's own name. The layers above read it to show they reach core through the workspace. */
export const PACKAGE = "@steadyhand/core";

export * from "./advice.ts";
export * from "./buy-and-hold.ts";
export * from "./broker-view.ts";
export * from "./cash.ts";
export * from "./freshness.ts";
export * from "./indonesian-number.ts";
export * from "./money.ts";
export * from "./monthly-savings.ts";
export * from "./notes.ts";
export * from "./risk.ts";
export * from "./sizing.ts";
export * from "./strategy.ts";
export * from "./tradable.ts";
export { IdxCalendar } from "./calendar.ts";
export { RuleDecimal } from "./ratio.ts";
export type { Dated } from "./rules-file.ts";
export { adviceDayAt, shippedSessions, type SessionRow } from "./sessions.ts";
