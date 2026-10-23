/**
 * The setup file every project runs first (#394): after each test file, write Node's own V8
 * coverage (`NODE_V8_COVERAGE`) of everything this worker ran. Vitest stops its workers with a
 * signal, and a process stopped so never writes the coverage Node writes at a normal exit
 * (measured 2026-10-23: no worker's report without this, all ten with it). Registered first, its
 * `afterAll` runs after every other setup file's. Without `NODE_V8_COVERAGE`, `takeCoverage` does
 * nothing.
 */
import { takeCoverage } from "node:v8";
import { afterAll } from "vitest";

afterAll(() => {
  takeCoverage();
});
