/**
 * `node tests/node-coverage-report.ts --raw <folder> --out <folder> --project <name>...` (#394):
 * after a native run (`npm run test:native`) wrote Node's raw V8 coverage into `--raw`, write the
 * istanbul report of the test files, setup files and config of the projects run to
 * `<out>/coverage-final.json`, for the coverage gate. The files come from the config's own
 * include, exclude and setup settings, so a file added later is measured with no list to edit.
 */
import { join } from "node:path";
import { transformSync } from "amaro";
import { configDefaults } from "vitest/config";
import config from "../vitest.config.ts";
import { report, type Settings } from "./lib/node-coverage.ts";

const EXTENSION = join(import.meta.dirname, "..");

/** This checkout's settings, read from `vitest.config.ts` as a plain run (`--mode test`) reads it.
 * Reading the config loads Vite under it, more than a unit file's load limit allows (measured
 * 2026-10-23: 105 ms of CPU against 100 ms), and globbing the tree is whole-tree work, so this
 * program is tested in the guards suite (`tests/guards/node-coverage-report.test.ts`) and its
 * logic in unit (`tests/node-coverage.test.ts`). */
/** Node's own stripper (amaro, bundled in Node): each type blanked in place, positions kept. Passed in,
 * not imported by the converter, whose unit tests stand it in (#405). */
export const stripTypes = (source: string): string =>
  transformSync(source, { mode: "strip-only" }).code;

export const SETTINGS: Settings = {
  root: EXTENSION,
  configFile: join(EXTENSION, "vitest.config.ts"),
  // The config always lists its projects; its type leaves every key optional.
  projects: (config({ mode: "test", command: "serve" }).test as { projects: unknown[] }).projects,
  defaultExclude: configDefaults.exclude,
  strip: stripTypes,
};

/** Write the report when Node runs this file as its program, and do nothing when it is imported:
 * a test runs both arms in-process. */
export async function main(isProgram: boolean | undefined, argv: string[]): Promise<void> {
  if (isProgram) {
    process.exitCode = await report(argv, SETTINGS, console.log, console.error);
  }
}

await main(import.meta.main, process.argv.slice(2));
