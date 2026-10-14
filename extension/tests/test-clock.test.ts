import { expect, test } from "vitest";
import {
  CPU_LIMIT_MICROSECONDS,
  WALL_LIMIT_MILLISECONDS,
  limitsFor,
  spentOf,
  testRefusal,
  testReport,
} from "./lib/test-clock.ts";

const spent = (name: string, cpu: number, wall = cpu * 2) => ({
  name,
  cpuMicroseconds: cpu,
  wallMicroseconds: wall,
});

test("the limits are a second of wall and a tenth of a second of CPU", () => {
  expect([WALL_LIMIT_MILLISECONDS, CPU_LIMIT_MICROSECONDS]).toEqual([1_000, 100_000]);
});

test("a limits run holds each test and hook to a second; any other run holds none", () => {
  expect(limitsFor("limits")).toEqual({ testTimeout: 1_000, hookTimeout: 1_000 });
  expect(limitsFor("test")).toEqual({ testTimeout: 0, hookTimeout: 0 });
  expect(limitsFor("guards")).toEqual({ testTimeout: 0, hookTimeout: 0 });
});

test.each([0, 100_000])("a test of %i us of CPU is within the limit", (cpu) => {
  expect(testRefusal(spent("tests/a.test.ts > adds", cpu))).toBeUndefined();
});

test("a test over the limit is refused, naming it and its CPU", () => {
  expect(testRefusal(spent("tests/heavy.test.ts > loops", 100_001))).toBe(
    "CPU LIMIT: tests/heavy.test.ts > loops took 100001 us of its own CPU, over 100000: " +
      "cut its work or move its real case out of unit",
  );
});

test("the report lists the heaviest ten first, under a heading naming both limits", () => {
  const all = Array.from({ length: 12 }, (_, n) =>
    spent(`tests/x.test.ts > t${String(n).padStart(2, "0")}`, n * 1_000),
  );
  const lines = testReport(all);
  expect(lines[0]).toBe(
    "own CPU and wall per unit test (limits 100000 us of CPU, 1000 ms of wall), " +
      "12 tests, the heaviest 10:",
  );
  expect(lines.slice(1).map((line) => line.split("  ").at(-1))).toEqual(
    Array.from({ length: 10 }, (_, n) => `tests/x.test.ts > t${String(11 - n).padStart(2, "0")}`),
  );
  expect(lines[1]).toBe("     11000 us CPU      22000 us wall  tests/x.test.ts > t11");
});

test("tests of equal CPU are listed by name", () => {
  const lines = testReport([spent("tests/x.test.ts > b", 7), spent("tests/x.test.ts > a", 7)]);
  expect(lines.slice(1).map((line) => line.split("  ").at(-1))).toEqual([
    "tests/x.test.ts > a",
    "tests/x.test.ts > b",
  ]);
});

test("a test's time is read back from its meta, and a test with none has none", () => {
  const meta = { spent: spent("tests/a.test.ts > adds", 5) };
  expect(spentOf(meta)).toEqual(meta.spent);
  expect(spentOf({})).toBeUndefined();
});
