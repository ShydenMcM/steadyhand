/**
 * `npm run floors:record`: run every suite (unit and guards) in record mode, then raise each
 * floor that grew, printing every one that moved with its delta. It never lowers a floor. It runs
 * only in the `record-floors` workflow, never on the laptop and never in the checks the floors feed
 * (#285; `tests/guards/test_extension_ci.py` reads every workflow and asserts it). On the laptop,
 * `npm run floors:fetch <run id>` writes what that workflow recorded.
 */
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { FLOORS_PATH, RECORD_ENV, recordFloors } from "./lib/floors.ts";

const VITEST = join(import.meta.dirname, "..", "node_modules", "vitest", "vitest.mjs");

if (process.env.GITHUB_ACTIONS === "true") {
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
} else {
  console.error(
    "floors:record runs only in CI: label the pull request `record-floors`, then " +
      "`npm run floors:fetch <run id>` (#285, CI records and the laptop commits)",
  );
  process.exitCode = 1;
}
