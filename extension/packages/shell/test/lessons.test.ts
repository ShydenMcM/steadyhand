import { readFileSync } from "node:fs";
import { NOTE_CODES } from "@steadyhand/core";
import { expect, test } from "vitest";
import { lessonFrom, type Lesson } from "../src/lesson-text.ts";
import { catalogue, LESSONS } from "../src/lessons.ts";
import { identicalAllowed } from "../src/words.ts";

// The lessons the extension ships (#244, spec §13): the Python course's lessons, less those that
// describe what the extension does not do, sixteen rewritten for it, and six new.

/** Kept as written: their text is the Python lesson's, word for word. */
const AS_WRITTEN = [
  "costs.sale_tax",
  "costs.stamp_duty",
  "dividends.basics",
  "idx.auto_reject",
  "idx.lots",
  "idx.settlement",
  "idx.ticks",
  "income.calendar",
  "income.goal",
  "income.run_rate",
  "shares.basics",
  "shares.cost_basis",
  "shares.splits",
] as const;
const REWRITTEN = [
  "costs.trading",
  "idx.sessions",
  "idx.special_monitoring",
  "idx.universe",
  "orders.not_tradable",
  "risk.drawdown",
  "risk.limits",
  "risk.returns",
  "shares.prices",
  "start.explanations",
  "start.welcome",
  "strategies.buy_and_hold",
  "strategies.dividend_growth",
  "strategies.holding_cash",
  "strategies.monthly_savings",
  "tax.dividend",
] as const;
const NEW = [
  "broker.reading",
  "orders.limit_prices",
  "strategies.ex_date",
  "strategies.high_yield",
  "strategies.low_volatility",
  "strategies.ma_trend",
  "strategies.momentum_rotation",
  "strategies.total_return",
] as const;

const ALL: readonly Lesson[] = LESSONS.en.flatMap((module) => module.lessons);

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
 * the Python configuration file (any "configuration", #548), or a data folder (#544). */
const FORBIDDEN =
  /backtest|paper[ -]?trad|paper run|yahoo|steadyhand\.toml|steadyhand-idx|command line|\bCLI\b|explain command|configuration|data folder/iu;
const forbiddenIn = (lesson: Lesson): string[] =>
  textsOf(lesson).filter((text) => FORBIDDEN.test(text));

test("the ex-date lesson states what was measured, what was assumed, and that it is a coin flip", () => {
  const lesson = ALL.find((one) => one.id === "strategies.ex_date");
  for (const fact of [
    "258 trades",
    "+0.25%",
    "-0.08%",
    "+0.57%",
    "52%",
    "0.15%",
    "0.25%",
    "10%",
    "public data source",
    "coin flip",
  ]) {
    expect(JSON.stringify(lesson?.blocks)).toContain(fact);
  }
});

test("the course ships the lessons kept as written, the rewritten ones and the new ones", () => {
  expect(ALL.map((lesson) => lesson.id).sort()).toEqual(
    [...AS_WRITTEN, ...REWRITTEN, ...NEW].sort(),
  );
});

test("the modules are the course's, in order, and none is empty", () => {
  expect(LESSONS.en.map((module) => module.title)).toEqual([
    "Start here",
    "Shares and dividends",
    "How IDX works",
    "Costs and tax",
    "Risk",
    "Using steadyhand",
    "The income goal",
    "Strategies",
  ]);
  expect(LESSONS.en.filter((module) => module.lessons.length === 0)).toEqual([]);
});

test("each module's lessons are in their order, each place once", () => {
  for (const module of LESSONS.en) {
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
  "%s names no backtest, paper trading, Yahoo, command line, configuration or data folder",
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

test("a lesson naming a data folder is refused (#544)", () => {
  const planted = lessonFrom(
    '+++\nid = "x.y"\ntitle = "T"\nsummary = "S."\nexplains = []\nmodule = "m"\nposition = 1\nsee_also = []\n+++\n\nKeep the list in your Data Folder.',
  );
  expect(forbiddenIn(planted)).toEqual(["Keep the list in your Data Folder."]);
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

// The lessons in Indonesian (#251 AC1-AC2): every English lesson has one, in the same module and
// place, explaining the same notes and pointing to the same lessons, with blocks of the same
// shape, and none is its English left untranslated.

const INDONESIAN: readonly Lesson[] = LESSONS.id.flatMap((module) => module.lessons);
const IDS = ALL.map((lesson) => lesson.id).sort();
const englishOf = (id: string): Lesson =>
  ALL.find((lesson) => lesson.id === id) ?? pythonLesson(id);
const indonesianOf = (id: string): Lesson | undefined =>
  INDONESIAN.find((lesson) => lesson.id === id);

/** A lesson's blocks with their words left out: each block's kind and how many items, rows and
 * cells it has. */
const shapeOf = (lesson: Lesson | undefined): unknown =>
  lesson?.blocks.map((block) => {
    if (block.kind === "paragraph") {
      return "paragraph";
    }
    if (block.kind === "list") {
      return [block.ordered ? "ordered" : "list", block.items.length];
    }
    return ["table", block.heading.length, block.rows.map((row) => row.length)];
  });

test("the Indonesian course has every English lesson, and no other", () => {
  expect(INDONESIAN.map((lesson) => lesson.id).sort()).toEqual(IDS);
});

test("the Indonesian modules are the course's, in order", () => {
  expect(LESSONS.id.map((module) => module.title)).toEqual([
    "Mulai di sini",
    "Saham dan dividen",
    "Cara kerja BEI",
    "Biaya dan pajak",
    "Risiko",
    "Memakai steadyhand",
    "Target pendapatan",
    "Strategi",
  ]);
});

test.each(IDS)("%s in Indonesian keeps its module, place, notes, links and shape", (id) => {
  const english = englishOf(id);
  const indonesian = indonesianOf(id);
  expect([
    indonesian?.module,
    indonesian?.position,
    indonesian?.explains,
    indonesian?.seeAlso,
    shapeOf(indonesian),
  ]).toEqual([
    english.module,
    english.position,
    english.explains,
    english.seeAlso,
    shapeOf(english),
  ]);
});

/** A lesson's words outside code spans: a code span is a name (a strategy, a setting), the same in
 * every language. */
const proseOf = (lesson: Lesson): string[] => [
  lesson.title,
  lesson.summary,
  ...lesson.blocks
    .flatMap((block) => {
      if (block.kind === "paragraph") {
        return block.spans;
      }
      if (block.kind === "list") {
        return block.items.flat();
      }
      return [block.heading, ...block.rows].flat(2);
    })
    .filter((span) => span.style !== "code")
    .map((span) => span.text),
];

test.each(IDS)("%s in Indonesian is not its English left untranslated", (id) => {
  const english = new Set(proseOf(englishOf(id)));
  const indonesian = indonesianOf(id);
  const left = (indonesian === undefined ? ["(missing)"] : proseOf(indonesian)).filter(
    (text) => english.has(text) && !identicalAllowed(text.trim()),
  );
  expect(left).toEqual([]);
});

test.each(IDS)("%s in Indonesian never advises, nor speaks as kami or kita", (id) => {
  const indonesian = indonesianOf(id);
  const words = (indonesian === undefined ? ["(missing)"] : textsOf(indonesian)).flatMap(
    (text) =>
      text.match(/merekomendasikan|rekomendasi|kami\s+sarankan|\b(?:kami|kita)\b|\(missing\)/giu) ??
      [],
  );
  expect(words).toEqual([]);
});

// A lesson that sends the reader to the next lesson needs one at the next place in its module
// (#546).
test.each(ALL.map((lesson) => lesson.id))(
  "%s sends the reader to no next lesson that does not ship",
  (id) => {
    const lesson = ALL.find((one) => one.id === id) ?? pythonLesson(id);
    const next = ALL.some(
      (one) => one.module === lesson.module && one.position === lesson.position + 1,
    );
    expect(textsOf(lesson).filter((text) => /next lesson/iu.test(text) && !next)).toEqual([]);
  },
);
