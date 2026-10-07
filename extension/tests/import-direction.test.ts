import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "vitest";
import { floorBreach } from "./lib/floors.ts";
import { importsOf, layerOf, targetOf, upstreamImports } from "./lib/imports.ts";
import { searched } from "./lib/population.ts";
import {
  EXTENSION,
  parse,
  preScannedImports,
  readSource,
  UnreadableSourceError,
} from "./lib/source.ts";
import { filesUnder, gitListed } from "./lib/walk.ts";

const SUFFIXES = [".ts", ".js"] as const;
const PACKAGE_FILES = filesUnder("packages", SUFFIXES);
const WORKSPACE_FILES = filesUnder(".", SUFFIXES);

/** Each way the workspace can import a module (AC3), naming shell. */
const FORMS: readonly (readonly [string, string])[] = [
  ["an import", 'import { a } from "@steadyhand/shell";'],
  ["a type-only import", 'import type { A } from "@steadyhand/shell";'],
  ["a side-effect import", 'import "@steadyhand/shell";'],
  ["an export from", 'export { a } from "@steadyhand/shell";'],
  ["an export of everything from", 'export * from "@steadyhand/shell";'],
  ["an import-equals require", 'import a = require("@steadyhand/shell");'],
  ["a dynamic import", 'await import("@steadyhand/shell");'],
  ["a require call", 'require("@steadyhand/shell");'],
  ["a type's import", 'type A = import("@steadyhand/shell").A;'],
  ["a relative path into another package", 'import { a } from "../../shell/src/side-panel.ts";'],
];

test.each(FORMS)("%s from core is refused by file and line", (_, code) => {
  const path = "packages/core/src/sample.ts";
  expect(upstreamImports(path, parse(`\n${code}\n`, path))).toEqual([
    expect.stringMatching(/^packages\/core\/src\/sample\.ts line 2: core imports shell \(/u),
  ]);
});

test.each([
  ["core", "history"],
  ["core", "readers"],
  ["core", "shell"],
  ["readers", "shell"],
  ["history", "shell"],
])("%s importing %s is refused", (from, to) => {
  const path = `packages/${from}/src/sample.ts`;
  expect(upstreamImports(path, parse(`import "@steadyhand/${to}";\n`, path))).toEqual([
    `${path} line 1: ${from} imports ${to} (@steadyhand/${to})`,
  ]);
});

test.each([
  ["readers", "core"],
  ["history", "core"],
  ["readers", "history"],
  ["history", "readers"],
  ["shell", "readers"],
  ["shell", "history"],
  ["shell", "core"],
  ["core", "core"],
])("%s importing %s is allowed", (from, to) => {
  const path = `packages/${from}/src/sample.ts`;
  expect(upstreamImports(path, parse(`import "@steadyhand/${to}";\n`, path))).toEqual([]);
});

test("a module from outside the workspace is external, never a layer", () => {
  expect(targetOf("packages/core/src/a.ts", "decimal.js")).toBe("external");
});

test("an import whose module is not a written string is refused by name", () => {
  const path = "packages/core/src/sample.ts";
  expect(() => importsOf(parse("const name = 'x';\nawait import(name);\n", path))).toThrow(
    new UnreadableSourceError(
      "packages/core/src/sample.ts line 2: the module this import names is not written as a " +
        "string, so its direction cannot be judged",
    ),
  );
});

test("a workspace name that is no package is refused by name", () => {
  expect(() => targetOf("packages/core/src/a.ts", "@steadyhand/ledger")).toThrow(
    new UnreadableSourceError(
      "packages/core/src/a.ts: @steadyhand/ledger names no package of the workspace",
    ),
  );
});

test("a relative path leaving the packages is refused by name", () => {
  expect(() => targetOf("packages/core/src/a.ts", "../../../build.ts")).toThrow(
    new UnreadableSourceError(
      "packages/core/src/a.ts: ../../../build.ts reaches outside the packages",
    ),
  );
});

test("a file outside the packages has no layer to judge, and is refused by name", () => {
  expect(layerOf("tests/a.ts")).toBeUndefined();
  expect(() => upstreamImports("tests/a.ts", parse("export {};\n", "tests/a.ts"))).toThrow(
    new UnreadableSourceError("tests/a.ts: not in a package, so it has no layer to judge"),
  );
});

test("the package files read are the ones git lists, and as many as recorded", () => {
  expect(PACKAGE_FILES).toEqual(gitListed("packages", SUFFIXES));
  expect(floorBreach("import-direction.files", PACKAGE_FILES.length)).toBeUndefined();
});

test.each(WORKSPACE_FILES)(
  "%s: the tree reader finds the imports the pre-scanner finds",
  (path) => {
    const text = readFileSync(join(EXTENSION, path), "utf8");
    expect(importsOf(parse(text, path)).map(({ specifier }) => specifier)).toEqual(
      preScannedImports(text),
    );
  },
);

test("no package imports a package above it", () => {
  const imports = PACKAGE_FILES.flatMap((path) => importsOf(readSource(path)));
  const found = PACKAGE_FILES.flatMap((path) => upstreamImports(path, readSource(path)));
  expect(searched(found, { of: imports.length, what: "imports in the packages" })).toEqual([]);
  expect(floorBreach("import-direction.imports", imports.length)).toBeUndefined();
});

test("only tests/lib/source.ts imports the TypeScript compiler", () => {
  const imports = WORKSPACE_FILES.flatMap((path) =>
    importsOf(readSource(path)).map(({ specifier, line }) => ({ path, specifier, line })),
  );
  const compiler = imports.filter(({ specifier }) => specifier === "typescript");
  expect(compiler.map(({ path }) => path)).toContain("tests/lib/source.ts");
  const found = compiler
    .filter(({ path }) => path !== "tests/lib/source.ts")
    .map(({ path, line }) => `${path} line ${String(line)}: imports typescript`);
  expect(searched(found, { of: imports.length, what: "imports in the workspace" })).toEqual([]);
  expect(floorBreach("compiler-home.imports", imports.length)).toBeUndefined();
});
