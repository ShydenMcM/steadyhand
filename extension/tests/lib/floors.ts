/**
 * The recorded floors: one measured figure per population a guard judges (spec §14.2).
 *
 * Shyden's rule (2026-10-02): a floor is the measured figure, checked for EQUALITY, so a guard
 * that goes blind to part of its population fails, and so does growth until it is recorded. A
 * floor typed into a test drifts the day after it is measured, so every figure lives in
 * `tests/floors.json`, written only by `npm run floors:record`, which raises a figure and never
 * lowers one, and never runs in CI.
 */
import { appendFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { type RunnerTestCase, TestRunner } from "vitest";

export const FLOORS_PATH = join(import.meta.dirname, "..", "floors.json");

/** Set by the recorder only: each floor then appends its measurement here instead of judging. */
export const RECORD_ENV = "STEADYHAND_FLOORS_RECORD";

export type Floors = Readonly<Record<string, number>>;

/** One floor measured while recording, with the test that asserted it. */
export interface Measurement {
  id: string;
  measured: number;
  test: string;
}

/** The floors in `text`; anything but whole numbers of zero or more is refused by id. */
export const parseFloors = (text: string): Floors => {
  const parsed: unknown = JSON.parse(text);
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("the floors file is not an object of floor ids");
  }
  for (const [id, figure] of Object.entries(parsed)) {
    if (!Number.isSafeInteger(figure) || (figure as number) < 0) {
      throw new Error(
        `floor ${id}: ${JSON.stringify(figure)} is not a whole number of zero or more`,
      );
    }
  }
  return parsed as Floors;
};

export const readFloors = (path: string = FLOORS_PATH): Floors =>
  parseFloors(readFileSync(path, "utf8"));

/**
 * The test asserting a floor right now, by its full name; a floor asserted outside a test is
 * refused. Measured on 2026-10-06: inside a hook, `expect.getState()` still names the test that
 * ran last, so the runner's own current test is asked instead, which is `undefined` in a hook.
 */
const currentTest = (): string => {
  const running = TestRunner.getCurrentTest<RunnerTestCase | undefined>();
  if (running === undefined) {
    throw new Error("a floor is asserted inside a test, so the recorder can tell who owns it");
  }
  return running.fullName;
};

/**
 * Why `measured` breaks floor `id`, or `undefined` when it equals the recorded figure. Use it as
 * `expect(floorBreach(id, population.length)).toBeUndefined()`, in the test whose search judged
 * that population.
 */
export const floorBreach = (
  id: string,
  measured: number,
  env: Readonly<Record<string, string | undefined>> = process.env,
  floorsPath: string = FLOORS_PATH,
): string | undefined => {
  const recording = env[RECORD_ENV];
  if (recording !== undefined) {
    if (env.CI !== undefined) {
      throw new Error("floors are recorded on a developer's machine, never in CI");
    }
    const line: Measurement = { id, measured, test: currentTest() };
    appendFileSync(recording, `${JSON.stringify(line)}\n`);
    return undefined;
  }
  const recorded = readFloors(floorsPath)[id];
  if (recorded === undefined) {
    return `floor ${id}: none recorded, measured ${String(measured)}; run npm run floors:record`;
  }
  if (measured > recorded) {
    return (
      `floor ${id}: measured ${String(measured)}, recorded ${String(recorded)} (+${String(measured - recorded)}); ` +
      "read the growth against the diff, then run npm run floors:record"
    );
  }
  if (measured < recorded) {
    return (
      `floor ${id}: measured ${String(measured)}, recorded ${String(recorded)} (${String(measured - recorded)}); ` +
      "a reader may have gone blind to part of its population. If it really shrank, lower " +
      "the figure in tests/floors.json by a deliberate edit"
    );
  }
  return undefined;
};

/** What the recorder would write, every floor that moved, and every reason to write nothing. */
export interface Merged {
  floors: Record<string, number>;
  moved: string[];
  refused: string[];
}

/**
 * The floors after `measurements`: a figure rises to its measurement and never falls. An id
 * asserted by two tests, a figure measured below its record, and a recorded id no test asserted
 * any more are refused, because each is a decision for a person, not the recorder.
 */
export const mergeFloors = (recorded: Floors, measurements: readonly Measurement[]): Merged => {
  const byId = new Map<string, Measurement[]>();
  for (const measurement of measurements) {
    byId.set(measurement.id, [...(byId.get(measurement.id) ?? []), measurement]);
  }
  const floors: Record<string, number> = { ...recorded };
  const moved: string[] = [];
  const refused: string[] = [];
  for (const [id, found] of [...byId].sort(([a], [b]) => a.localeCompare(b))) {
    const tests = [...new Set(found.map((m) => m.test))];
    const figures = [...new Set(found.map((m) => m.measured))];
    const figure = Math.max(...figures);
    const before = recorded[id];
    if (tests.length > 1) {
      refused.push(
        `floor ${id} is asserted from ${String(tests.length)} places: ${tests.join("; ")}`,
      );
    } else if (figures.length > 1) {
      refused.push(`floor ${id} measured ${figures.join(" and ")} in one run`);
    } else if (before === undefined) {
      moved.push(`${id}: new, ${String(figure)}`);
      floors[id] = figure;
    } else if (figure > before) {
      moved.push(`${id}: ${String(before)} → ${String(figure)} (+${String(figure - before)})`);
      floors[id] = figure;
    } else if (figure < before) {
      refused.push(
        `floor ${id}: measured ${String(figure)}, below its record of ${String(before)}; the recorder never ` +
          "lowers a floor. Lower it by a deliberate edit if the population really shrank",
      );
    }
  }
  for (const id of Object.keys(recorded).filter((known) => !byId.has(known))) {
    refused.push(
      `floor ${id} is recorded, but no test asserted it; remove it by a deliberate edit`,
    );
  }
  const sorted = Object.fromEntries(Object.entries(floors).sort(([a], [b]) => a.localeCompare(b)));
  return { floors: sorted, moved, refused };
};

/** The measurements one recording run wrote, one JSON object a line; a malformed line is refused. */
export const parseMeasurements = (text: string): Measurement[] =>
  text
    .split("\n")
    .filter((line) => line !== "")
    .map((line, index) => {
      const parsed = JSON.parse(line) as Partial<Measurement>;
      if (
        typeof parsed.id !== "string" ||
        !Number.isSafeInteger(parsed.measured) ||
        typeof parsed.test !== "string"
      ) {
        throw new Error(`measurement ${String(index + 1)} is not {id, measured, test}: ${line}`);
      }
      return parsed as Measurement;
    });

/**
 * One recording: run the suite with `RECORD_ENV` set, then write the raised floors, or nothing.
 * `run` takes the measurements path and returns the suite's exit status. The recorder never
 * runs in CI, so its own test passes a run that writes measurements instead of the real suite.
 * Returns the recorder's exit status.
 */
export const recordFloors = (
  floorsPath: string,
  run: (measurementsPath: string) => number,
  log: (line: string) => void,
): number => {
  const scratch = mkdtempSync(join(tmpdir(), "steadyhand-floors-"));
  try {
    const measurementsPath = join(scratch, "measurements.jsonl");
    writeFileSync(measurementsPath, "");
    const status = run(measurementsPath);
    if (status !== 0) {
      log(`the suite exited ${String(status)}: nothing recorded`);
      return 1;
    }
    const merged = mergeFloors(
      readFloors(floorsPath),
      parseMeasurements(readFileSync(measurementsPath, "utf8")),
    );
    if (merged.refused.length > 0) {
      merged.refused.forEach((reason) => {
        log(reason);
      });
      log("nothing recorded");
      return 1;
    }
    writeFileSync(floorsPath, `${JSON.stringify(merged.floors, null, 2)}\n`);
    (merged.moved.length > 0 ? merged.moved : ["no floor moved"]).forEach((line) => {
      log(line);
    });
    return 0;
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
};
