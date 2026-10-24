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
import { asProgram } from "./lib/program.ts";

/** What downloads the run's artifact, as this script calls `spawnSync`. */
export type Spawn = (
  command: string,
  args: string[],
  options: { stdio: "inherit" },
) => { status: number | null };

/** The program's work, given its arguments, floors file, `gh` and output, so a unit test stands
 * them in (#374 AC6): its exit status. */
export function fetchProgram(
  argv: readonly string[],
  floorsPath: string,
  download: Spawn,
  log: (line: string) => void,
  error: (line: string) => void,
): number {
  const run = argv[2] ?? "";
  if (!/^\d+$/u.test(run)) {
    error("usage: npm run floors:fetch <run id of a record-floors workflow run>");
    return 1;
  }
  const into = mkdtempSync(join(tmpdir(), "floors-"));
  const asked = ["run", "download", run, "--name", "floors", "--dir", into];
  if (download("gh", asked, { stdio: "inherit" }).status !== 0) {
    error(`floors:fetch: could not download the floors of run ${run}`);
    return 1;
  }
  const text = readFileSync(join(into, "floors.json"), "utf8");
  const floors = JSON.parse(text) as unknown;
  const whole =
    typeof floors === "object" &&
    floors !== null &&
    Object.values(floors).every((value) => Number.isInteger(value) && Number(value) >= 0);
  const lines = join(into, basename(commitLinesPath(floorsPath)));
  if (!existsSync(lines)) {
    error(`floors:fetch: run ${run} recorded no commit lines; record again (#367)`);
    return 1;
  }
  if (!whole) {
    error(`floors:fetch: run ${run}'s floors.json is not a record of whole-number floors`);
    return 1;
  }
  writeFileSync(floorsPath, text);
  log(
    `floors:fetch: wrote ${floorsPath} from run ${run}; review the diff, fold it into the ` +
      "unpushed commit with these lines in its message, push the branch, then delete the " +
      "scratch ref:",
  );
  log(readFileSync(lines, "utf8").trimEnd());
  return 0;
}

asProgram(
  import.meta.main,
  fetchProgram,
  process.argv,
  FLOORS_PATH,
  spawnSync,
  console.log,
  console.error,
);
