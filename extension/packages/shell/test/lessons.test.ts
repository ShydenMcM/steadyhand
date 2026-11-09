import { readFileSync } from "node:fs";
import { NOTE_CODES } from "@steadyhand/core";
import { expect, test } from "vitest";
import { lessonFrom, type Lesson } from "../src/lesson-text.ts";
import { catalogue, LESSONS } from "../src/lessons.ts";

// The lessons the extension ships (#244, spec §13): the Python course's lessons, less those that
// describe what the extension does not do, thirteen rewritten for it, and six new.

/** Kept as written: their text is the Python lesson's, word for word. */
const AS_WRITTEN = [
  "costs.sale_tax",
  "costs.stamp_duty",
  "dividends.basics",
  "idx.auto_reject",
  "idx.lots",
  "idx.settlement",
  "idx.special_monitoring",
  "idx.ticks",
  "income.calendar",
  "income.goal",
  "income.run_rate",
  "risk.limits",
  "shares.basics",
  "shares.cost_basis",
  "shares.splits",
  "tax.dividend",
] as const;
const REWRITTEN = [
  "costs.trading",
  "idx.sessions",
  "idx.universe",
  "orders.not_tradable",
  "risk.drawdown",
  "risk.returns",
  "shares.prices",
  "start.explanations",
  "start.welcome",
  "strategies.buy_and_hold",
  "strategies.dividend_growth",
  "strategies.holding_cash",
  "strategies.monthly_savings",
] as const;
const NEW = [
  "broker.reading",
  "orders.limit_prices",
  "strategies.high_yield",
  "strategies.low_volatility",
  "strategies.ma_trend",
  "strategies.momentum_rotation",
  "strategies.total_return",
] as const;

const ALL: readonly Lesson[] = LESSONS.flatMap((module) => module.lessons);

/** Where the Python course keeps each lesson, by its package. */
const PYTHON = new URL("../../../../packages/", import.meta.url);
const pythonLesson = (id: string): Lesson => {
  for (const place of [
    "steadyhand-idx/src/steadyhand_idx/training/lessons/en/",
    "steadyhand/src/steadyhand/training/lessons/en/",
  ]) {
    try {
      return lessonFrom(readFileSync(new URL(`${place}${id}.md`, PYTHON), "utf8"));
    } catch (failure) {
      if (!String(failure).includes("ENOENT")) {
        throw failure;
      }
    }
  }
  throw new Error(`no Python lesson ${id}`);
};

/** Every piece of text a lesson shows, its title and summary first. */
const textsOf = (lesson: Lesson): string[] => [
  lesson.title,
  lesson.summary,
  ...lesson.blocks.flatMap((block) => {
    if (block.kind === "paragraph") {
      return block.spans.map((span) => span.text);
    }
    if (block.kind === "list") {
      return block.items.flat().map((span) => span.text);
    }
    return [block.heading, ...block.rows].flat(2).map((span) => span.text);
  }),
];

/** What spec §13 refuses in a shipped lesson: backtests, paper trading, Yahoo, a command line or
 * the Python configuration file. */
const FORBIDDEN =
  /backtest|paper[ -]?trad|paper run|yahoo|steadyhand\.toml|steadyhand-idx|command line|\bCLI\b|explain command|configuration file/iu;
const forbiddenIn = (lesson: Lesson): string[] =>
  textsOf(lesson).filter((text) => FORBIDDEN.test(text));

test("the course ships the lessons kept as written, the rewritten ones and the new ones", () => {
  expect(ALL.map((lesson) => lesson.id).sort()).toEqual(
    [...AS_WRITTEN, ...REWRITTEN, ...NEW].sort(),
  );
});

test("the modules are the course's, in order, and none is empty", () => {
  expect(LESSONS.map((module) => module.title)).toEqual([
    "Start here",
    "Shares and dividends",
    "How IDX works",
    "Costs and tax",
    "Risk",
    "Using steadyhand",
    "The income goal",
    "Strategies",
  ]);
  expect(LESSONS.filter((module) => module.lessons.length === 0)).toEqual([]);
});

test("each module's lessons are in their order, each place once", () => {
  for (const module of LESSONS) {
    const places = module.lessons.map((lesson) => lesson.position);
    expect(places).toEqual([...new Set(places)].sort((one, other) => one - other));
  }
});

test("every lesson a lesson points to ships", () => {
  const ids = new Set(ALL.map((lesson) => lesson.id));
  expect(ALL.flatMap((lesson) => lesson.seeAlso.filter((id) => !ids.has(id)))).toEqual([]);
});

test("every note a lesson explains is one of the core's codes", () => {
  const codes = new Set<string>(Object.values(NOTE_CODES));
  expect(ALL.flatMap((lesson) => lesson.explains.filter((code) => !codes.has(code)))).toEqual([]);
});

test.each(AS_WRITTEN)("%s is the Python lesson's text, word for word", (id) => {
  const shipped = ALL.find((lesson) => lesson.id === id);
  const python = pythonLesson(id);
  expect([shipped?.title, shipped?.summary, shipped?.blocks]).toEqual([
    python.title,
    python.summary,
    python.blocks,
  ]);
});

test.each(ALL.map((lesson) => lesson.id))(
  "%s names no backtest, paper trading, Yahoo, command line or configuration file",
  (id) => {
    expect(
      forbiddenIn(ALL.find((lesson) => lesson.id === id) ?? ALL[0] ?? pythonLesson(id)),
    ).toEqual([]);
  },
);

test.each(ALL.map((lesson) => lesson.id))("%s never advises, nor speaks as we or me", (id) => {
  const words = textsOf(ALL.find((lesson) => lesson.id === id) ?? pythonLesson(id)).flatMap(
    (text) => text.match(/recommend|we\s+suggest|\b(?:we|us|our|ours|me|my)\b/giu) ?? [],
  );
  expect(words).toEqual([]);
});

test("a lesson naming a backtest or a command is refused", () => {
  const planted = lessonFrom(
    '+++\nid = "x.y"\ntitle = "A backtest"\nsummary = "Run steadyhand-idx learn."\nexplains = []\nmodule = "m"\nposition = 1\nsee_also = []\n+++\n\nPaper trading on Yahoo prices.',
  );
  expect(forbiddenIn(planted)).toEqual([
    "A backtest",
    "Run steadyhand-idx learn.",
    "Paper trading on Yahoo prices.",
  ]);
});

const placed = (id: string, module: string, position: number): Lesson => ({
  id,
  title: id,
  summary: id,
  explains: [],
  module,
  position,
  seeAlso: [],
  blocks: [],
});

test("the catalogue holds each module the lessons are in, in the course's order, by place", () => {
  expect(
    catalogue([placed("b", "strategies", 2), placed("a", "strategies", 1), placed("c", "risk", 1)]),
  ).toEqual([
    { title: "Risk", lessons: [placed("c", "risk", 1)] },
    { title: "Strategies", lessons: [placed("a", "strategies", 1), placed("b", "strategies", 2)] },
  ]);
});

test("a lesson in a module the course does not have is refused, naming both", () => {
  expect(() => catalogue([placed("x.y", "backtesting", 1)])).toThrow(
    "x.y is in the module backtesting, which the course does not have",
  );
});
