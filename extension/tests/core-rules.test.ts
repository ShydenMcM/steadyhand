import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, expect, test } from "vitest";
import { browserGlobals, numberTypes, numberWords, typedDeclarations } from "./lib/core-rules.ts";
import { floorBreach } from "./lib/floors.ts";
import { searched } from "./lib/population.ts";
import {
  nodes,
  parse,
  readSource,
  tokens,
  ts,
  typeChecked,
  UnreadableSourceError,
} from "./lib/source.ts";
import { filesUnder, gitListed } from "./lib/walk.ts";

const SUFFIXES = [".ts", ".js"] as const;
const CORE = filesUnder("packages/core/src", SUFFIXES);

const sample = (code: string): ts.SourceFile => parse(code, "sample.ts");

/** Each way core could reach a browser global (AC3), with what the guard reports. */
test.each([
  ["a bare global", "window.alert;", ["line 1: window"]],
  ["document", "document.title;", ["line 1: document"]],
  ["chrome", "chrome.runtime;", ["line 1: chrome"]],
  ["indexedDB", "indexedDB.open('x');", ["line 1: indexedDB"]],
  ["a typeof", "typeof window;", ["line 1: window"]],
  ["a shorthand property", "const a = { window };", ["line 1: window"]],
  ["a property of globalThis", "globalThis.chrome;", ["line 1: globalThis.chrome"]],
  ["a property of self", "self.indexedDB;", ["line 1: self.indexedDB"]],
  ["a key into globalThis", 'globalThis["document"];', ['line 1: globalThis["document"]']],
  ["window's own document", "window.document;", ["line 1: window.document", "line 1: window"]],
])("core reaching %s is refused", (_, code, found) => {
  expect(browserGlobals(sample(code))).toEqual(found);
});

/** Where the same names are keys or members, never the browser's globals. */
test.each([
  ["an object key", "const a = { window: 1n };"],
  ["a property of another object", "page.window;"],
  ["a class field", "class A { window = 1n; }"],
  ["an interface member", "interface A { window: string }"],
  ["a method", "class A { document(): void {} }"],
  ["a method signature", "interface A { chrome(): void }"],
  ["a getter", "class A { get window(): string { return ''; } }"],
  ["a setter", "class A { set window(v: string) {} }"],
  ["an enum member", "enum A { window }"],
  ["a qualified type name", "type A = B.window;"],
  ["a key into another object", 'page["window"];'],
  ["a key into globalThis naming no browser global", 'globalThis["structuredClone"];'],
  ["a string", '"window";'],
])("%s named like a browser global is allowed", (_, code) => {
  expect(browserGlobals(sample(code))).toEqual([]);
});

test("a computed key into a global object cannot be judged, and is refused by name", () => {
  expect(() => browserGlobals(sample("globalThis[key];"))).toThrow(
    new UnreadableSourceError(
      "sample.ts line 1: globalThis[…] with a computed key cannot be judged",
    ),
  );
});

/** Each way core could write a `number` (AC4), with what the guard reports. */
test.each([
  ["an annotation", "let a: number;", "line 1: number"],
  ["an assertion", "const a = b as number;", "line 1: number"],
  ["a satisfies", "const a = b satisfies number;", "line 1: number"],
  ["a type argument", "const a: Array<number> = [];", "line 1: number"],
  ["an array type", "let a: number[];", "line 1: number"],
  ["Number", "Number('1');", "line 1: Number"],
  ["Number's constant", "Number.MAX_SAFE_INTEGER;", "line 1: Number"],
  ["parseFloat", "parseFloat('1');", "line 1: parseFloat"],
  ["parseInt", "parseInt('1', 10);", "line 1: parseInt"],
  ["a decimal", "1.5;", "line 1: literal 1.5"],
  ["an exponent", "1e3;", "line 1: literal 1e3"],
  ["a leading point", ".5;", "line 1: literal .5"],
])("core writing %s is refused", (_, code, found) => {
  expect(numberWords(sample(code))).toEqual([found]);
});

test.each([
  ["a whole-number index", "rows[0];"],
  ["hex", "0xff;"],
  ["octal", "0o17;"],
  ["binary", "0b101;"],
  ["separators", "1_000;"],
  ["a bigint", "100n;"],
  ["a key named Number", "const a = { Number: 1n };"],
  ["a word in a comment", "// number 1.5 Number\n"],
])("%s is allowed by the written-word guard", (_, code) => {
  expect(numberWords(sample(code))).toEqual([]);
});

/** Each value a type can make a `number` without the word (Shyden, 2026-10-06), and the
 * finding. Each is its own file in one program, so the checker is built once. */
const TYPED: readonly (readonly [string, string, readonly string[]])[] = [
  ["an unlabelled whole number", "export const fee = 100;", ["line 1: fee: 100"]],
  ["a let", "export let fee = 100;", ["line 1: fee: number"]],
  ["a length kept in a name", "export const n = [1n].length;", ["line 1: n: number"]],
  [
    "an object literal holding one",
    "export const row = { fee: 100 };",
    ["line 1: row: { fee: number; }", "line 1: fee: number"],
  ],
  ["an array of them", "export const fees = [100];", ["line 1: fees: number[]"]],
  ["a function's result", "export function rate() {\n  return 100;\n}", ["line 1: returns number"]],
  ["an arrow's result", "export const rate = () => 100;", ["line 1: returns number"]],
  [
    "a parameter",
    "export const half = (n = 2) => n;",
    ["line 1: returns number", "line 1: n: number"],
  ],
  [
    "a destructured name",
    "const { length } = [1n];\nexport { length };",
    ["line 1: length: number"],
  ],
  ["a class field", "export class A {\n  fee = 100;\n}", ["line 2: fee: number"]],
  [
    "a literal type in an interface",
    "export interface A {\n  fee: bigint | 1;\n}",
    ["line 2: fee: bigint | 1"],
  ],
  [
    "a method's result",
    "export class A {\n  fee() {\n    return 1;\n  }\n}",
    ["line 2: returns number"],
  ],
  [
    "a getter's result",
    "export class A {\n  get fee() {\n    return 1;\n  }\n}",
    ["line 2: fee: number"],
  ],
  [
    "a callback's parameter",
    "export const xs = [1n].map((x, i) => x + BigInt(i));",
    ["line 1: i: number"],
  ],
  ["a bigint", "export const fee = 100n;", []],
  ["a comparator's result", "export const s = [2n, 1n].toSorted((a, b) => (a < b ? -1 : 1));", []],
  ["a string", 'export const s = "100";', []],
  ["an inline index", "export const first = [1n][0];", []],
  ["a repeated field type", "export const pair = { a: 1n, b: 1n };", []],
];

let fixtures = "";
let checked: ReturnType<typeof typeChecked> | undefined;

beforeAll(() => {
  fixtures = mkdtempSync(join(tmpdir(), "steadyhand-types-"));
  const paths = TYPED.map(([, code], index) => {
    const path = join(fixtures, `case-${String(index)}.ts`);
    writeFileSync(path, `${code}\n`);
    return path;
  });
  checked = typeChecked(paths);
});

afterAll(() => {
  rmSync(fixtures, { recursive: true, force: true });
});

test.each(TYPED.map((row, index) => [...row, index] as const))(
  "the type pass judges %s",
  (_, __, found, index) => {
    const file = checked?.files[index];
    expect(
      file === undefined || checked === undefined ? undefined : numberTypes(checked.checker, file),
    ).toEqual(found);
  },
);

test("core's files are the ones git lists, and as many as recorded", () => {
  expect(CORE).toEqual(gitListed("packages/core/src", SUFFIXES));
  expect(floorBreach("core.files", CORE.length)).toBeUndefined();
});

test("core reaches no browser global", () => {
  const read = CORE.map((path) => ({ path, file: readSource(path) }));
  const identifiers = read.flatMap(({ file }) => nodes(file).filter(ts.isIdentifier));
  const found = read.flatMap(({ path, file }) => browserGlobals(file).map((f) => `${path} ${f}`));
  expect(searched(found, { of: identifiers.length, what: "identifiers in core" })).toEqual([]);
  expect(floorBreach("browser-globals.identifiers", identifiers.length)).toBeUndefined();
});

test("core writes no number", () => {
  const read = CORE.map((path) => ({ path, file: readSource(path) }));
  const judged = read.flatMap(({ file }) => nodes(file));
  const found = read.flatMap(({ path, file }) => numberWords(file).map((f) => `${path} ${f}`));
  expect(searched(found, { of: judged.length, what: "nodes in core" })).toEqual([]);
  expect(floorBreach("number-words.nodes", judged.length)).toBeUndefined();
});

test("no value in core has a number type, written or inferred", () => {
  const { checker, files } = typeChecked(CORE);
  const judged = files.flatMap((file) => typedDeclarations(file));
  const found = files.flatMap((file) =>
    numberTypes(checker, file).map((f) => `${file.fileName} ${f}`),
  );
  expect(searched(found, { of: judged.length, what: "typed values in core" })).toEqual([]);
  expect(floorBreach("number-types.values", judged.length)).toBeUndefined();
});

/** The values the type pass should judge, counted by the token walk instead of the node walk. */
const typedByTokens = (file: ts.SourceFile): number =>
  tokens(file).filter((token) => {
    const { parent } = token;
    const passed =
      ts.isCallExpression(parent.parent) &&
      parent.parent.arguments.includes(parent as ts.Expression);
    if (ts.isIdentifier(token)) {
      return (parent as { name?: ts.Node }).name === token && NAMED_BY_TOKEN.has(parent.kind);
    }
    if (token.kind === ts.SyntaxKind.EqualsGreaterThanToken) {
      return ts.isArrowFunction(parent) && !passed;
    }
    return (
      token.kind === ts.SyntaxKind.FunctionKeyword &&
      (ts.isFunctionDeclaration(parent) || ts.isFunctionExpression(parent)) &&
      !passed
    );
  }).length;

const NAMED_BY_TOKEN = new Set([
  ts.SyntaxKind.VariableDeclaration,
  ts.SyntaxKind.Parameter,
  ts.SyntaxKind.BindingElement,
  ts.SyntaxKind.PropertyDeclaration,
  ts.SyntaxKind.PropertySignature,
  ts.SyntaxKind.PropertyAssignment,
  ts.SyntaxKind.ShorthandPropertyAssignment,
  ts.SyntaxKind.GetAccessor,
  ts.SyntaxKind.MethodDeclaration,
  ts.SyntaxKind.MethodSignature,
]);

test.each(TYPED.map(([name, code]) => [name, code] as const))(
  "the token walk counts the values the type pass judges in %s",
  (_, code) => {
    const file = sample(code);
    expect(typedDeclarations(file)).toHaveLength(typedByTokens(file));
  },
);

test.each(CORE)("%s: the token walk counts the values the type pass judges", (path) => {
  const file = readSource(path);
  expect(typedDeclarations(file)).toHaveLength(typedByTokens(file));
});
