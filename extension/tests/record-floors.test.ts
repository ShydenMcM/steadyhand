/**
 * `npm run floors:record` with its process, environment, recorder and output stood in (#374 AC6):
 * it records only in CI, where it runs every suite in record mode through the recorder, and refuses
 * anywhere else. `recordFloors` itself is tested in `tests/floors.test.ts`; here the recorder is a
 * stand-in passed as an argument (no module mock, #394) that runs the suite runner it is handed, so
 * the command that runner starts is seen.
 */
import { expect, test, vi } from "vitest";
import { FLOORS_PATH, RECORD_ADVICE } from "./lib/floors.ts";
import { type RecordFloors, recordProgram, type Spawn } from "./record-floors.ts";

function recorder(): ReturnType<typeof vi.fn<RecordFloors>> {
  return vi.fn<RecordFloors>((path, run, log) => {
    log(`recording ${path}`);
    return run("/scratch/measurements.json") + 40;
  });
}

interface Started {
  command: string;
  args: readonly string[];
  env: NodeJS.ProcessEnv;
}

function spawned(status: number | null): { spawn: Spawn; started: Started[] } {
  const started: Started[] = [];
  const spawn: Spawn = (command, args, options) => {
    started.push({ command, args, env: options.env });
    return { status };
  };
  return { spawn, started };
}

test("in CI it records the floors, running every suite in record mode", () => {
  const { spawn, started } = spawned(2);
  const recorded = recorder();
  const lines: string[] = [];
  const code = recordProgram(
    { GITHUB_ACTIONS: "true", KEPT: "k" },
    spawn,
    recorded,
    (line) => lines.push(line),
    () => {},
  );
  expect(code).toBe(42);
  expect(recorded.mock.calls.map(([path]) => path)).toEqual([FLOORS_PATH]);
  expect(lines).toEqual([`recording ${FLOORS_PATH}`]);
  expect(started).toEqual([
    {
      command: process.execPath,
      args: [expect.stringMatching(/\/node_modules\/vitest\/vitest\.mjs$/u), "run"],
      env: {
        GITHUB_ACTIONS: "true",
        KEPT: "k",
        STEADYHAND_FLOORS_RECORD: "/scratch/measurements.json",
      },
    },
  ]);
});

test("a suite run with no exit status counts as failed", () => {
  const { spawn } = spawned(null);
  expect(
    recordProgram(
      { GITHUB_ACTIONS: "true" },
      spawn,
      recorder(),
      () => {},
      () => {},
    ),
  ).toBe(41);
});

test.each([{}, { GITHUB_ACTIONS: "false" }, { GITHUB_ACTIONS: "1" }])(
  "outside CI (%j) it refuses, records nothing and starts nothing",
  (env) => {
    const { spawn, started } = spawned(0);
    const recorded = recorder();
    const errors: string[] = [];
    expect(
      recordProgram(
        env,
        spawn,
        recorded,
        () => {},
        (line) => errors.push(line),
      ),
    ).toBe(1);
    expect(errors).toEqual([
      `floors:record runs only in CI: ${RECORD_ADVICE} (#285, CI records and the laptop commits)`,
    ]);
    expect(recorded).not.toHaveBeenCalled();
    expect(started).toEqual([]);
  },
);
