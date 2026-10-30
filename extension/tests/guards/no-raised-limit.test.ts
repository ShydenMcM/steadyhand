import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "vitest";
import { GUARDS, INTEGRATION } from "../../vitest.config.ts";
import { foundIn } from "../lib/found.ts";
import {
  clockReads,
  declaringCalls,
  declaringCallsByText,
  LIMITS_HOME,
  limitFlags,
  raisedLimits,
} from "../lib/raised-limits.ts";
import { EXTENSION, parse, readSource } from "../lib/source.ts";
import { filesUnder, gitListed } from "../lib/walk.ts";

const SUFFIXES = [".ts", ".js", ".mjs"] as const;
/** The product's own source is no test and no config; everything else in the workspace is. */
const isProduct = (path: string): boolean => /^packages\/[^/]+\/src\//u.test(path);
const FILES = filesUnder(".", SUFFIXES).filter((path) => !isProduct(path));
const prefix = (glob: string): string => glob.slice(0, glob.indexOf("**"));
/** The files a unit run loads: every test and helper outside the guards and integration suites. */
const UNIT_FILES = FILES.filter(
  (path) => !path.startsWith(prefix(GUARDS)) && !path.startsWith(prefix(INTEGRATION)),
);

const sample = (code: string): ReturnType<typeof parse> => parse(code, "tests/sample.test.ts");

/** Each way a test or config can raise or set a limit, or hide a runner from this guard (AC 3). */
const FORMS: readonly (readonly [string, string, string | readonly string[]])[] = [
  ["a third-argument limit", 'test("a", () => {}, 5000);', "test is given a limit or options"],
  ["a limit held in a const", 'test("a", () => {}, LIMIT);', "test is given a limit or options"],
  ["a limit by arithmetic", 'it("a", () => {}, 400 + 20);', "it is given a limit or options"],
  ["a limit on test.only", 'test.only("a", () => {}, 5000);', "test is given a limit or options"],
  [
    "an options object first",
    'test("a", { timeout: 5000 }, () => {});',
    ["test is given a limit or options", "a limit key timeout: 5000"],
  ],
  [
    "an options object last",
    'test("a", () => {}, { timeout: 5000 });',
    ["test is given a limit or options", "a limit key timeout: 5000"],
  ],
  [
    "options spread from a name",
    'test("a", { ...options }, () => {});',
    "test is given a limit or options",
  ],
  ["options held in a name", 'test("a", options, () => {});', "test is given a limit or options"],
  [
    "a limit on test.each",
    'test.each([1])("a %i", () => {}, 5000);',
    "test is given a limit or options",
  ],
  ["a limit on describe", 'describe("a", () => {}, 5000);', "describe is given a limit or options"],
  ["a limit on suite", 'suite("a", () => {}, 5000);', "suite is given a limit or options"],
  [
    "a limit on bench",
    'bench("a", () => {}, { time: 5000 });',
    "bench is given a limit or options",
  ],
  [
    "a limit on describe.skipIf",
    'describe.skipIf(x)("a", () => {}, 5000);',
    "describe is given a limit or options",
  ],
  ["a limit on beforeAll", "beforeAll(() => {}, 5000);", "beforeAll is given a limit or options"],
  [
    "a limit on beforeEach",
    "beforeEach(() => {}, 5000);",
    "beforeEach is given a limit or options",
  ],
  ["a limit on afterAll", "afterAll(() => {}, 5000);", "afterAll is given a limit or options"],
  ["a limit on afterEach", "afterEach(() => {}, 5000);", "afterEach is given a limit or options"],
  [
    "a limit on onTestFinished",
    "onTestFinished(() => {}, 5000);",
    "onTestFinished is given a limit or options",
  ],
  [
    "a limit on a test by element access",
    'test["only"]("a", () => {}, 5000);',
    "test is given a limit or options",
  ],
  [
    "a member not written as a name",
    'test[mode]("a", () => {});',
    "a member of test not written as a name",
  ],
  ["vi.setConfig", "vi.setConfig(config);", ".setConfig, which sets a limit or names a runner"],
  [
    "setConfig by element access",
    'vi["setConfig"]({});',
    ".setConfig, which sets a limit or names a runner",
  ],
  [
    "a test's own setTimeout",
    "test.setTimeout(5000);",
    ".setTimeout, which sets a limit or names a runner",
  ],
  ["a slow test", "test.slow();", ".slow, which sets a limit or names a runner"],
  ["test.extend", "const mine = test.extend({});", ".extend, which sets a limit or names a runner"],
  ["test.scoped", "test.scoped({});", ".scoped, which sets a limit or names a runner"],
  [
    "a testTimeout key",
    "export default { test: { testTimeout: 5_000 } };",
    "a limit key testTimeout: 5_000",
  ],
  ["a hookTimeout key", "const config = { hookTimeout: 5000 };", "a limit key hookTimeout: 5000"],
  [
    "a teardownTimeout key",
    "const config = { teardownTimeout: 5000 };",
    "a limit key teardownTimeout: 5000",
  ],
  ["a timeout key in a name", "const options = { timeout: 5000 };", "a limit key timeout: 5000"],
  [
    "a quoted limit key",
    'const config = { "testTimeout": 5000 };',
    'a limit key "testTimeout": 5000',
  ],
  [
    "a computed limit key",
    'const config = { ["testTimeout"]: 5000 };',
    'a limit key ["testTimeout"]: 5000',
  ],
  [
    "a shorthand limit key",
    "const config = { testTimeout };",
    "a limit key testTimeout: testTimeout",
  ],
  ["a renamed import", 'import { test as check } from "vitest";', "test renamed on import"],
  [
    "an import renamed to a runner",
    'import { check as test } from "./helpers.ts";',
    "test renamed on import",
  ],
  ["a renamed export", "export { test as check };", "test renamed on export"],
  ["a renamed binding", "const { test: check } = runner;", "test renamed in a binding"],
  ["a namespace import", 'import * as runner from "vitest";', "vitest imported whole"],
  ["a default import", 'import runner from "vitest";', "vitest imported whole"],
  [
    "a namespace import of node:test",
    'import * as runner from "node:test";',
    "node:test imported whole",
  ],
  ["a dynamic import", 'const runner = await import("vitest");', "vitest imported by a call"],
  [
    "a require",
    'const runner = require("@playwright/test");',
    "@playwright/test imported by a call",
  ],
  [
    "an import not written",
    "const runner = await import(name);",
    "an import whose module is not written",
  ],
  ["a runner held in a name", "const check = test;", "test held or passed, not called"],
  ["a runner passed", "[1].forEach(it);", "it held or passed, not called"],
  ["a modifier's result held", "const each = test.each([1]);", "test held or passed, not called"],
  ["a member held", "const only = test.only;", "test held or passed, not called"],
  ["a local test", "const test = (a, b, c) => a;", "test declared here, hiding the runner's"],
  [
    "a parameter named suite",
    "const f = (suite) => 1;",
    "suite declared here, hiding the runner's",
  ],
  ["a function named it", "function it() {}", "it declared here, hiding the runner's"],
  ["a binding named vi", "const { vi } = helpers;", "vi declared here, hiding the runner's"],
  [
    "a destructured member not written",
    "const { [name]: read } = vi;",
    "a destructured member not written as a name",
  ],
  [
    "a runner destructured into a pattern",
    "const { test: { only } } = runner;",
    "test renamed in a binding",
  ],
];

test.each(FORMS)("%s is refused by line", (_, code, what) => {
  expect(raisedLimits(sample(`\n${code}\n`))).toEqual([what].flat().map((w) => `line 2: ${w}`));
});

/** What the workspace writes today, which sets no limit. */
const ALLOWED: readonly (readonly [string, string])[] = [
  ["a test", 'test("a", () => {});'],
  ["a test by a function name", 'test("a", body);'],
  ["a todo", 'test.todo("a");'],
  ["test.each", 'test.each([1, 2])("a %i", (n) => {});'],
  ["test.for", 'test.for([1])("a %i", ([n]) => {});'],
  ["a skip with its reason", 'test.skipIf(process.env.CI)("a", () => {});'],
  ["a hook reading the suite", "beforeAll(({}, running) => {});"],
  [
    "an import of the runner",
    'import { afterEach, beforeAll, describe, expect, test, vi } from "vitest";',
  ],
  ["vi's own calls", 'vi.fn(); vi.mock("node:fs");'],
  ["a re-export", 'export { test } from "./runner.ts";'],
  ["a runner name as a key", "const config = { test: { include: [] } };"],
  ["a runner name as a member", "config.test.include;"],
  ["a namespace import of another module", 'import * as esbuild from "esbuild";'],
  ["a renamed import of another name", 'import { PACKAGE as CORE } from "@steadyhand/core";'],
  ["a key that is no limit", "const a = { timeoutMessage: 'x', mode: 'limits' };"],
  ["a wait", "await new Promise((resolve) => setTimeout(resolve, 5));"],
];

test.each(ALLOWED)("%s sets no limit", (_, code) => {
  expect(raisedLimits(sample(code))).toEqual([]);
});

/** Each way a unit test can read a clock, and so hold a time budget of its own (AC 3). */
const CLOCKS: readonly (readonly [string, string, string])[] = [
  ["performance.now", "const t = performance.now();", ".now reads a clock"],
  ["Date.now", "const t = Date.now();", ".now reads a clock"],
  ["globalThis.performance.now", "globalThis.performance.now();", ".now reads a clock"],
  ["now by element access", 'performance["now"]();', ".now reads a clock"],
  ["now destructured", "const { now } = performance;", ".now reads a clock"],
  ["process.hrtime", "process.hrtime();", ".hrtime reads a clock"],
  ["process.hrtime.bigint", "process.hrtime.bigint();", ".hrtime reads a clock"],
  ["process.cpuUsage", "process.cpuUsage();", ".cpuUsage reads a clock"],
  ["process.threadCpuUsage", "process.threadCpuUsage();", ".threadCpuUsage reads a clock"],
  ["process.uptime", "process.uptime();", ".uptime reads a clock"],
  ["performance.timeOrigin", "performance.timeOrigin;", ".timeOrigin reads a clock"],
  ["now by a quoted key", 'const { "now": read } = performance;', ".now reads a clock"],
  ["new Date()", "const d = new Date();", "new Date() reads a clock"],
  ["new Date without parentheses", "const d = new Date;", "new Date() reads a clock"],
  ["Date()", "const d = Date();", "Date() reads a clock"],
  ["perf_hooks", 'import { performance } from "node:perf_hooks";', "node:perf_hooks imported"],
  ["perf_hooks bare", 'import { performance } from "perf_hooks";', "perf_hooks imported"],
];

test.each(CLOCKS)("%s is refused in a unit file", (_, code, what) => {
  expect(clockReads(sample(`\n${code}\n`))).toEqual([`line 2: ${what}`]);
});

test.each([
  ["a fixed date", 'new Date("2026-10-15T09:00:00Z");'],
  ["a date from a number", "new Date(0);"],
  ["Date.UTC", "Date.UTC(2026, 9, 15);"],
])("%s reads no clock", (_, code) => {
  expect(clockReads(sample(code))).toEqual([]);
});

test.each([
  ["--testTimeout=5000", "vitest run --testTimeout=5000"],
  ["--testTimeout 5000", "vitest run --testTimeout 5000"],
  ["--test-timeout", "vitest run --test-timeout=5000"],
  ["--hookTimeout", "vitest run --hookTimeout=5000"],
  ["--hook-timeout", "vitest run --hook-timeout 5000"],
  ["--teardownTimeout", "vitest run --teardownTimeout=5000"],
  ["--teardown-timeout", "vitest run --teardown-timeout=5000"],
])("the flag %s is refused in a script", (flag, script) => {
  expect(limitFlags(script)).toEqual([flag.split(/[= ]/u)[0]]);
});

test("a script that sets no limit is allowed", () => {
  expect(limitFlags("vitest run --project unit --mode limits")).toEqual([]);
});

// The one named place (AC 2): its keys and their values, pinned here by literal.
test("vitest.config.ts is the one place a limit is set: 1 s per unit test and hook", () => {
  const found = raisedLimits(readSource(LIMITS_HOME)).map((f) => f.replace(/^line \d+: /u, ""));
  expect(found).toEqual(["a limit key testTimeout: 1_000", "a limit key hookTimeout: 1_000"]);
});

test("the files judged are the ones git lists", () => {
  expect(FILES).toEqual(gitListed(".", SUFFIXES).filter((path) => !isProduct(path)));
  expect(FILES).toContain("vitest.config.ts");
});

test("no test, helper or config raises, sets or hides a limit, outside the one place", () => {
  const judged = FILES.filter((path) => path !== LIMITS_HOME);
  const found = foundIn(
    judged,
    (path) => path,
    (path) => raisedLimits(readSource(path)),
  );
  expect(found).toEqual([]);
});

test("no unit file reads a clock, outside the two clocks", () => {
  const judged = UNIT_FILES;
  const found = foundIn(
    judged,
    (path) => path,
    (path) => clockReads(readSource(path)),
  );
  expect(found).toEqual([]);
});

test("no npm script sets a limit", () => {
  const manifests = filesUnder(".", ["package.json"]);
  const scripts = manifests.flatMap((path) =>
    Object.values(
      (
        JSON.parse(readFileSync(join(EXTENSION, path), "utf8")) as {
          scripts?: Record<string, string>;
        }
      ).scripts ?? {},
    ),
  );
  const found = foundIn(
    scripts,
    (script) => script,
    (script) => limitFlags(script),
  );
  expect(found).toEqual([]);
});

// Independent of the reader's walk: each test and hook call the code text opens is judged.
test.each(FILES)("%s: every test and hook declaration in the text is judged", (path) => {
  const file = readSource(path);
  expect(declaringCalls(file)).toHaveLength(declaringCallsByText(file));
});
