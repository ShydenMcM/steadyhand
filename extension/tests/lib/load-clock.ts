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

/** The load recorded on a test file's meta by `tests/load-clock.ts`, if any. */
export const loadOf = (meta: object): Load | undefined => (meta as { load?: Load }).load;

/** Record `load` on a test file's meta, for the reporter. */
export const recordLoad = (meta: object, load: Load): void => {
  (meta as { load?: Load }).load = load;
};

/** The environment variable a limits run sets (`npm run test:limits`): only then are loads
 * judged, since under coverage the tracer is timed with the file. */
export const JUDGE_ENV = "STEADYHAND_JUDGE_LOADS";

/** Why a load is refused, or undefined when it is not: a file over the limit. The list of files
 * allowed over it until their ticket moved the cost out emptied when #286 moved the tool
 * configuration checks to the integration suite; it only ever shrank (Shyden, 2026-10-12, #285),
 * so it is gone. */
export const loadRefusal = (load: Load): string | undefined =>
  load.cpuMicroseconds > LOAD_CPU_LIMIT_MICROSECONDS
    ? `LOAD LIMIT: ${load.path} took ${String(load.cpuMicroseconds)} us of CPU to load, over ` +
      `${String(LOAD_CPU_LIMIT_MICROSECONDS)}: cut its import-time work or move it out of unit`
    : undefined;

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
