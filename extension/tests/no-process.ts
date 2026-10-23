/**
 * The unit project's FIRST setup file (#286): it refuses every process and outside connection
 * before the test file is imported, and fails a file or test that swallowed a refusal.
 */
import { afterEach, beforeAll } from "vitest";
import { install, raiseSwallowed, takeRefused } from "./lib/no-process.ts";

install();

beforeAll(() => {
  raiseSwallowed(takeRefused(), "loading the file: ");
});

afterEach(() => {
  raiseSwallowed(takeRefused(), "");
});
