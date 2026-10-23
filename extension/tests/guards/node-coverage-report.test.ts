/**
 * The program that writes Node's coverage of the test, setup and config files (#394), read with
 * this checkout's own config. Reading the config loads Vite, more than a unit file's load allows,
 * and the files it names are found across the tree, so this runs with the guards; the program's
 * work (`report`) is tested in unit, in `tests/node-coverage.test.ts`.
 */
import { join } from "node:path";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { main, SETTINGS } from "../node-coverage-report.ts";

let exitCode: typeof process.exitCode;

beforeEach(() => {
  exitCode = process.exitCode;
  process.exitCode = undefined;
});

afterEach(() => {
  process.exitCode = exitCode;
  vi.restoreAllMocks();
});

const EXTENSION = join(import.meta.dirname, "..", "..");

test("the settings are this checkout's config, its three projects and Vitest's default exclude", () => {
  expect(SETTINGS.root).toBe(EXTENSION);
  expect(SETTINGS.configFile).toBe(join(EXTENSION, "vitest.config.ts"));
  const names = SETTINGS.projects.map(
    (project) => (project as { test: { name: string } }).test.name,
  );
  expect(names).toEqual(["unit", "guards", "integration"]);
  expect(SETTINGS.defaultExclude).toContain("**/node_modules/**");
});

test("run as a program, its status is the report's, and its refusal printed", async () => {
  const printed = vi.spyOn(console, "error").mockImplementation(() => undefined);
  const missing = join(EXTENSION, "no-such-raw-folder");
  await main(true, ["--raw", missing, "--out", missing, "--project", "unit"]);
  const code = process.exitCode;
  process.exitCode = undefined;
  expect(code).toBe(1);
  expect(printed.mock.calls).toHaveLength(1);
  expect(String(printed.mock.calls[0]?.[0])).toMatch(`node coverage: cannot read ${missing}`);
});

test.each([false, undefined])("imported (main is %s), it does nothing", async (isProgram) => {
  const printed = vi.spyOn(console, "error").mockImplementation(() => undefined);
  await main(isProgram, []);
  expect(process.exitCode).toBeUndefined();
  expect(printed).not.toHaveBeenCalled();
});
