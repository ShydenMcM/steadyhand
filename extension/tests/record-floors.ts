/**
 * `npm run floors:record`: run every suite (unit and guards) in record mode, then raise each
 * floor that grew, printing every one that moved with its delta and writing those lines beside
 * the floors for the commit message. It never lowers a floor. It runs only in the `record-floors`
 * workflow, on a scratch ref `refs/floors/<branch>` the session pushed (#367), never on the laptop
 * and never in the checks the floors feed (#285; `tests/guards/test_extension_ci.py` reads every
 * workflow and asserts it). On the laptop, `npm run floors:fetch <run id>` writes what that
 * workflow recorded, to fold into the commit before the branch is pushed.
 */
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { FLOORS_PATH, RECORD_ADVICE, RECORD_ENV, recordFloors } from "./lib/floors.ts";

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
    `floors:record runs only in CI: ${RECORD_ADVICE} (#285, CI records and the laptop commits)`,
  );
  process.exitCode = 1;
}
