/**
 * Loading a unit test file is limited too (#285). Shyden's rule (2026-10-11, every project): a
 * test's own clocks start once it runs, so what a file does as it is imported counted against no
 * limit (measured 2026-10-12: `workspace.test.ts` took 1.12 s of CPU to load). The setup file
 * `tests/load-clock.ts` times each unit file's load and refuses one over the limit; the reporter
 * `tests/load-report.ts` prints every file. This module is the logic both share.
 */

/** The most CPU one unit file may take to load, in microseconds of its own thread. An integer,
 * so the edit hook refusing a raised limit (`~/.claude/hooks/unit-limit-never-raised.py`) reads
 * it; the same name and value as the Python suite's `tests/plugins/load_clock.py`. */
export const LOAD_CPU_LIMIT_MICROSECONDS = 100_000;

/** One test file's import and collection, named by its path in the workspace. */
export interface Load {
  path: string;
  cpuMicroseconds: number;
  wallMicroseconds: number;
}

declare module "vitest" {
  interface TaskMeta {
    load?: Load;
  }
}

/** Files allowed over the limit until their ticket moves the cost out, each with its measured cost
 * and that ticket. Shyden, 2026-10-12 (#285): "Burn-down until #286". It only shrinks: a listed
 * file that loads within the limit is refused until it is taken off, and nothing is ever added. */
export const LOAD_BURN_DOWN: Readonly<Record<string, string>> = {
  "tests/tool-configs.test.ts":
    "loads typescript-eslint (0.34 s of CPU), Playwright (0.21 s) and Vitest's config (0.10 s), " +
    "measured 2026-10-12; #286 moves it to the integration suite",
};

/** Why a load is refused, or undefined when it is not: a file over the limit, or a listed file
 * now within it. */
export const loadRefusal = (load: Load): string | undefined => {
  const over = load.cpuMicroseconds > LOAD_CPU_LIMIT_MICROSECONDS;
  const listed = Object.hasOwn(LOAD_BURN_DOWN, load.path);
  if (listed && !over) {
    return (
      `LOAD BURN-DOWN: ${load.path} now loads within the limit ` +
      `(${String(load.cpuMicroseconds)} us of CPU): take it off LOAD_BURN_DOWN in tests/lib/load-clock.ts`
    );
  }
  return over && !listed
    ? `LOAD LIMIT: ${load.path} took ${String(load.cpuMicroseconds)} us of CPU to load, over ` +
        `${String(LOAD_CPU_LIMIT_MICROSECONDS)}: cut its import-time work or move it out of unit`
    : undefined;
};

const column = (value: number): string => String(value).padStart(10);

/** One line per file, heaviest CPU first, under a heading naming the limit. */
export const report = (loads: readonly Load[]): string[] => [
  `load CPU and wall per test file (limit ${String(LOAD_CPU_LIMIT_MICROSECONDS)} us of CPU), ` +
    `${String(loads.length)} files:`,
  ...[...loads]
    .sort((a, b) => b.cpuMicroseconds - a.cpuMicroseconds || a.path.localeCompare(b.path))
    .map(
      (load) =>
        `${column(load.cpuMicroseconds)} us CPU ${column(load.wallMicroseconds)} us wall  ${load.path}`,
    ),
];
