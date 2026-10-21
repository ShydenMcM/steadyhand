/**
 * `npm run floors:fetch <run id>`: write the floors the `record-floors` workflow recorded in that
 * run into `tests/floors.json`, for review and a commit (#285: CI records, the laptop commits),
 * and print the lines that moved for that commit's message. The commit is the unpushed one the
 * run measured on its scratch ref (#367). It refuses a run whose files are missing or whose
 * floors are not a record of whole-number floors.
 */
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import { commitLinesPath, FLOORS_PATH } from "./lib/floors.ts";

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
    const lines = join(into, basename(commitLinesPath(FLOORS_PATH)));
    if (!existsSync(lines)) {
      console.error(`floors:fetch: run ${run} recorded no commit lines; record again (#367)`);
      process.exitCode = 1;
    } else if (whole) {
      writeFileSync(FLOORS_PATH, text);
      console.log(
        `floors:fetch: wrote ${FLOORS_PATH} from run ${run}; review the diff, fold it into the ` +
          "unpushed commit with these lines in its message, push the branch, then delete the " +
          "scratch ref:",
      );
      console.log(readFileSync(lines, "utf8").trimEnd());
    } else {
      console.error(
        `floors:fetch: run ${run}'s floors.json is not a record of whole-number floors`,
      );
      process.exitCode = 1;
    }
  }
}
