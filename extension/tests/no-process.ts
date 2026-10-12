/**
 * The unit project's FIRST setup file (#286): it refuses every process and outside connection
 * before the test file is imported, and fails a file or test that swallowed a refusal.
 */
import { afterEach, beforeAll } from "vitest";
import { install, swallowedMessage, takeRefused } from "./lib/no-process.ts";

install();

beforeAll(() => {
  const swallowed = swallowedMessage(takeRefused());
  if (swallowed !== undefined) throw new Error(`loading the file: ${swallowed}`);
});

afterEach(() => {
  const swallowed = swallowedMessage(takeRefused());
  if (swallowed !== undefined) throw new Error(swallowed);
});
