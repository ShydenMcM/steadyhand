import { expect, test } from "vitest";
import {
  LOAD_BURN_DOWN,
  LOAD_CPU_LIMIT_MICROSECONDS,
  loadOf,
  loadRefusal,
  report,
} from "./lib/load-clock.ts";

const load = (path: string, cpu: number, wall = cpu + 5) => ({
  path,
  cpuMicroseconds: cpu,
  wallMicroseconds: wall,
});

test("the limit is a tenth of a second of CPU", () => {
  expect(LOAD_CPU_LIMIT_MICROSECONDS).toBe(100_000);
});

test.each([0, 100_000])("a load of %i us of CPU is within the limit", (cpu) => {
  expect(loadRefusal(load("tests/a.test.ts", cpu))).toBeUndefined();
});

test("a load over the limit is refused, naming the file and its CPU", () => {
  expect(loadRefusal(load("tests/heavy.test.ts", 100_001))).toBe(
    "LOAD LIMIT: tests/heavy.test.ts took 100001 us of CPU to load, over 100000: " +
      "cut its import-time work or move it out of unit",
  );
});

const LISTED = "tests/tool-configs.test.ts";

test("the burn-down list holds only the tool configuration checks, and why", () => {
  // Shyden, 2026-10-12 (#285), "Burn-down until #286": it only shrinks; nothing is ever added.
  expect(Object.keys(LOAD_BURN_DOWN)).toEqual([LISTED]);
  expect(LOAD_BURN_DOWN[LISTED]).toContain("#286");
});

test("a listed file over the limit is reported, not refused", () => {
  expect(loadRefusal(load(LISTED, 700_000))).toBeUndefined();
});

test.each([0, 100_000])("a listed file loading in %i us must come off the list", (cpu) => {
  expect(loadRefusal(load(LISTED, cpu))).toBe(
    `LOAD BURN-DOWN: ${LISTED} now loads within the limit (${String(cpu)} us of CPU): ` +
      "take it off LOAD_BURN_DOWN in tests/lib/load-clock.ts",
  );
});

test("the report lists every file, heaviest first", () => {
  expect(
    report([load("tests/a.test.ts", 2_000, 9_000), load("tests/b.test.ts", 75_000, 80_000)]),
  ).toEqual([
    "load CPU and wall per test file (limit 100000 us of CPU), 2 files:",
    "     75000 us CPU      80000 us wall  tests/b.test.ts",
    "      2000 us CPU       9000 us wall  tests/a.test.ts",
  ]);
});

test("files that load alike are listed by name", () => {
  expect(report([load("tests/b.test.ts", 7), load("tests/a.test.ts", 7)]).slice(1)).toEqual([
    "         7 us CPU         12 us wall  tests/a.test.ts",
    "         7 us CPU         12 us wall  tests/b.test.ts",
  ]);
});

test("this file's own load was recorded on its meta", ({ task }) => {
  const recorded = loadOf(task.file.meta);
  expect(recorded?.path).toBe("tests/load-clock.test.ts");
  expect(recorded?.cpuMicroseconds).toBeGreaterThan(0);
  expect(recorded?.wallMicroseconds).toBeGreaterThan(0);
});
