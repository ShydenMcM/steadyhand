/**
 * The tools' own configuration, judged by loading each tool (#285). Loading them costs more CPU
 * than a unit file may spend (measured 2026-10-12: typescript-eslint 0.34 s, Playwright 0.21 s,
 * Vitest's config 0.10 s), so #286 moved this file to the integration suite (Shyden, 2026-10-12,
 * "Burn-down until #286").
 */
import tseslint from "typescript-eslint";
import { readdirSync } from "node:fs";
import { expect, test } from "vitest";
import eslint from "../../eslint.config.js";
import playwright from "../../playwright.config.ts";
import vitestConfig, {
  GUARDS,
  GUARDS_COVERED,
  INTEGRATION,
  UNIT_COVERED,
} from "../../vitest.config.ts";

test("ESLint applies every rule set of typescript-eslint's strict, type-checked config", () => {
  const strict = tseslint.configs.strictTypeChecked;
  expect(strict.length).toBeGreaterThan(0);
  expect(strict.filter((config) => !eslint.includes(config))).toEqual([]);
});

const unit = vitestConfig({ command: "serve", mode: "test" });
const guards = vitestConfig({ command: "serve", mode: "guards" });

test.each([
  ["unit", unit],
  ["guards", guards],
])("Vitest fails a %s run below 100% coverage on every measure", (_suite, config) => {
  expect(config.test?.coverage).toMatchObject({
    provider: "v8",
    thresholds: { branches: 100, functions: 100, lines: 100, statements: 100 },
  });
});

test("Playwright never retries a failed test", () => {
  expect(playwright.retries).toBe(0);
});

test("each suite's run covers its own list", () => {
  expect(unit.test?.coverage?.include).toEqual(UNIT_COVERED);
  expect(guards.test?.coverage?.include).toEqual(GUARDS_COVERED);
});

test("every helper in tests/lib is held to coverage by exactly one suite", () => {
  const helpers = readdirSync(new URL("../lib", import.meta.url)).map(
    (name) => `tests/lib/${name}`,
  );
  expect(helpers).toContain("tests/lib/found.ts");
  const listed = [...UNIT_COVERED, ...GUARDS_COVERED];
  expect(helpers.filter((path) => listed.filter((entry) => entry === path).length !== 1)).toEqual(
    [],
  );
  expect(listed.filter((entry) => entry.startsWith("tests/lib/")).sort()).toEqual(helpers.sort());
});

interface Project {
  test?: { name?: string; include?: string[]; exclude?: string[]; setupFiles?: string[] };
}
const projects = unit.test?.projects as Project[];
const project = (name: string): Project["test"] =>
  projects.find((candidate) => candidate.test?.name === name)?.test;

test("the three projects are unit, guards and integration, in that order", () => {
  expect(projects.map((candidate) => candidate.test?.name)).toEqual([
    "unit",
    "guards",
    "integration",
  ]);
});

test.each([
  ["guards", GUARDS],
  ["integration", INTEGRATION],
])("the %s project holds its own folder, which unit leaves out", (name, glob) => {
  expect(project(name)?.include).toEqual([glob]);
  expect(project("unit")?.exclude).toContain(glob);
});

test("a unit run refuses processes", () => {
  expect(project("unit")?.setupFiles).toEqual(["tests/no-process.ts"]);
});

test.each(["guards", "integration"])("a %s run has no setup file", (name) => {
  expect(project(name)?.setupFiles).toBeUndefined();
});
