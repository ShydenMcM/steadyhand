/**
 * Node's own coverage, converted from reports Node itself wrote (#394): a TypeScript file Node
 * ran, and a planted project run by Vitest natively (`npm run test:native`'s flags) with the real
 * setup file that writes each worker's report. The converter's logic, on reports shaped by hand,
 * is unit-tested in `tests/node-coverage.test.ts`.
 */
import { execFile } from "node:child_process";
import { copyFile, mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { afterAll, assert, beforeAll, expect, test } from "vitest";
import {
  type FileCoverageData,
  readRawReports,
  report,
  type Settings,
  toIstanbul,
} from "../lib/node-coverage.ts";
import { FLUSH_NODE_COVERAGE } from "../../vitest.config.ts";
import { stripTypes } from "../node-coverage-report.ts";

const EXTENSION = join(import.meta.dirname, "..", "..");
const VITEST = join(EXTENSION, "node_modules/vitest/vitest.mjs");

const TYPED = `const a: number = 1;
export function used(x: number): number {
  return x > 0 ? a : 2;
}
export function unused(): string {
  return "never";
}
used(1);
`;

const PLANTED = `import { expect, test } from "vitest";

const half = (n: number): number => (n > 10 ? n / 2 : n);

test("halves", () => {
  expect(half(20)).toBe(10);
});
`;

const PROJECT = {
  test: { name: "planted", include: ["planted.test.ts"], setupFiles: ["flush.ts"] },
};

let folder = "";

beforeAll(async () => {
  folder = await mkdtemp(join(tmpdir(), "steadyhand-node-coverage-"));
  // Node resolves `vitest` from the planted files' folder, so it finds the extension's own.
  await symlink(join(EXTENSION, "node_modules"), join(folder, "node_modules"));
  await writeFile(join(folder, "typed.ts"), TYPED);
  await writeFile(join(folder, "planted.test.ts"), PLANTED);
  await copyFile(join(EXTENSION, FLUSH_NODE_COVERAGE), join(folder, "flush.ts"));
  await writeFile(
    join(folder, "vitest.config.ts"),
    `const projects = [${JSON.stringify(PROJECT)}];\nexport default { test: { projects } };\n`,
  );
});

afterAll(async () => {
  await rm(folder, { recursive: true, force: true });
});

/** Node running *args* in the planted folder with its coverage written to *raw*. */
const node = async (args: string[], raw: string): Promise<void> => {
  const env = { ...process.env, NODE_V8_COVERAGE: raw, NO_COLOR: "1" };
  await promisify(execFile)(process.execPath, args, { cwd: folder, env });
};

/** Each line's count, for the lines a statement starts on (the greatest, where two do). */
const lines = (data: FileCoverageData): Record<number, number> => {
  const counts: Record<number, number> = {};
  for (const [key, where] of Object.entries(data.statementMap)) {
    const { line } = (where as { start: { line: number } }).start;
    counts[line] = Math.max(counts[line] ?? 0, data.s[key] as number);
  }
  return counts;
};

/** Each named function's count. */
const functions = (data: FileCoverageData): Record<string, number> =>
  Object.fromEntries(
    Object.entries(data.fnMap).map(([key, fn]) => [
      (fn as { name: string }).name,
      data.f[key] as number,
    ]),
  );

test("a TypeScript file Node ran converts at its own positions, an uncalled function unrun", async () => {
  const raw = join(folder, "raw-typed");
  await node(["typed.ts"], raw);
  const path = join(folder, "typed.ts");
  const converted = (await toIstanbul(readRawReports(raw), [path], stripTypes))[path];
  assert.isDefined(converted);
  expect(lines(converted)).toEqual({ 1: 1, 3: 1, 6: 0, 8: 1 });
  expect(functions(converted)).toEqual({ used: 1, unused: 0 });
  expect(Object.values(converted.b)).toEqual([[1, 0]]);
});

/** The planted project run by Vitest natively, as `npm run test:native` runs, into *raw*. */
const runPlanted = async (raw: string): Promise<void> => {
  const pkg = JSON.parse(await readFile(join(EXTENSION, "package.json"), "utf8")) as {
    scripts: { "test:native": string };
  };
  const flags = pkg.scripts["test:native"].split(" ").slice(1);
  await node([VITEST, ...flags], raw);
};

/** The planted project's report from *raw*, written to *out*: its status and what it printed. */
const reportOf = async (raw: string, out: string): Promise<{ status: number; said: string[] }> => {
  const settings: Settings = {
    root: folder,
    configFile: join(folder, "vitest.config.ts"),
    projects: [PROJECT],
    defaultExclude: [],
    strip: stripTypes,
  };
  const said: string[] = [];
  const argv = ["--raw", raw, "--out", out, "--project", "planted"];
  const status = await report(
    argv,
    settings,
    (line) => said.push(line),
    (line) => said.push(line),
  );
  return { status, said };
};

test("a native Vitest run measures its test file, its setup file and its config", async () => {
  const raw = join(folder, "raw-run");
  const out = join(folder, "out");
  await runPlanted(raw);
  const { status, said } = await reportOf(raw, out);
  expect(status, said.join("\n")).toBe(0);
  const written = JSON.parse(await readFile(join(out, "coverage-final.json"), "utf8")) as Record<
    string,
    FileCoverageData
  >;
  const at = (name: string): FileCoverageData => {
    const found = written[join(folder, name)];
    assert.isDefined(found, name);
    return found;
  };
  expect(Object.keys(written).sort()).toEqual(
    ["flush.ts", "planted.test.ts", "vitest.config.ts"].map((name) => join(folder, name)),
  );
  // An import is no statement, and an arrow function has no name of its own (measured).
  expect(lines(at("planted.test.ts"))).toEqual({ 3: 1, 5: 1, 6: 1 });
  expect(functions(at("planted.test.ts"))).toEqual({ "(anonymous_0)": 1, "(anonymous_1)": 1 });
  expect(Object.values(at("planted.test.ts").b)).toEqual([[1, 0]]);
  expect(functions(at("flush.ts"))).toEqual({ "(anonymous_0)": 1 });
  expect(Object.values(at("flush.ts").s)).toEqual([1, 1]);
  expect(lines(at("vitest.config.ts"))).toEqual({ 1: 1 });
});

test("a file changed after the run is refused: it ran as other code than it now holds", async () => {
  const planted = join(folder, "planted.test.ts");
  const raw = join(folder, "raw-stale");
  await runPlanted(raw);
  await writeFile(planted, `${PLANTED}// changed since\n`);
  try {
    const { status, said } = await reportOf(raw, join(folder, "out-stale"));
    expect(status).toBe(1);
    expect(said.join("\n")).toContain(`${planted}: the code that ran is `);
  } finally {
    await writeFile(planted, PLANTED);
  }
});
