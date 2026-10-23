import { expect, test } from "vitest";
import { floorBreach } from "../lib/floors.ts";
import { holderNames, moduleMocks } from "../lib/module-mocks.ts";
import { codeText, parse, readSource, ts, UnreadableSourceError } from "../lib/source.ts";
import { searched } from "../lib/population.ts";
import { filesUnder, gitListed } from "../lib/walk.ts";

const SUFFIXES = [".ts", ".mts", ".cts", ".js", ".mjs", ".cjs"] as const;
const FILES = filesUnder(".", SUFFIXES);

const sample = (code: string): ts.SourceFile => parse(code, "sample.ts");

/** Each way a test could mock a module or hide `vi` (#394), with what the guard reports. */
test.each([
  ["vi.mock", 'vi.mock("x");', ["line 1: vi.mock"]],
  ["vi.unmock", 'vi.unmock("x");', ["line 1: vi.unmock"]],
  ["vi.hoisted", "const a = vi.hoisted(() => 1);", ["line 1: vi.hoisted"]],
  ["vi.doMock", 'vi.doMock("x");', ["line 1: vi.doMock"]],
  ["vi.doUnmock", 'vi.doUnmock("x");', ["line 1: vi.doUnmock"]],
  ["vi.importActual", 'await vi.importActual("x");', ["line 1: vi.importActual"]],
  ["vi.importMock", 'await vi.importMock("x");', ["line 1: vi.importMock"]],
  ["vitest's own name", 'vitest.mock("x");', ["line 1: vitest.mock"]],
  ["type arguments", 'vi.mock<typeof import("x")>("x");', ["line 1: vi.mock"]],
  ["an optional chain", 'vi?.doMock("x");', ["line 1: vi.doMock"]],
  ["a member read, not called", "const m = vi.mock;", ["line 1: vi.mock"]],
  ["a key", 'vi["mock"]("x");', ['line 1: vi["mock"]']],
  ["a template key", 'vi[`doMock`]("x");', ['line 1: vi["doMock"]']],
  ["vi read from globalThis", 'globalThis.vi.mock("x");', ["line 1: vi.mock"]],
  ["vitest read from a module", "helpers.vitest.hoisted(() => 1);", ["line 1: vitest.hoisted"]],
  ["vi read from a module by key", 'helpers["vi"].mock("x");', ["line 1: vi.mock"]],
  ["a call split over lines", 'vi\n  /* c */ .mock(\n  "x",\n);', ["line 1: vi.mock"]],
  ["vi renamed on import", 'import { vi as v } from "vitest";', ["line 1: vi renamed on import"]],
  ["a name renamed to vi", 'import { x as vi } from "y";', ["line 1: vi renamed on import"]],
  [
    "vitest renamed on import",
    'import { vitest as v } from "vitest";',
    ["line 1: vitest renamed on import"],
  ],
  ["a string import name", 'import { "vi" as v } from "vitest";', ["line 1: vi renamed on import"]],
  ["vi renamed on export", 'export { vi as v } from "vitest";', ["line 1: vi renamed on export"]],
  ["a namespace import", 'import * as V from "vitest";', ["line 1: vitest imported whole"]],
  ["a default import", 'import V from "vitest";', ["line 1: vitest imported whole"]],
  ["an export of everything", 'export * from "vitest";', ["line 1: vitest exported whole"]],
  ["a namespace export", 'export * as V from "vitest";', ["line 1: vitest exported whole"]],
  ["an import call", 'await import("vitest");', ["line 1: vitest imported by a call"]],
  ["a require call", 'require("vitest");', ["line 1: vitest imported by a call"]],
  [
    "vi held",
    "const v = vi;",
    ["line 1: vi held, passed or declared, so its members cannot be judged"],
  ],
  ["vi passed", "f(vi);", ["line 1: vi held, passed or declared, so its members cannot be judged"]],
  [
    "vi in a shorthand property",
    "const o = { vi };",
    ["line 1: vi held, passed or declared, so its members cannot be judged"],
  ],
  [
    "vi spread",
    "const o = { ...vi };",
    ["line 1: vi held, passed or declared, so its members cannot be judged"],
  ],
  [
    "vi destructured",
    "const { mock } = vi;",
    ["line 1: vi held, passed or declared, so its members cannot be judged"],
  ],
  [
    "vi declared",
    "const vi = helpers;",
    ["line 1: vi held, passed or declared, so its members cannot be judged"],
  ],
  [
    "vi as a parameter",
    "function f(vi: unknown) {}",
    ["line 1: vi held, passed or declared, so its members cannot be judged"],
  ],
  [
    "vi bound from another object",
    "const { vi: v } = helpers;",
    ["line 1: vi held, passed or declared, so its members cannot be judged"],
  ],
  [
    "vi exported as the default",
    "export default vi;",
    ["line 1: vi held, passed or declared, so its members cannot be judged"],
  ],
  [
    "globalThis's vi held",
    "const v = globalThis.vi;",
    ["line 1: vi held, passed or declared, so its members cannot be judged"],
  ],
  [
    "a module's vi held by key",
    'const v = helpers["vi"];',
    ["line 1: vi held, passed or declared, so its members cannot be judged"],
  ],
])("a test reaching %s is refused", (_, code, found) => {
  expect(moduleMocks(sample(code))).toEqual(found);
});

/** Where the same names are vi's other members, keys, types, text or another object's. */
test.each([
  ["vi.fn", "vi.fn();"],
  ["vi.spyOn", 'vi.spyOn(console, "log");'],
  ["vi.restoreAllMocks", "vi.restoreAllMocks();"],
  ["a key naming another member", 'vi["fn"]();'],
  ["a mock function's record", "fn.mock.calls;"],
  ["another object's mock", 'page.mock("x");'],
  ["vi imported by name", 'import { vi } from "vitest";'],
  ["vi renamed to itself", 'import { vi as vi } from "vitest";'],
  ["vi exported by name", 'export { vi } from "vitest";'],
  ["a type imported from vitest", 'import type { Mock } from "vitest";'],
  ["an import of another module", 'await import("node:fs");'],
  ["an object key", "const o = { vi: 1 };"],
  ["a class field and a method", "class A { vi = 1; mock() {} }"],
  ["an interface member", "interface A { vitest: string }"],
  ["a type named through vi", "type T = vi.Mock;"],
  ["a string", 'const s = "vi.mock(\\"x\\")";'],
  ["a comment", '// vi.mock("x")\nconst a = 1;'],
])("%s is allowed", (_, code) => {
  expect(moduleMocks(sample(code))).toEqual([]);
});

test("a computed key into vi cannot be judged, and is refused by name", () => {
  expect(() => moduleMocks(sample('vi[name]("x");'))).toThrow(
    new UnreadableSourceError("sample.ts line 1: vi[…] with a computed key cannot be judged"),
  );
});

/** The names in `file`'s code text, counted by its token walk: independent of `holderNames`. */
const namesByText = (file: ts.SourceFile): number =>
  codeText(file).match(/(?<![\w$#])(?:vi|vitest)(?![\w$])/gu)?.length ?? 0;

test.each([
  ["a call", 'vi.mock("x");', 1],
  ["two names and a string", 'import { vi, vitest } from "vitest";', 2],
  ["a name in a comment and a template", "/* vi */ const s = `vi ${vitest.fn()}`;", 1],
  ["a private name", "class A { #vi = 1; }", 0],
])("the text count reads %s as the parse tree does", (_, code, count) => {
  const file = sample(code);
  expect(holderNames(file)).toHaveLength(count);
  expect(namesByText(file)).toBe(count);
});

test("the extension's files are the ones git lists, and as many as recorded", () => {
  expect(FILES).toEqual(gitListed(".", SUFFIXES));
  expect(floorBreach("module-mocks.files", FILES.length)).toBeUndefined();
});

test("no extension file mocks a module", () => {
  const read = FILES.map((path) => ({ path, file: readSource(path) }));
  const names = read.flatMap(({ file }) => holderNames(file));
  const found = read.flatMap(({ path, file }) => moduleMocks(file).map((f) => `${path} ${f}`));
  expect(
    searched(found, { of: names.length, what: "vi and vitest names in the extension" }),
  ).toEqual([]);
  expect(floorBreach("module-mocks.names", names.length)).toBeUndefined();
});

test.each(FILES)(
  "%s: the text count reads its vi and vitest names as the parse tree does",
  (path) => {
    const file = readSource(path);
    expect(holderNames(file)).toHaveLength(namesByText(file));
  },
);
