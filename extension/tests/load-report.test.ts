/**
 * The reporter that prints every unit file's load and the heaviest tests' time (#285, #323),
 * driven in-process with test modules shaped as vitest hands them over (#374 AC6): a file with no
 * load recorded, or a test that ran with no time recorded, fails the run rather than report less.
 */
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { TestModule } from "vitest/node";
import LoadReport from "./load-report.ts";

interface Case {
  fullName: string;
  state: string;
  meta: object;
}

function moduleOf(project: string, moduleId: string, meta: object, cases: Case[]): TestModule {
  return {
    project: { name: project },
    moduleId,
    meta: () => meta,
    children: {
      *allTests() {
        for (const one of cases) {
          yield {
            fullName: one.fullName,
            result: () => ({ state: one.state }),
            meta: () => one.meta,
          };
        }
      },
    },
  } as unknown as TestModule;
}

const LOAD = { load: { path: "tests/a.test.ts", cpuMicroseconds: 2_000, wallMicroseconds: 3_000 } };
const SPENT = { spent: { name: "a > one", cpuMicroseconds: 400, wallMicroseconds: 500 } };

let printed: string[] = [];
let refused: string[] = [];
let exitCode: typeof process.exitCode;

beforeEach(() => {
  exitCode = process.exitCode;
  process.exitCode = undefined;
  printed = [];
  refused = [];
  vi.spyOn(console, "log").mockImplementation((line: string) => printed.push(line));
  vi.spyOn(console, "error").mockImplementation((line: string) => refused.push(line));
});

afterEach(() => {
  vi.restoreAllMocks();
  process.exitCode = exitCode;
});

function report(modules: TestModule[]): typeof process.exitCode {
  new LoadReport().onTestRunEnd(modules);
  const code = process.exitCode;
  process.exitCode = undefined;
  return code;
}

test("a unit run prints each file's load and each test's time, and fails nothing", () => {
  const code = report([
    moduleOf("unit", "/x/tests/a.test.ts", LOAD, [
      { fullName: "a > one", state: "passed", meta: SPENT },
    ]),
  ]);
  expect(code).toBeUndefined();
  expect(refused).toEqual([]);
  expect(printed).toEqual([
    "load CPU and wall per test file (limit 100000 us of CPU), 1 files:\n" +
      "      2000 us CPU       3000 us wall  tests/a.test.ts",
    "own CPU and wall per unit test (limits 100000 us of CPU, 1000 ms of wall), 1 tests, the " +
      "heaviest 10:\n       400 us CPU        500 us wall  a > one",
  ]);
});

test("a unit file with no load recorded fails the run, naming it", () => {
  const code = report([moduleOf("unit", "/x/tests/a.test.ts", {}, [])]);
  expect(code).toBe(1);
  expect(refused).toEqual(["LOAD CLOCK: no load recorded for /x/tests/a.test.ts"]);
});

test.each(["passed", "failed"])(
  "a %s test with no time recorded fails the run, naming it",
  (state) => {
    const code = report([
      moduleOf("unit", "/x/tests/a.test.ts", LOAD, [{ fullName: "a > one", state, meta: {} }]),
    ]);
    expect(code).toBe(1);
    expect(refused).toEqual(["TEST CLOCK: no time recorded for a > one"]);
  },
);

test("a failed test's time is reported like a passed one's", () => {
  report([
    moduleOf("unit", "/x/tests/a.test.ts", LOAD, [
      { fullName: "a > one", state: "failed", meta: SPENT },
    ]),
  ]);
  expect(printed[1]).toContain(" 1 tests,");
});

test("a test that did not run needs no time", () => {
  const code = report([
    moduleOf("unit", "/x/tests/a.test.ts", LOAD, [
      { fullName: "a > one", state: "skipped", meta: {} },
    ]),
  ]);
  expect(code).toBeUndefined();
  expect(refused).toEqual([]);
  expect(printed[1]).toContain(" 0 tests,");
});

test("another project's files are not the unit run's, and with none no test report is printed", () => {
  const code = report([
    moduleOf("guards", "/x/tests/guards/g.test.ts", {}, [
      { fullName: "g", state: "passed", meta: {} },
    ]),
  ]);
  expect(code).toBeUndefined();
  expect(refused).toEqual([]);
  expect(printed).toEqual(["load CPU and wall per test file (limit 100000 us of CPU), 0 files:"]);
});
