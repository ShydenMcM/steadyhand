import { expect, test } from "vitest";
import { floorBreach } from "./lib/floors.ts";
import { assertionsOf, floorConstants, literalFloors, variablesOf } from "./lib/literal-floors.ts";
import { searched } from "./lib/population.ts";
import { codeText, parse, readSource, tokens, ts, UnreadableSourceError } from "./lib/source.ts";
import { filesUnder, gitListed } from "./lib/walk.ts";

const SUFFIXES = [".ts", ".js"] as const;

/** The workspace's tests: every file under `tests/` and each package's `test/`. */
const isTest = (path: string): boolean =>
  path.startsWith("tests/") || path.split("/")[2] === "test";
const TESTS = filesUnder(".", SUFFIXES).filter(isTest);

const sample = (code: string): ts.SourceFile => parse(code, "sample.ts");

/** Each way a test can write a floor by hand (AC1), with what the guard reports. */
test.each([
  [
    "toBeGreaterThanOrEqual",
    "expect(n).toBeGreaterThanOrEqual(197);",
    "toBeGreaterThanOrEqual(197)",
  ],
  ["toBeGreaterThan", "expect(n).toBeGreaterThan(196);", "toBeGreaterThan(196)"],
  ["a negated toBeLessThan", "expect(n).not.toBeLessThan(197);", "not.toBeLessThan(197)"],
  [
    "a negated toBeLessThanOrEqual",
    "expect(n).not.toBeLessThanOrEqual(196);",
    "not.toBeLessThanOrEqual(196)",
  ],
  ["a resolved value", "await expect(p).resolves.toBeGreaterThan(5);", "toBeGreaterThan(5)"],
  ["a soft assertion", "expect.soft(n).toBeGreaterThan(5);", "toBeGreaterThan(5)"],
  ["a polled assertion", "await expect.poll(f).toBeGreaterThan(5);", "toBeGreaterThan(5)"],
  ["a separated literal", "expect(n).toBeGreaterThan(1_000);", "toBeGreaterThan(1_000)"],
  ["a bigint", "expect(n).toBeGreaterThan(5n);", "toBeGreaterThan(5n)"],
  ["a negative literal", "expect(n).toBeGreaterThan(-1);", "toBeGreaterThan(-1)"],
  ["a comparison", "expect(n >= 197).toBe(true);", "n >= 197"],
  ["a strict comparison", "expect(n > 196).toBe(true);", "n > 196"],
  ["a reversed comparison", "expect(197 <= n).toBe(true);", "197 <= n"],
  ["a reversed strict comparison", "expect(196 < n).toBe(true);", "196 < n"],
])("a floor written as %s is refused by line", (_, code, found) => {
  expect(literalFloors(sample(`\n${code}\n`))).toEqual([`line 2: ${found}`]);
});

test("a floor bound to a named literal is refused, naming both", () => {
  expect(
    literalFloors(sample("const MIN = 197;\nexpect(n).toBeGreaterThanOrEqual(MIN);\n")),
  ).toEqual(["line 2: toBeGreaterThanOrEqual(MIN = 197)"]);
});

test.each([
  ["FILES_FLOOR", "const FILES_FLOOR = 197;", "line 1: FILES_FLOOR = 197"],
  ["filesFloor", "let filesFloor = 196;", "line 1: filesFloor = 196"],
  ["a negative one", "const FLOOR = -1;", "line 1: FLOOR = -1"],
])("a constant named %s set to a literal is refused", (_, code, found) => {
  expect(floorConstants(sample(code))).toEqual([found]);
});

/** Bounds that are not floors, and floors that are recorded. */
test.each([
  ["a non-emptiness check", "expect(n).toBeGreaterThan(0);"],
  ["a ceiling", "expect(ms).toBeLessThan(30_000);"],
  ["a negated lower bound", "expect(n).not.toBeGreaterThan(5);"],
  ["a computed bound", "expect(n).toBeGreaterThan(rows.length);"],
  ["a negated computed bound", "expect(n).toBeGreaterThan(-rows.length);"],
  ["a bound kept in a computed name", "const min = rows.length;\nexpect(n).toBeGreaterThan(min);"],
  ["a recorded floor", 'expect(floorBreach("a.files", n)).toBeUndefined();'],
  ["a comparison outside an assertion", "if (n > 197) {\n  throw new Error();\n}"],
  ["a comparison against zero", "expect(n > 0).toBe(true);"],
  ["a matcher on something that is not an assertion", "helper(n).toBeGreaterThan(5);"],
  ["a matcher with no bound", "expect(n).toBeGreaterThan();"],
  ["a floor in a comment or a string", '// toBeGreaterThan(197)\nconst s = "FLOOR = 3";'],
  ["a floor constant that is computed", "const FILES_FLOOR = files.length;"],
  ["a floor constant of zero", "const FLOOR = 0;"],
  ["a floor constant with no value", "let floor;"],
])("%s is not a literal floor", (_, code) => {
  expect(literalFloors(sample(code))).toEqual([]);
  expect(floorConstants(sample(code))).toEqual([]);
});

test.each([
  ["an imported name", 'import { MIN } from "./m.ts";\nexpect(n).toBeGreaterThan(MIN);', "MIN"],
  ["a parameter", "(min: number) =>\n  expect(n).toBeGreaterThan(min);", "min"],
  ["a name declared with no value", "let min;\nexpect(n).toBeGreaterThan(min);", "min"],
])("a bound held in %s cannot be classified, and is refused by name", (_, code, name) => {
  expect(() => literalFloors(sample(code))).toThrow(
    new UnreadableSourceError(
      `sample.ts line 2: cannot tell whether ${name} is a literal floor; bound an assertion by ` +
        "a value computed in the test, or by a recorded floor",
    ),
  );
});

test("the test files read are the ones git lists, and as many as recorded", () => {
  expect(TESTS).toEqual(gitListed(".", SUFFIXES).filter(isTest));
  expect(floorBreach("literal-floors.files", TESTS.length)).toBeUndefined();
});

/** Assertions counted in the code text instead of the tree: `expect (`, `expect . soft (`. */
const ASSERTION_TEXT = /(?<!\. )\bexpect (?:\. (?:soft|poll) )?\(/gu;

test.each(TESTS)("%s: the tree reader finds the assertions the code text holds", (path) => {
  const file = readSource(path);
  expect(assertionsOf(file)).toHaveLength(codeText(file).match(ASSERTION_TEXT)?.length ?? 0);
});

test.each(TESTS)("%s: the tree reader finds the variables the token walk names", (path) => {
  const file = readSource(path);
  const named = tokens(file).filter(
    (token) =>
      ts.isIdentifier(token) &&
      ts.isVariableDeclaration(token.parent) &&
      token.parent.name === token,
  );
  expect(variablesOf(file)).toHaveLength(named.length);
});

test("no test bounds an assertion by a literal floor", () => {
  const read = TESTS.map((path) => ({ path, file: readSource(path) }));
  const assertions = read.flatMap(({ file }) => assertionsOf(file));
  const found = read.flatMap(({ path, file }) => literalFloors(file).map((f) => `${path} ${f}`));
  expect(searched(found, { of: assertions.length, what: "assertions in the tests" })).toEqual([]);
  expect(floorBreach("literal-floors.assertions", assertions.length)).toBeUndefined();
});

test("no test keeps a floor in a constant", () => {
  const read = TESTS.map((path) => ({ path, file: readSource(path) }));
  const variables = read.flatMap(({ file }) => variablesOf(file));
  const found = read.flatMap(({ path, file }) => floorConstants(file).map((f) => `${path} ${f}`));
  expect(searched(found, { of: variables.length, what: "variables in the tests" })).toEqual([]);
  expect(floorBreach("literal-floors.variables", variables.length)).toBeUndefined();
});
