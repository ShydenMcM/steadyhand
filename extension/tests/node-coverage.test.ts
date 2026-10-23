/**
 * The converter from Node's raw V8 coverage to the gate's istanbul report (#394), run on files
 * written to a temporary folder and raw reports shaped as V8 writes them. The real run's reports
 * are converted in CI by `tests/node-coverage-report.ts` (its work is `report`, tested here); `tests/integration/node-coverage.test.ts`
 * converts a report Node itself wrote.
 */
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { afterEach, beforeEach, expect, test } from "vitest";
import {
  type FunctionCoverage,
  measuredFiles,
  NodeCoverageError,
  projectFiles,
  readRawReports,
  report,
  type ScriptCoverage,
  type Settings,
  toIstanbul,
} from "./lib/node-coverage.ts";

let root = "";

beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), "steadyhand-node-coverage-"));
});

afterEach(async () => {
  await rm(root, { recursive: true, force: true });
});

/** Writes *text* at *path* under the temporary root, its folders first; the absolute path. */
async function file(path: string, text: string): Promise<string> {
  const absolute = join(root, path);
  await mkdir(join(absolute, ".."), { recursive: true });
  await writeFile(absolute, text);
  return absolute;
}

/** What Node runs for a strip-only TypeScript *source* loaded from *url*: its types blanked (the
 * fixtures below hold only annotations, each blanked to as many spaces) and one sourceURL line. */
function ran(blanked: string, url: string): string {
  return `${blanked}\n\n//# sourceURL=${url}`;
}

/** A script whose whole code ran once, with *functions* after the top level. */
function script(url: string, code: string, functions: FunctionCoverage[] = []): ScriptCoverage {
  const top = { startOffset: 0, endOffset: code.length, count: 1 };
  return {
    url,
    functions: [{ functionName: "", isBlockCoverage: true, ranges: [top] }, ...functions],
  };
}

const SOURCE =
  "const a: number = 1;\nexport function f(x: number): number {\n  return x > 0 ? a : 2;\n}\n";
const BLANKED =
  "const a         = 1;\nexport function f(x        )         {\n  return x > 0 ? a : 2;\n}\n";

/** Function `f` of SOURCE, run *count* times. */
function f(count: number): FunctionCoverage {
  const start = SOURCE.indexOf("function f");
  const end = SOURCE.indexOf("}\n") + 1;
  return {
    functionName: "f",
    isBlockCoverage: true,
    ranges: [{ startOffset: start, endOffset: end, count }],
  };
}

test("the fixture's blanked text is what Node runs for it, position for position", () => {
  expect(BLANKED).toHaveLength(SOURCE.length);
});

test("the projects named are read in the order named, with their include, exclude and setup files", () => {
  const projects = [
    { test: { name: "unit", include: ["a/**"], exclude: ["a/x/**"], setupFiles: ["s.ts"] } },
    { test: { name: "guards", include: ["g/**"], exclude: ["g/y/**"], setupFiles: ["t.ts"] } },
  ];
  expect(projectFiles(projects, ["guards", "unit"], ["d/**"])).toEqual([
    { name: "guards", include: ["g/**"], exclude: ["g/y/**"], setupFiles: ["t.ts"] },
    { name: "unit", include: ["a/**"], exclude: ["a/x/**"], setupFiles: ["s.ts"] },
  ]);
});

test("a project naming no exclude takes Vitest's default, and one naming no setup file has none", () => {
  const projects = [{ test: { name: "guards", include: ["g/**"] } }];
  expect(projectFiles(projects, ["guards"], ["d/**"])).toEqual([
    { name: "guards", include: ["g/**"], exclude: ["d/**"], setupFiles: [] },
  ]);
});

test("a project name the config does not hold is refused, naming it", () => {
  const projects = [{ test: { name: "unit", include: ["a/**"] } }];
  expect(() => projectFiles(projects, ["unit", "gaurds"], [])).toThrow(
    new NodeCoverageError("the config holds no project named gaurds"),
  );
});

test("a project that names no include is refused: Node's coverage measures only what the config names", () => {
  const projects = [{ test: { name: "unit" } }];
  expect(() => projectFiles(projects, ["unit"], [])).toThrow(
    new NodeCoverageError("the config's project unit names no include"),
  );
});

test("the files measured are those included and not excluded, the setup files and the config", async () => {
  const kept = await file("tests/a.test.ts", "");
  const nested = await file("tests/deep/b.test.ts", "");
  await file("tests/guards/c.test.ts", "");
  await file("tests/d.ts", "");
  const setup = await file("tests/setup.ts", "");
  const config = await file("vitest.config.ts", "");
  const unit = {
    name: "unit",
    include: ["tests/**/*.test.ts"],
    exclude: ["tests/guards/**"],
    setupFiles: ["tests/setup.ts"],
  };
  expect(measuredFiles(root, config, [unit])).toEqual([kept, nested, setup, config]);
});

test("a file two projects name is measured once", async () => {
  const shared = await file("tests/a.test.ts", "");
  const config = await file("vitest.config.ts", "");
  const one = {
    name: "one",
    include: ["tests/*.test.ts"],
    exclude: [],
    setupFiles: ["tests/a.test.ts"],
  };
  const two = { name: "two", include: ["tests/**/*.test.ts"], exclude: [], setupFiles: [] };
  expect(measuredFiles(root, config, [one, two])).toEqual([shared, config]);
});

test("every script of every raw report is read, the reports in name order", async () => {
  const first = { url: "file:///a.ts", functions: [] };
  const second = { url: "file:///b.ts", functions: [] };
  await file("raw/coverage-2.json", JSON.stringify({ result: [second] }));
  await file("raw/coverage-1.json", JSON.stringify({ result: [first] }));
  expect(readRawReports(join(root, "raw"))).toEqual([first, second]);
});

test("a folder holding no raw report is refused: the run wrote none", async () => {
  await file("raw/notes.txt", "");
  expect(() => readRawReports(join(root, "raw"))).toThrow(
    new NodeCoverageError(`${join(root, "raw")} holds no raw coverage report (coverage-*.json)`),
  );
});

test("a missing folder is refused, naming it", () => {
  const missing = join(root, "none");
  expect(() => readRawReports(missing)).toThrow(NodeCoverageError);
  expect(() => readRawReports(missing)).toThrow(`cannot read ${missing}`);
});

test.each([
  ["not JSON", "{"],
  ["no result list", JSON.stringify({ results: [] })],
])("a raw report that is %s is refused, naming it", async (_kind, text) => {
  const report = await file("raw/coverage-1.json", text);
  expect(() => readRawReports(join(root, "raw"))).toThrow(
    new RegExp(`^${report}: not a raw V8 coverage report`),
  );
});

test("a TypeScript file converts with its types counted as nothing, and an uncalled function unrun", async () => {
  const path = await file("tests/a.test.ts", SOURCE);
  const url = pathToFileURL(path).href;
  const report = await toIstanbul([script(url, ran(BLANKED, url), [f(0)])], [path]);
  expect(Object.keys(report)).toEqual([path]);
  expect(report[path]?.s).toEqual({ 0: 1, 1: 0 });
  expect(report[path]?.f).toEqual({ 0: 0 });
  expect(report[path]?.b).toEqual({ 0: [0, 0] });
});

test("one file's scripts from several workers are summed, their queries left off", async () => {
  const path = await file("tests/setup.ts", SOURCE);
  const url = pathToFileURL(path).href;
  const one = `${url}?vitest=1`;
  const two = `${url}?vitest=22`;
  const report = await toIstanbul(
    [script(one, ran(BLANKED, one), [f(2)]), script(two, ran(BLANKED, two), [f(1)])],
    [path],
  );
  expect(report[path]?.s).toEqual({ 0: 2, 1: 3 });
  expect(report[path]?.f).toEqual({ 0: 3 });
});

test("a file the run never loaded is refused, naming it", async () => {
  const loaded = await file("tests/a.test.ts", SOURCE);
  const never = await file("tests/b.test.ts", SOURCE);
  const url = pathToFileURL(loaded).href;
  await expect(toIstanbul([script(url, ran(BLANKED, url))], [loaded, never])).rejects.toThrow(
    new NodeCoverageError(`${never}: no raw report holds it, so the run never loaded it`),
  );
});

test("a script that ran as other code than the file holds is refused: rewritten, or changed since", async () => {
  const path = await file("tests/a.test.ts", SOURCE);
  const url = pathToFileURL(path).href;
  const rewritten = `${BLANKED}vi.mock("x");\n`;
  const expected = ran(BLANKED, url).length;
  await expect(toIstanbul([script(url, ran(rewritten, url))], [path])).rejects.toThrow(
    new NodeCoverageError(
      `${path}: the code that ran is ${expected + rewritten.length - BLANKED.length} characters, the file stripped of its types ${expected}; it ran rewritten, or the file changed since`,
    ),
  );
});

test("a test or setup file Vitest loaded outside the files measured is refused: the set missed it", async () => {
  const path = await file("tests/a.test.ts", SOURCE);
  const stray = await file("tests/other/b.test.ts", SOURCE);
  const url = pathToFileURL(path).href;
  const strayUrl = `${pathToFileURL(stray).href}?vitest=5`;
  await expect(
    toIstanbul([script(url, ran(BLANKED, url)), script(strayUrl, ran(BLANKED, strayUrl))], [path]),
  ).rejects.toThrow(
    new NodeCoverageError(
      `${stray}: Vitest loaded it as a test or setup file, but the config's settings do not name it`,
    ),
  );
});

test("scripts outside the files measured are left out: package sources, Node's own and built ones", async () => {
  const path = await file("tests/a.test.ts", SOURCE);
  const other = await file("packages/core/src/index.ts", SOURCE);
  const url = pathToFileURL(path).href;
  const report = await toIstanbul(
    [
      script("node:internal/main", "x"),
      script(pathToFileURL(other).href, "y"),
      script(url, ran(BLANKED, url)),
    ],
    [path],
  );
  expect(Object.keys(report)).toEqual([path]);
});

/** A raw report in which each of *paths* (plain JavaScript, nothing to strip) ran once whole. */
async function rawReport(paths: string[]): Promise<void> {
  const result = await Promise.all(
    paths.map(async (path) => {
      const url = pathToFileURL(path).href;
      const code = `${await readFile(path, "utf8")}\n\n//# sourceURL=${url}`;
      const ranges = [{ startOffset: 0, endOffset: code.length, count: 1 }];
      return { url, functions: [{ functionName: "", isBlockCoverage: true, ranges }] };
    }),
  );
  await file("raw/coverage-1.json", JSON.stringify({ result }));
}

/** Settings for a config at the temporary root with one project, `unit`. */
function settings(): Settings {
  const unit = {
    test: { name: "unit", include: ["tests/*.test.ts"], setupFiles: ["tests/setup.ts"] },
  };
  return { root, configFile: join(root, "vitest.config.ts"), projects: [unit], defaultExclude: [] };
}

test("the report of the files measured is written for the gate, and each file's share printed", async () => {
  const config = await file("vitest.config.ts", "const a = 1;\n");
  const setup = await file("tests/setup.ts", "const b = 2;\nconst c = 3;\n");
  const spec = await file("tests/a.test.ts", "const d = 4;\n");
  await rawReport([config, setup, spec]);
  const log: string[] = [];
  const error: string[] = [];
  const argv = ["--raw", join(root, "raw"), "--out", join(root, "out"), "--project", "unit"];
  expect(
    await report(
      argv,
      settings(),
      (line) => log.push(line),
      (line) => error.push(line),
    ),
  ).toBe(0);
  const written = JSON.parse(
    await readFile(join(root, "out", "coverage-final.json"), "utf8"),
  ) as Record<string, { s: Record<string, number> }>;
  expect(Object.keys(written)).toEqual([spec, setup, config]);
  expect(written[setup]?.s).toEqual({ 0: 1, 1: 1 });
  expect(log).toEqual([
    "tests/a.test.ts: 1 of 1 statements run",
    "tests/setup.ts: 2 of 2 statements run",
    "vitest.config.ts: 1 of 1 statements run",
    `3 files measured by Node's own coverage, written to ${join(root, "out")}`,
  ]);
  expect(error).toEqual([]);
});

test.each([
  ["--raw", ["--out", "o", "--project", "unit"]],
  ["--out", ["--raw", "r", "--project", "unit"]],
  ["--project", ["--raw", "r", "--out", "o"]],
])("a run without %s is refused with the usage, and status 1", async (_missing, argv) => {
  const error: string[] = [];
  expect(
    await report(
      argv,
      settings(),
      () => undefined,
      (line) => error.push(line),
    ),
  ).toBe(1);
  expect(error).toEqual([
    "node coverage: usage: node-coverage-report.ts --raw <folder> --out <folder> --project <name>...",
  ]);
});

test("a refusal is printed and the status is 1, with no report written", async () => {
  await file("vitest.config.ts", "const a = 1;\n");
  const raw = join(root, "raw");
  await mkdir(raw);
  const error: string[] = [];
  const argv = ["--raw", raw, "--out", join(root, "out"), "--project", "unit"];
  expect(
    await report(
      argv,
      settings(),
      () => undefined,
      (line) => error.push(line),
    ),
  ).toBe(1);
  expect(error).toEqual([`node coverage: ${raw} holds no raw coverage report (coverage-*.json)`]);
  await expect(readFile(join(root, "out", "coverage-final.json"), "utf8")).rejects.toThrow(
    "ENOENT",
  );
});
