/**
 * A script's program entry (#374 AC6): run as a program it sets the exit status from its work;
 * imported, as a unit test imports it, it does nothing, so both arms run in-process.
 */
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { asProgram } from "./lib/program.ts";

let exitCode: typeof process.exitCode;

beforeEach(() => {
  exitCode = process.exitCode;
  process.exitCode = undefined;
});

afterEach(() => {
  process.exitCode = exitCode;
});

test("run as a program, its work runs with its arguments and sets the exit status", () => {
  const work = vi.fn((name: string, count: number) => name.length + count);
  asProgram(true, work, "x", 2);
  const code = process.exitCode;
  process.exitCode = undefined;
  expect(work.mock.calls).toEqual([["x", 2]]);
  expect(code).toBe(3);
});

test.each([false, undefined])("imported (main is %s), its work never runs", (isProgram) => {
  const work = vi.fn<() => number>();
  asProgram(isProgram, work);
  expect(work).not.toHaveBeenCalled();
  expect(process.exitCode).toBeUndefined();
});
