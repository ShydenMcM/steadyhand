/**
 * `npm run floors:record`: run the whole suite in record mode, then raise each floor that grew,
 * printing every one that moved with its delta. It never lowers a floor and never runs in CI
 * (`tests/meta/test_extension_ci.py` reads every workflow and asserts it).
 */
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { FLOORS_PATH, RECORD_ENV, recordFloors } from "./lib/floors.ts";

const VITEST = join(import.meta.dirname, "..", "node_modules", "vitest", "vitest.mjs");

process.exitCode = recordFloors(
  FLOORS_PATH,
  (measurementsPath) =>
    spawnSync(process.execPath, [VITEST, "run"], {
      stdio: "inherit",
      env: { ...process.env, [RECORD_ENV]: measurementsPath },
    }).status ?? 1,
  (line) => {
    console.log(line);
  },
);
