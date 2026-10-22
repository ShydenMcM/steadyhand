/**
 * `npm run floors:fetch <run id>` with `gh` and the floors file stood in (#374 AC6): `gh` is a
 * function that writes what the run's artifact would hold into the folder it is asked for, and the
 * floors file is a temporary one, so no test writes `tests/floors.json`.
 */
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, expect, test } from "vitest";
import type { Spawn } from "./fetch-floors.ts";

const { fetchProgram } = await import("./fetch-floors.ts");

const FLOORS = '{\n  "a": 3,\n  "b": 0\n}\n';
const LINES = "floors: a 2 -> 3\n";
let home = "";
let floorsPath = "";
let started: string[][] = [];
let printed: string[] = [];
let refused: string[] = [];

beforeEach(() => {
  home = mkdtempSync(join(tmpdir(), "steadyhand-fetch-unit-"));
  floorsPath = join(home, "floors.json");
  writeFileSync(floorsPath, "old\n");
  started = [];
  printed = [];
  refused = [];
});

afterEach(() => {
  rmSync(home, { recursive: true, force: true });
});

/** `gh run download`, answering with *status* after writing *files* into its `--dir`. */
function gh(status: number | null, files: Record<string, string>): Spawn {
  return (command, args) => {
    started.push([command, ...args]);
    const into = args[args.indexOf("--dir") + 1] ?? "";
    for (const [name, text] of Object.entries(files)) writeFileSync(join(into, name), text);
    return { status };
  };
}

function fetch(argv: string[], download: Spawn): number {
  return fetchProgram(
    argv,
    floorsPath,
    download,
    (line) => printed.push(line),
    (line) => refused.push(line),
  );
}

const ARTIFACT = { "floors.json": FLOORS, "floors-commit-lines.txt": LINES };

test("a recorded run's floors are written, and the lines that moved printed for the commit", () => {
  expect(fetch(["node", "fetch-floors.ts", "42"], gh(0, ARTIFACT))).toBe(0);
  expect(readFileSync(floorsPath, "utf8")).toBe(FLOORS);
  expect(started.map((call) => call.slice(0, 6))).toEqual([
    ["gh", "run", "download", "42", "--name", "floors"],
  ]);
  expect(printed).toEqual([
    `floors:fetch: wrote ${floorsPath} from run 42; review the diff, fold it into the unpushed ` +
      "commit with these lines in its message, push the branch, then delete the scratch ref:",
    "floors: a 2 -> 3",
  ]);
  expect(refused).toEqual([]);
});

test.each([[[]], [["4x2"]], [[""]], [["-1"]]])(
  "a run id that is not a number (%j) is refused before anything is downloaded",
  (rest) => {
    expect(fetch(["node", "fetch-floors.ts", ...rest], gh(0, ARTIFACT))).toBe(1);
    expect(refused).toEqual([
      "usage: npm run floors:fetch <run id of a record-floors workflow run>",
    ]);
    expect(started).toEqual([]);
  },
);

test.each([1, null])("a download that fails (status %s) is refused, writing nothing", (status) => {
  expect(fetch(["node", "fetch-floors.ts", "42"], gh(status, {}))).toBe(1);
  expect(refused).toEqual(["floors:fetch: could not download the floors of run 42"]);
  expect(readFileSync(floorsPath, "utf8")).toBe("old\n");
});

test("a run that recorded no commit lines is refused, writing nothing", () => {
  expect(fetch(["node", "fetch-floors.ts", "42"], gh(0, { "floors.json": FLOORS }))).toBe(1);
  expect(refused).toEqual(["floors:fetch: run 42 recorded no commit lines; record again (#367)"]);
  expect(readFileSync(floorsPath, "utf8")).toBe("old\n");
});

test.each(['{"a": -1}', '{"a": 1.5}', '{"a": "3"}', "null", "7"])(
  "floors that are not whole-number floors (%s) are refused, writing nothing",
  (text) => {
    const download = gh(0, { "floors.json": text, "floors-commit-lines.txt": LINES });
    expect(fetch(["node", "fetch-floors.ts", "42"], download)).toBe(1);
    expect(refused).toEqual([
      "floors:fetch: run 42's floors.json is not a record of whole-number floors",
    ]);
    expect(readFileSync(floorsPath, "utf8")).toBe("old\n");
  },
);

test("the artifact is downloaded into a fresh folder of its own, never beside the floors", () => {
  fetch(["node", "fetch-floors.ts", "42"], gh(0, ARTIFACT));
  const into = started[0]?.[started[0].indexOf("--dir") + 1] ?? "";
  expect(into.startsWith(join(tmpdir(), "floors-"))).toBe(true);
  expect(existsSync(join(into, "floors.json"))).toBe(true);
});
