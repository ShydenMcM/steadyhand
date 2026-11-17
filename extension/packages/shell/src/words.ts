/** The panel's words (#584: English only, Shyden's ruling 2026-11-17): every string the panel
 * writes, by key. A `{name}` in a text is a slot `fill` puts a value in. */

import { CHOICE_LINE, DISCLAIMER } from "./advice-view.ts";

const ENGLISH = {
  tabAdvice: "Advice",
  tabSettings: "Settings",
  tabHistory: "History",
  tabLessons: "Lessons",
  tabTax: "Tax",
  disclaimer: DISCLAIMER,
  choiceLine: CHOICE_LINE,

  read: "Read this page",
  resumeLabel: "Type the strategy's name to resume buying",
  resume: "Resume",
  pasteLabel: "Or paste a broker page you saved",
  readPaste: "Read the pasted page",
  importLabel: "Or open a broker page you saved",
  answerNone: "No deposits or withdrawals since {day}",

  strategyLabel: "Strategy",
  saveStrategy: "Save strategy",
  goalLabel: "Monthly income goal, in rupiah",
  saveGoal: "Save goal",
  contributionLabel: "Monthly amount you add, in rupiah",
  saveContribution: "Save amount",
  exemptionLabel: "I claim the dividend reinvestment exemption",
  dividendDayLabel: "Day the dividend was received, such as 2025-06-16",
  entryStockLabel: "Stock code, such as BBCA",
  dividendGrossLabel: "Gross dividend, in rupiah",
  addDividend: "Keep this dividend",
  purchaseDayLabel: "Day of the purchase, such as 2025-06-16",
  purchaseAmountLabel: "Amount reinvested, in rupiah",
  addPurchase: "Keep this purchase",
  remove: "Remove",
  dividendLine: "{day}: {symbol}, gross dividend {amount}",
  purchaseLine: "{day}: {symbol}, bought for {amount}",
  dividendKept: "Dividend of {amount} from {symbol}, received on {day}, kept.",
  purchaseKept: "Purchase of {symbol} for {amount} on {day} kept.",
  entryFuture: "Not kept: {day} is after today, {today}.",
  entryEarly: "Not kept: the market rules are known from {first}, and {day} is before it.",
  stockNotKept: 'Not kept: type a stock code such as BBCA, got "{typed}"',
  entryRemoved: "Entry removed.",
  limitMaxWeight: "The largest share of one stock, in percent",
  limitMinLots: "The smallest buy, in lots",
  limitDailyLoss: "The one-day fall that halts ordering, in percent",
  limitMaxDrawdown: "The fall from the high that halts ordering, in percent",
  saveLimits: "Save risk limits",
  presetLabel: "Broker fee preset",
  savePreset: "Save fee preset",
  deposit: "Deposit",
  withdrawal: "Withdrawal",
  movementKindLabel: "Deposit or withdrawal",
  movementDayLabel: "Day, such as 2025-06-16",
  movementAmountLabel: "Amount, in rupiah",
  addMovement: "Keep this deposit or withdrawal",
  noMovements: "No deposits or withdrawals typed.",
  depositLine: "{day}: deposit of {amount}",
  withdrawalLine: "{day}: withdrawal of {amount}",
  universeLabel: "Universe: the stocks to choose from",
  saveUniverse: "Save universe",
  exclusionsLabel: "Excluded stocks: one per line, the code and then your reason",
  saveExclusions: "Save exclusions",

  recordingNote: "steadyhand records a broker page only while this panel is open beside it.",
  nothingRecorded: "Nothing is recorded yet.",
  stockLine: "{symbol}: {days} recorded, {chartReads}, {dividends}",
  dayOne: "{count} day",
  dayMany: "{count} days",
  chartReadOne: "{count} chart read",
  chartReadMany: "{count} chart reads",
  dividendOne: "{count} dividend",
  dividendMany: "{count} dividends",
  forget: "Forget everything",
  forgetWarning:
    "This deletes everything steadyhand has recorded and every setting. It cannot be undone.",
  forgetYes: "Yes, forget everything",
  forgetKeep: "Keep everything",

  noLessons: "The lessons come in a later release.",

  notABrokerTab: "This tab shows no broker page steadyhand reads.",
  pageNotRead: "This page was not read: {reason}",
  pageRead: "Read {page}.",
  pagePortfolio: "the portfolio page",
  pageWatchlist: "the watchlist page",
  pageFlags: "the flags page",
  pageCashMovements: "the cash movement page",
  pageCorporateActions: "the corporate action page",
  pageDividends: "the dividend page",
  pageStockDetail: "the stock's page",
  nothingPasted: "Nothing is pasted.",
  noFileChosen: "No file was chosen.",
  answeredNone: "Kept: no deposits or withdrawals since {day}.",
  notResumed: "Not resumed: {reason}",
  resumed: "Buying resumed: {strategy}.",
  universeNotSaved: 'Universe not saved: "{code}" is not a four-letter IDX stock code.',
  universeSaved: "Universe saved: {count} stocks.",
  strategyNotSaved: "Strategy not saved: {reason}",
  strategySaved: "Strategy saved: {strategy}.",
  goalCleared: "Income goal cleared.",
  goalSaved: "Income goal saved.",
  goalNotSaved: 'Income goal not saved: type whole rupiah, such as 5.000.000, got "{typed}"',
  contributionCleared: "Monthly amount cleared.",
  contributionSaved: "Monthly amount saved.",
  contributionNotSaved:
    'Monthly amount not saved: type whole rupiah, such as 500.000, got "{typed}"',
  limitsNotSaved: "Risk limits not saved: {reason}",
  limitsSaved: "Risk limits saved.",
  presetSaved: "Fee preset saved: {preset}.",
  dayNotKept: 'Not kept: type the day as a date such as 2025-06-16, got "{typed}"',
  amountNotKept: 'Not kept: type whole rupiah above 0, such as 1.000.000, got "{typed}"',
  depositKept: "Deposit of {amount} on {day} kept.",
  withdrawalKept: "Withdrawal of {amount} on {day} kept.",
  exclusionsNotCode: 'Exclusions not saved: "{code}" is not a four-letter IDX stock code.',
  exclusionsTwice: "Exclusions not saved: {symbol} is listed twice.",
  exclusionsSavedOne: "Exclusions saved: {count} stock.",
  exclusionsSavedMany: "Exclusions saved: {count} stocks.",
  forgotten: "Everything is forgotten.",
  wentWrong: "Something went wrong: {failure}",
} as const;

export type Words = Readonly<Record<keyof typeof ENGLISH, string>>;

export const WORDS: Words = ENGLISH;

const SLOT = /\{(\w+)\}/gu;

/** The slots in `text`, each once, sorted. */
export const slotsOf = (text: string): readonly string[] =>
  [...new Set([...text.matchAll(SLOT)].flatMap((match) => match.slice(1, 2)))].sort();

/** `text` with each slot filled from `values`; a slot with no value, or a value for no slot,
 * is refused by name. */
export const fill = (text: string, values: Readonly<Record<string, string>>): string => {
  const slots = slotsOf(text);
  const unused = Object.keys(values).find((name) => !slots.includes(name));
  if (unused !== undefined) {
    throw new Error(`the text has no slot {${unused}}`);
  }
  return text.replaceAll(SLOT, (slot, name: string) => {
    const value = values[name];
    if (value === undefined) {
      throw new Error(`the text has a slot ${slot} with no value`);
    }
    return value;
  });
};
