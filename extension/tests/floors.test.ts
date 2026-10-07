import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeAll, describe, expect, test } from "vitest";
import {
  FLOORS_PATH,
  floorBreach,
  type Measurement,
  mergeFloors,
  parseFloors,
  parseMeasurements,
  RECORD_ENV,
  readFloors,
  recordFloors,
} from "./lib/floors.ts";

const scratches: string[] = [];

/** A fresh directory for one test, removed after it. */
const scratch = (): string => {
  const directory = mkdtempSync(join(tmpdir(), "steadyhand-floors-test-"));
  scratches.push(directory);
  return directory;
};

afterEach(() => {
  scratches.splice(0).forEach((directory) => {
    rmSync(directory, { recursive: true, force: true });
  });
});

/** A floors file holding `floors`, in a fresh directory. */
const floorsFile = (floors: Record<string, number>): string => {
  const path = join(scratch(), "floors.json");
  writeFileSync(path, `${JSON.stringify(floors, null, 2)}\n`);
  return path;
};

const at = (test: string, id: string, measured: number): Measurement => ({ id, measured, test });

test("the recorded floors file holds whole numbers of zero or more, by id", () => {
  expect(() => readFloors(FLOORS_PATH)).not.toThrow();
});

test.each([
  ["an array", "[1]", "the floors file is not an object of floor ids"],
  ["null", "null", "the floors file is not an object of floor ids"],
  ["a fraction", '{"a.files": 1.5}', "floor a.files: 1.5 is not a whole number of zero or more"],
  ["a negative", '{"a.files": -1}', "floor a.files: -1 is not a whole number of zero or more"],
  ["a string", '{"a.files": "3"}', 'floor a.files: "3" is not a whole number of zero or more'],
])("a floors file holding %s is refused", (_, text, message) => {
  expect(() => parseFloors(text)).toThrow(message);
});

test("a floors file of whole numbers reads as written", () => {
  expect(parseFloors('{"a.files": 0, "b.tests": 12}')).toEqual({ "a.files": 0, "b.tests": 12 });
});

test("a measurement equal to its record breaks nothing", () => {
  expect(floorBreach("a.files", 3, {}, floorsFile({ "a.files": 3 }))).toBeUndefined();
});

test("growth breaks the floor until it is recorded, naming the delta", () => {
  expect(floorBreach("a.files", 4, {}, floorsFile({ "a.files": 3 }))).toBe(
    "floor a.files: measured 4, recorded 3 (+1); read the growth against the diff, then run " +
      "npm run floors:record",
  );
});

test("a loss breaks the floor and says a reader may have gone blind", () => {
  expect(floorBreach("a.files", 2, {}, floorsFile({ "a.files": 3 }))).toBe(
    "floor a.files: measured 2, recorded 3 (-1); a reader may have gone blind to part of its " +
      "population. If it really shrank, lower the figure in tests/floors.json by a deliberate edit",
  );
});

test("an id with no record breaks the floor, naming the recorder", () => {
  expect(floorBreach("a.files", 3, {}, floorsFile({}))).toBe(
    "floor a.files: none recorded, measured 3; run npm run floors:record",
  );
});

test("recording appends the measurement and the test that asserted it, and judges nothing", () => {
  const measurements = join(scratch(), "m.jsonl");
  const floors = floorsFile({ "a.files": 3 });
  expect(floorBreach("a.files", 9, { [RECORD_ENV]: measurements }, floors)).toBeUndefined();
  const [line] = parseMeasurements(readFileSync(measurements, "utf8"));
  expect(line).toMatchObject({ id: "a.files", measured: 9 });
  expect(line?.test).toMatch(
    /^tests\/floors\.test\.ts > recording appends the measurement and the test that asserted it, and judges nothing$/u,
  );
});

test("recording refuses to run in CI, so CI can never pass a floor unjudged", () => {
  const env = { [RECORD_ENV]: join(scratch(), "m.jsonl"), CI: "true" };
  expect(() => floorBreach("a.files", 3, env, floorsFile({}))).toThrow(
    "floors are recorded on a developer's machine, never in CI",
  );
});

/** What recording a floor from a hook does: run before any test, and after one (2026-10-06:
 * there `expect.getState()` still named the test before, so the runner is asked instead). */
const recordFromAHook = (): unknown => {
  try {
    floorBreach("a.files", 3, { [RECORD_ENV]: join(scratch(), "m.jsonl") });
    return undefined;
  } catch (error) {
    return error;
  }
};

const OUTSIDE = new Error(
  "a floor is asserted inside a test, so the recorder can tell who owns it",
);

let fromTheFileHook: unknown;
beforeAll(() => {
  fromTheFileHook = recordFromAHook();
});

test("a floor recorded from a hook before any test is refused", () => {
  expect(fromTheFileHook).toEqual(OUTSIDE);
});

describe("after a test has run", () => {
  let fromASuiteHook: unknown;
  beforeAll(() => {
    fromASuiteHook = recordFromAHook();
  });

  test("a floor recorded from a suite's hook is refused, not credited to the test before", () => {
    expect(fromASuiteHook).toEqual(OUTSIDE);
  });
});

test("the recorder records a new floor", () => {
  expect(mergeFloors({}, [at("t1", "a.files", 3)])).toEqual({
    floors: { "a.files": 3 },
    moved: ["a.files: new, 3"],
    refused: [],
  });
});

test("the recorder raises a floor that grew, printing its delta", () => {
  expect(mergeFloors({ "a.files": 3 }, [at("t1", "a.files", 5)])).toEqual({
    floors: { "a.files": 5 },
    moved: ["a.files: 3 → 5 (+2)"],
    refused: [],
  });
});

test("the recorder leaves an unchanged floor alone and prints nothing for it", () => {
  expect(mergeFloors({ "a.files": 3 }, [at("t1", "a.files", 3)])).toEqual({
    floors: { "a.files": 3 },
    moved: [],
    refused: [],
  });
});

test("the recorder never lowers a floor", () => {
  expect(mergeFloors({ "a.files": 3 }, [at("t1", "a.files", 2)]).refused).toEqual([
    "floor a.files: measured 2, below its record of 3; the recorder never lowers a floor. " +
      "Lower it by a deliberate edit if the population really shrank",
  ]);
});

test("the recorder refuses an id asserted from two places", () => {
  expect(mergeFloors({}, [at("t1", "a.files", 3), at("t2", "a.files", 3)]).refused).toEqual([
    "floor a.files is asserted from 2 places: t1; t2",
  ]);
});

test("the recorder refuses an id measured twice with two figures in one test", () => {
  expect(mergeFloors({}, [at("t1", "a.files", 3), at("t1", "a.files", 4)]).refused).toEqual([
    "floor a.files measured 3 and 4 in one run",
  ]);
});

test("the recorder refuses a recorded id that no test asserts any more", () => {
  expect(mergeFloors({ "a.files": 3, "b.tests": 1 }, [at("t1", "a.files", 3)]).refused).toEqual([
    "floor b.tests is recorded, but no test asserted it; remove it by a deliberate edit",
  ]);
});

test("the recorder writes the floors sorted by id", () => {
  const merged = mergeFloors({}, [at("t1", "b.tests", 1), at("t2", "a.files", 2)]);
  expect(Object.keys(merged.floors)).toEqual(["a.files", "b.tests"]);
  expect(merged.moved).toEqual(["a.files: new, 2", "b.tests: new, 1"]);
});

test("measurements read one JSON object a line", () => {
  const text = `${JSON.stringify(at("t1", "a.files", 3))}\n${JSON.stringify(at("t2", "b", 1))}\n`;
  expect(parseMeasurements(text)).toEqual([at("t1", "a.files", 3), at("t2", "b", 1)]);
});

test("a malformed measurement is refused by its line number", () => {
  expect(() => parseMeasurements('{"id": "a.files", "measured": 1.5, "test": "t1"}\n')).toThrow(
    'measurement 1 is not {id, measured, test}: {"id": "a.files", "measured": 1.5, "test": "t1"}',
  );
});

/** A suite run that writes `measurements` and exits `status`, in place of the real suite. */
const suite =
  (measurements: readonly Measurement[], status = 0) =>
  (path: string): number => {
    writeFileSync(path, measurements.map((m) => `${JSON.stringify(m)}\n`).join(""));
    return status;
  };

test("a recording writes the raised floors and prints each one that moved", () => {
  const path = floorsFile({ "a.files": 3 });
  const lines: string[] = [];
  expect(recordFloors(path, suite([at("t1", "a.files", 4)]), (l) => lines.push(l))).toBe(0);
  expect(readFileSync(path, "utf8")).toBe('{\n  "a.files": 4\n}\n');
  expect(lines).toEqual(["a.files: 3 → 4 (+1)"]);
});

test("a recording where nothing moved says so", () => {
  const path = floorsFile({ "a.files": 3 });
  const lines: string[] = [];
  expect(recordFloors(path, suite([at("t1", "a.files", 3)]), (l) => lines.push(l))).toBe(0);
  expect(lines).toEqual(["no floor moved"]);
});

test("a recording whose suite failed writes nothing", () => {
  const path = floorsFile({ "a.files": 3 });
  const lines: string[] = [];
  expect(recordFloors(path, suite([at("t1", "a.files", 9)], 1), (l) => lines.push(l))).toBe(1);
  expect(readFloors(path)).toEqual({ "a.files": 3 });
  expect(lines).toEqual(["the suite exited 1: nothing recorded"]);
});

test("a recording with a refusal prints it and writes nothing", () => {
  const path = floorsFile({ "a.files": 3 });
  const lines: string[] = [];
  expect(recordFloors(path, suite([at("t1", "a.files", 2)]), (l) => lines.push(l))).toBe(1);
  expect(readFloors(path)).toEqual({ "a.files": 3 });
  expect(lines).toEqual([
    "floor a.files: measured 2, below its record of 3; the recorder never lowers a floor. " +
      "Lower it by a deliberate edit if the population really shrank",
    "nothing recorded",
  ]);
});
