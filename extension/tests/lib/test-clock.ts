/**
 * Each unit test is held to 1 s of wall and 0.1 s of its own thread CPU (#323). The global rule
 * (Shyden, 2026-10-07 to 2026-10-12, every project): a unit test runs in under 1 s and at or under
 * 0.1 s of its own thread CPU, and no limit is ever raised. Both apply to a limits run only
 * (`npm run test:limits`, no coverage): under coverage the tracer is timed with the code. The
 * wall limit is vitest's `testTimeout` and `hookTimeout`, set from `limitsFor` in
 * `vitest.config.ts`; the setup file `tests/test-clock.ts` times each test's own CPU and refuses
 * one over the limit; the reporter `tests/load-report.ts` prints the heaviest. This module is the
 * logic they share, as `tests/lib/load-clock.ts` is for each file's load (#285).
 */

/** The most own CPU one unit test may take, in microseconds of its thread. An integer, so the
 * edit hook refusing a raised limit (`~/.claude/hooks/unit-limit-never-raised.py`, CPU_LIMITS)
 * reads it; the same name and value as the Python suite's `tests/plugins/unit_limits.py`. */
export const CPU_LIMIT_MICROSECONDS = 100_000;

/** The most wall-clock time one unit test or hook may take, in milliseconds. */
export const WALL_LIMIT_MILLISECONDS = 1_000;

const HEAVIEST_SHOWN = 10;

/** One test's own CPU and wall, from its first `beforeEach` to its last `afterEach`. */
export interface Spent {
  name: string;
  cpuMicroseconds: number;
  wallMicroseconds: number;
}

/** vitest's per-test and per-hook limits for a run in `mode`: a limits run holds each to a
 * second; any other run holds none (0 is none to vitest), its CI step bounding it. */
export const limitsFor = (mode: string): { testTimeout: number; hookTimeout: number } =>
  mode === "limits"
    ? { testTimeout: WALL_LIMIT_MILLISECONDS, hookTimeout: WALL_LIMIT_MILLISECONDS }
    : { testTimeout: 0, hookTimeout: 0 };

/** The time recorded on a test's meta by `tests/test-clock.ts`, if any. */
export const spentOf = (meta: object): Spent | undefined => (meta as { spent?: Spent }).spent;

/** Why a test is refused, or undefined when it is not: a test over the CPU limit. */
export const testRefusal = (spent: Spent): string | undefined =>
  spent.cpuMicroseconds > CPU_LIMIT_MICROSECONDS
    ? `CPU LIMIT: ${spent.name} took ${String(spent.cpuMicroseconds)} us of its own CPU, over ` +
      `${String(CPU_LIMIT_MICROSECONDS)}: cut its work or move its real case out of unit`
    : undefined;

const column = (value: number): string => String(value).padStart(10);

/** The heaviest tests first, under a heading naming both limits. */
export const testReport = (spent: readonly Spent[]): string[] => [
  `own CPU and wall per unit test (limits ${String(CPU_LIMIT_MICROSECONDS)} us of CPU, ` +
    `${String(WALL_LIMIT_MILLISECONDS)} ms of wall), ${String(spent.length)} tests, ` +
    `the heaviest ${String(HEAVIEST_SHOWN)}:`,
  ...[...spent]
    .sort((a, b) => b.cpuMicroseconds - a.cpuMicroseconds || a.name.localeCompare(b.name))
    .slice(0, HEAVIEST_SHOWN)
    .map(
      (one) =>
        `${column(one.cpuMicroseconds)} us CPU ${column(one.wallMicroseconds)} us wall  ${one.name}`,
    ),
];
