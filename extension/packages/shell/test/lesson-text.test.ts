import { expect, test } from "vitest";
import { lessonFrom } from "../src/lesson-text.ts";

// A lesson as written (spec §13, #244): TOML front matter between `+++` lines, then paragraphs,
// lists and tables with bold and code inline. The panel writes elements and text only, so the
// text is read into blocks and spans, never kept as markup.

const lesson = (body: string, front = ""): string =>
  [
    "+++",
    'id = "idx.lots"',
    'title = "Lots: shares come in hundreds"',
    'summary = "Shares trade in lots of 100."',
    'explains = ["limit.min_lots", "trade.no_bar"]',
    'module = "how-idx-works"',
    "position = 1",
    'see_also = ["idx.ticks"]',
    'sources = ["docs/research/t-rules.md §1"]',
    front,
    "+++",
    "",
    body,
  ].join("\n");

const plain = (text: string) => ({ text, style: "plain" });

test("the front matter gives the lesson's key, title, summary, notes, module, place and links", () => {
  const read = lessonFrom(lesson("One lot is 100 shares."));
  expect(read).toMatchObject({
    id: "idx.lots",
    title: "Lots: shares come in hundreds",
    summary: "Shares trade in lots of 100.",
    explains: ["limit.min_lots", "trade.no_bar"],
    module: "how-idx-works",
    position: 1,
    seeAlso: ["idx.ticks"],
  });
});

test("paragraphs are split on blank lines, their lines joined by a space", () => {
  expect(lessonFrom(lesson("One lot is 100\nshares.\n\nSo buy whole lots.")).blocks).toEqual([
    { kind: "paragraph", spans: [plain("One lot is 100 shares.")] },
    { kind: "paragraph", spans: [plain("So buy whole lots.")] },
  ]);
});

test("bold and code are spans of their own", () => {
  expect(lessonFrom(lesson("Shares trade in **lots**, see `idx.ticks` too.")).blocks).toEqual([
    {
      kind: "paragraph",
      spans: [
        plain("Shares trade in "),
        { text: "lots", style: "strong" },
        plain(", see "),
        { text: "idx.ticks", style: "code" },
        plain(" too."),
      ],
    },
  ]);
});

test("a list's items each start with a dash, and a line after one continues it", () => {
  const body = "Costs:\n\n- **The fee**: what the broker\n  charges.\n- The levy.";
  expect(lessonFrom(lesson(body)).blocks).toEqual([
    { kind: "paragraph", spans: [plain("Costs:")] },
    {
      kind: "list",
      ordered: false,
      items: [
        [{ text: "The fee", style: "strong" }, plain(": what the broker charges.")],
        [plain("The levy.")],
      ],
    },
  ]);
});

test("a numbered list is ordered", () => {
  expect(lessonFrom(lesson("1. Read the page.\n2. Get the orders.")).blocks).toEqual([
    { kind: "list", ordered: true, items: [[plain("Read the page.")], [plain("Get the orders.")]] },
  ]);
});

test("a table has its heading row and its rows, the rule line dropped", () => {
  const body =
    "| Previous close | Highest rise |\n|---|---|\n| up to Rp200 | **35%** |\n| over Rp200 | 25% |";
  expect(lessonFrom(lesson(body)).blocks).toEqual([
    {
      kind: "table",
      heading: [[plain("Previous close")], [plain("Highest rise")]],
      rows: [
        [[plain("up to Rp200")], [{ text: "35%", style: "strong" }]],
        [[plain("over Rp200")], [plain("25%")]],
      ],
    },
  ]);
});

test("empty lists in the front matter are empty", () => {
  const text = lesson("Text.").replace('["limit.min_lots", "trade.no_bar"]', "[]");
  expect(lessonFrom(text).explains).toEqual([]);
});

test("a lesson with no front matter is refused", () => {
  expect(() => lessonFrom("Just text.")).toThrow("a lesson begins with +++ front matter");
});

test("a front matter line that is not `key = value` is refused, naming it", () => {
  expect(() => lessonFrom(lesson("Text.", "loose words"))).toThrow(
    'idx.lots: the front matter line "loose words" is not key = value',
  );
});

test("a front matter field missing or of the wrong kind is refused, naming it", () => {
  expect(() =>
    lessonFrom(lesson("Text.").replace('summary = "Shares trade in lots of 100."', "")),
  ).toThrow("idx.lots: the front matter has no text summary");
  expect(() => lessonFrom(lesson("Text.").replace("position = 1", 'position = "first"'))).toThrow(
    "idx.lots: the front matter has no whole-number position",
  );
  expect(() =>
    lessonFrom(lesson("Text.").replace('see_also = ["idx.ticks"]', 'see_also = "idx.ticks"')),
  ).toThrow("idx.lots: the front matter has no list see_also");
});

test("unclosed bold or code is refused, naming the lesson", () => {
  expect(() => lessonFrom(lesson("A **loose start."))).toThrow(
    "idx.lots: unclosed ** or ` in: A **loose start.",
  );
});

test("a front matter with no id and a line it cannot read names it as a lesson", () => {
  expect(() => lessonFrom("+++\nloose words\n+++\nText.")).toThrow(
    'a lesson: the front matter line "loose words" is not key = value',
  );
});
