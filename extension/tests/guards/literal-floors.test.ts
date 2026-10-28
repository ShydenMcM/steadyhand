import { expect, test } from "vitest";
import { floorBreach } from "../lib/floors.ts";
import { assertionsOf, floorConstants, literalFloors, variablesOf } from "../lib/literal-floors.ts";
import { foundIn, searched } from "../lib/population.ts";
import { codeText, parse, readSource, tokens, ts, UnreadableSourceError } from "../lib/source.ts";
import { filesUnder, gitListed } from "../lib/walk.ts";

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
  // A literal anywhere in the bound, not only as its whole (#362).
  ["arithmetic", "expect(n).toBeGreaterThanOrEqual(400 + 20);", "toBeGreaterThanOrEqual(400 + 20)"],
  [
    "a literal inside a call",
    "expect(n).toBeGreaterThanOrEqual(Math.max(found.length, 5));",
    "toBeGreaterThanOrEqual(Math.max(found.length, 5))",
  ],
  ["a cast", "expect(n).toBeGreaterThan(5 as number);", "toBeGreaterThan(5 as number)"],
  ["parentheses", "expect(n).toBeGreaterThan((197));", "toBeGreaterThan((197))"],
  ["arithmetic in a comparison", "expect(n >= 400 + 20).toBe(true);", "n >= 400 + 20"],
  [
    "a call in a comparison",
    "expect(n >= Math.max(found.length, 5)).toBe(true);",
    "n >= Math.max(found.length, 5)",
  ],
  ["a cast in a comparison", "expect(n > (5 as number)).toBe(true);", "n > (5 as number)"],
  [
    "a comparison whose lower side is arithmetic",
    "expect(ms / 1000 < 30).toBe(true);",
    "ms / 1000 < 30",
  ],
  ["a reversed matcher", "expect(5).toBeLessThan(n);", "expect(5).toBeLessThan(n)"],
  [
    "a negated reversed matcher",
    "expect(5).not.toBeGreaterThan(n);",
    "expect(5).not.toBeGreaterThan(n)",
  ],
  [
    "a reversed matcher on a cast",
    "expect(5 as number).toBeLessThanOrEqual(n);",
    "expect(5 as number).toBeLessThanOrEqual(n)",
  ],
  [
    "a reversed matcher on arithmetic",
    "expect(400 + 20).toBeLessThan(n);",
    "expect(400 + 20).toBeLessThan(n)",
  ],
  // A function encloses it, but the name read is no parameter of it (#432).
  [
    "a literal beside a name that is no parameter",
    "(opts: object) => expect(n).toBeGreaterThan(Math.max(found.length, 5));",
    "toBeGreaterThan(Math.max(found.length, 5))",
  ],
])("a floor written as %s is refused by line", (_, code, found) => {
  expect(literalFloors(sample(`\n${code}\n`))).toEqual([`line 2: ${found}`]);
});

/** A floor reached through a name the test declares, directly or followed to a fixed point. */
test.each([
  [
    "a literal",
    "const MIN = 197;",
    "expect(n).toBeGreaterThanOrEqual(MIN);",
    "toBeGreaterThanOrEqual(MIN = 197)",
  ],
  [
    "arithmetic",
    "const MIN = 400 + 20;",
    "expect(n).toBeGreaterThan(MIN);",
    "toBeGreaterThan(MIN = 400 + 20)",
  ],
  [
    "another name",
    "const A = 5, MIN = A;",
    "expect(n).toBeGreaterThan(MIN);",
    "toBeGreaterThan(MIN = A)",
  ],
  [
    "a name inside a call",
    "const MIN = 5;",
    "expect(n).toBeGreaterThan(Math.max(found.length, MIN));",
    "toBeGreaterThan(Math.max(found.length, MIN))",
  ],
  ["a name in a comparison", "const MIN = 5;", "expect(n >= MIN).toBe(true);", "n >= MIN"],
  [
    "a reversed matcher's subject",
    "const MIN = 5;",
    "expect(MIN).toBeLessThan(n);",
    "expect(MIN).toBeLessThan(n)",
  ],
])("a floor bound to a name declared with %s is refused, naming it", (_, declared, code, found) => {
  expect(literalFloors(sample(`${declared}\n${code}\n`))).toEqual([`line 2: ${found}`]);
});

test.each([
  ["FILES_FLOOR", "const FILES_FLOOR = 197;", "line 1: FILES_FLOOR = 197"],
  ["filesFloor", "let filesFloor = 196;", "line 1: filesFloor = 196"],
  ["a negative one", "const FLOOR = -1;", "line 1: FLOOR = -1"],
  ["arithmetic (#362)", "const FLOOR = 400 + 20;", "line 1: FLOOR = 400 + 20"],
  ["a cast (#362)", "const FLOOR = 5 as number;", "line 1: FLOOR = 5 as number"],
  ["a name (#362)", "const MIN = 5;\nconst FLOOR = MIN;", "line 2: FLOOR = MIN"],
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
  // What #362's wider reading must still leave alone.
  ["a bound computed from two lengths", "expect(n).toBeGreaterThan(Math.max(a.length, b.length));"],
  ["a bound of zero in parentheses", "expect(n).toBeGreaterThan((0));"],
  ["a ceiling on arithmetic", "expect(ms / 1000).toBeLessThan(30);"],
  ["a negated bound computed from a length", "expect(n).not.toBeLessThan(rows.length);"],
  [
    "a property named like a declared literal",
    "const length = 5;\nexpect(n).toBeGreaterThan(rows.length);",
  ],
  [
    "the object of a property read",
    "const rows = [1, 2];\nexpect(n).toBeGreaterThan(rows.length);",
  ],
  ["the object of an element read", "const rows = [1, 2];\nexpect(n).toBeGreaterThan(rows[i]);"],
  ["a cycle of names", "const A = B;\nconst B = A;\nexpect(n).toBeGreaterThan(A);"],
  // A parameter that the bound never reads (#432).
  [
    "a property named like a parameter",
    "(length: number) => expect(n).toBeGreaterThan(rows.length);",
  ],
  [
    "an object key named like a parameter",
    "(min: number) => expect(n).toBeGreaterThan(pick({ min: rows }).length);",
  ],
  ["a parameter only in the subject", "(n: number) => expect(n).toBeGreaterThan(rows.length);"],
  [
    "a parameter of a callback inside the bound",
    "expect(n).toBeGreaterThan(rows.filter((row) => row.ok).length);",
  ],
  ["a floor constant computed in a call", "const FLOOR = Math.max(a.length, b.length);"],
  // Found by CI on the real tree (#362): a floor-named function or fixture is not a floor.
  [
    "a floor-named helper whose body holds a literal",
    "const floorsFile = (x: object): string => JSON.stringify(x, null, 2);",
  ],
  [
    "a floor-named value from a call with a literal",
    'const floors = floorsFile({ "a.files": 3 });',
  ],
  [
    "a bound from a helper whose body holds a literal",
    "const count = (): number => rows.length + 1;\nexpect(n).toBeGreaterThan(count());",
  ],
  ["a reversed matcher on zero", "expect(0).toBeLessThan(n);"],
])("%s is not a literal floor", (_, code) => {
  expect(literalFloors(sample(code))).toEqual([]);
  expect(floorConstants(sample(code))).toEqual([]);
});

test.each([
  ["an imported name", 'import { MIN } from "./m.ts";\nexpect(n).toBeGreaterThan(MIN);', "MIN"],
  ["a parameter", "(min: number) =>\n  expect(n).toBeGreaterThan(min);", "min"],
  ["a name declared with no value", "let min;\nexpect(n).toBeGreaterThan(min);", "min"],
  // A parameter reached anywhere in the bound (#432).
  [
    "a parameter's property",
    "(opts: { min: number }) =>\n  expect(n).toBeGreaterThan(opts.min);",
    "opts",
  ],
  ["a parameter's element", "(mins: number[]) =>\n  expect(n).toBeGreaterThan(mins[0]);", "mins"],
  [
    "a parameter nested in a call",
    "(min: number) =>\n  expect(n).toBeGreaterThan(Math.max(found.length, min));",
    "min",
  ],
  [
    "a parameter in a comparison",
    "(opts: { min: number }) =>\n  expect(n >= opts.min).toBe(true);",
    "opts",
  ],
  [
    "a destructured parameter",
    "({ min }: { min: number }) =>\n  expect(n).toBeGreaterThan(Math.max(found.length, min));",
    "min",
  ],
  [
    "a parameter destructured from an array",
    "([, min]: number[]) =>\n  expect(n).toBeGreaterThan(Math.max(found.length, min));",
    "min",
  ],
  [
    "an outer function's parameter",
    '(min: number) => {\n  test("t", () => expect(n).toBeGreaterThan(min + found.length));\n};',
    "min",
  ],
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
  const found = foundIn(
    read,
    ({ path }) => path,
    ({ file }) => literalFloors(file),
  );
  expect(searched(found, { of: assertions.length, what: "assertions in the tests" })).toEqual([]);
  expect(floorBreach("literal-floors.assertions", assertions.length)).toBeUndefined();
});

test("no test keeps a floor in a constant", () => {
  const read = TESTS.map((path) => ({ path, file: readSource(path) }));
  const variables = read.flatMap(({ file }) => variablesOf(file));
  const found = foundIn(
    read,
    ({ path }) => path,
    ({ file }) => floorConstants(file),
  );
  expect(searched(found, { of: variables.length, what: "variables in the tests" })).toEqual([]);
  expect(floorBreach("literal-floors.variables", variables.length)).toBeUndefined();
});
