import { expect, test } from "vitest";
import { NOTE_CODES } from "../../packages/core/src/notes.ts";
import { LESSONS } from "../../packages/shell/src/lessons.ts";
import { nodes, parse, readSource, ts } from "../lib/source.ts";
import { filesUnder, gitListed } from "../lib/walk.ts";

// Every note code the core can raise has a lesson that explains it (#244 AC4, spec §13). What the
// core can raise is read from its code: each `NOTE_CODES.X` it names, through the compiler's parse
// tree, so a name in a comment or a string is not counted. A code declared and never raised (a
// later story's) needs no lesson yet.

const CORE = filesUnder("packages/core/src", [".ts"]);

/** The codes `file` names as `NOTE_CODES.X`. */
const codesIn = (file: ts.SourceFile): string[] =>
  nodes(file).flatMap((node) =>
    ts.isPropertyAccessExpression(node) &&
    ts.isIdentifier(node.expression) &&
    node.expression.text === "NOTE_CODES" &&
    node.name.text in NOTE_CODES
      ? [NOTE_CODES[node.name.text as keyof typeof NOTE_CODES]]
      : [],
  );

test("the core's files walked are those git lists", () => {
  expect(CORE).toEqual(gitListed("packages/core/src", [".ts"]));
});

// In each language the lessons ship in (#251).
test.each(["en", "id"] as const)(
  "every note code the core raises has a lesson in %s that explains it",
  (language) => {
    const raised = [...new Set(CORE.flatMap((path) => codesIn(readSource(path))))].sort();
    expect(raised.length).toBeGreaterThan(0);
    const explained = new Set(
      LESSONS[language].flatMap((module) => module.lessons.flatMap((l) => l.explains)),
    );
    expect(raised.filter((code) => !explained.has(code))).toEqual([]);
  },
);

test("a code named only in a comment or a string is not counted as raised", () => {
  const file = parse(
    '// NOTE_CODES.TRADE_FROZEN\nconst text = "NOTE_CODES.TRADE_FROZEN";\nuse(NOTE_CODES.MISSING_PAGE, text);',
    "planted.ts",
  );
  expect(codesIn(file)).toEqual(["missing.page"]);
});
