/**
 * `npm run floors:fetch <run id>`: write the floors the `record-floors` workflow recorded in that
 * run into `tests/floors.json`, for review and a commit (#285: CI records, the laptop commits).
 * It refuses a run whose file is missing or not a record of whole-number floors.
 */
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { FLOORS_PATH } from "./lib/floors.ts";

const run = process.argv[2] ?? "";
if (!/^\d+$/u.test(run)) {
  console.error("usage: npm run floors:fetch <run id of a record-floors workflow run>");
  process.exitCode = 1;
} else {
  const into = mkdtempSync(join(tmpdir(), "floors-"));
  const downloaded = spawnSync("gh", ["run", "download", run, "--name", "floors", "--dir", into], {
    stdio: "inherit",
  });
  if (downloaded.status !== 0) {
    console.error(`floors:fetch: could not download the floors of run ${run}`);
    process.exitCode = 1;
  } else {
    const text = readFileSync(join(into, "floors.json"), "utf8");
    const floors = JSON.parse(text) as unknown;
    const whole =
      typeof floors === "object" &&
      floors !== null &&
      Object.values(floors).every((value) => Number.isInteger(value) && Number(value) >= 0);
    if (whole) {
      writeFileSync(FLOORS_PATH, text);
      console.log(
        `floors:fetch: wrote ${FLOORS_PATH} from run ${run}; review the diff, then commit`,
      );
    } else {
      console.error(
        `floors:fetch: run ${run}'s floors.json is not a record of whole-number floors`,
      );
      process.exitCode = 1;
    }
  }
}
