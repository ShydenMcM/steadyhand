/**
 * Node's own V8 coverage of the files Vitest's coverage cannot measure (#394): the test files, the
 * setup files and the Vitest config. Vitest's coverage leaves them out by a rule it hard-codes, so
 * a run that loads them natively (`npm run test:native`) writes Node's raw reports
 * (`NODE_V8_COVERAGE`), and this module turns those into the istanbul report the coverage gate
 * reads (`scripts/coverage_gate.py --istanbul`).
 *
 * Node strips a TypeScript file's types by blanking them, so every position in the code it ran is
 * the same position in the file, and it appends one `//# sourceURL=` line. The converter strips the
 * file the same way (amaro, the stripper Node bundles) and refuses any script whose length differs:
 * that script ran as other code than the file holds (rewritten by a loader, or changed since).
 */
import { globSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, matchesGlob } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { isDeepStrictEqual, parseArgs } from "node:util";
import { parse } from "acorn";
import { transformSync } from "amaro";
import convert from "ast-v8-to-istanbul";

/** A refusal: the raw reports cannot stand for the files they should measure. */
export class NodeCoverageError extends Error {
  override name = "NodeCoverageError";
}

/** One Vitest project's settings that name the files Vitest loads itself. */
export interface ProjectFiles {
  name: string;
  include: string[];
  exclude: string[];
  setupFiles: string[];
}

/** One block of a function in V8's coverage: its offsets in the code that ran, and its count. */
export interface CoverageRange {
  startOffset: number;
  endOffset: number;
  count: number;
}

/** One function's coverage, as V8 writes it. */
export interface FunctionCoverage {
  functionName: string;
  isBlockCoverage: boolean;
  ranges: CoverageRange[];
}

/** One script's coverage, as V8 writes it. */
export interface ScriptCoverage {
  url: string;
  functions: FunctionCoverage[];
}

/** One file's istanbul coverage, as `coverage-final.json` holds it. */
export interface FileCoverageData {
  path: string;
  statementMap: Record<string, unknown>;
  fnMap: Record<string, unknown>;
  branchMap: Record<string, unknown>;
  s: Record<string, number>;
  f: Record<string, number>;
  b: Record<string, number[]>;
}

/** A project entry of a Vitest config's `test.projects`, as far as this module reads it. */
interface ProjectEntry {
  test?: { name?: string; include?: string[]; exclude?: string[]; setupFiles?: string | string[] };
}

/** The project settings of the projects named, as a Vitest config's `test.projects` gives them: a
 * project naming no exclude takes Vitest's default (*defaultExclude*), as Vitest does. */
export function projectFiles(
  projects: readonly unknown[],
  names: readonly string[],
  defaultExclude: readonly string[],
): ProjectFiles[] {
  const entries = projects as readonly ProjectEntry[];
  return names.map((name) => {
    const test = entries.find((entry) => entry.test?.name === name)?.test;
    if (test === undefined) {
      throw new NodeCoverageError(`the config holds no project named ${name}`);
    }
    if (test.include === undefined) {
      throw new NodeCoverageError(`the config's project ${name} names no include`);
    }
    return {
      name,
      include: [...test.include],
      exclude: [...(test.exclude ?? defaultExclude)],
      setupFiles: [test.setupFiles ?? []].flat(),
    };
  });
}

/** The absolute paths Node's coverage must measure: every file the projects include and do not
 * exclude, every setup file they name, and the config file. Sorted, each once. */
export function measuredFiles(
  root: string,
  configFile: string,
  projects: readonly ProjectFiles[],
): string[] {
  const found = new Set([configFile]);
  for (const project of projects) {
    for (const path of globSync(project.include, { cwd: root })) {
      if (!project.exclude.some((pattern) => matchesGlob(path, pattern))) {
        found.add(join(root, path));
      }
    }
    for (const path of project.setupFiles) {
      found.add(join(root, path));
    }
  }
  return [...found].sort();
}

/** Every script of every raw report (`coverage-*.json`) in *folder*, the reports in name order. */
export function readRawReports(folder: string): ScriptCoverage[] {
  let names: string[];
  try {
    names = readdirSync(folder);
  } catch (error) {
    throw new NodeCoverageError(`cannot read ${folder}: ${String(error)}`);
  }
  const reports = names.filter((name) => /^coverage-.*\.json$/.test(name)).sort();
  if (reports.length === 0) {
    throw new NodeCoverageError(`${folder} holds no raw coverage report (coverage-*.json)`);
  }
  return reports.flatMap((name) => {
    const path = join(folder, name);
    let report: { result?: unknown };
    try {
      report = JSON.parse(readFileSync(path, "utf8")) as { result?: unknown };
    } catch (error) {
      throw new NodeCoverageError(`${path}: not a raw V8 coverage report: ${String(error)}`);
    }
    if (!Array.isArray(report.result)) {
      throw new NodeCoverageError(`${path}: not a raw V8 coverage report: it holds no result list`);
    }
    return report.result as ScriptCoverage[];
  });
}

/** The file a script ran from, its query left off; undefined for a script with no file. */
function fileOf(url: string): string | undefined {
  return url.startsWith("file:") ? fileURLToPath(url.replace(/\?.*$/, "")) : undefined;
}

/** One script's istanbul coverage of *path*, checked to be the file's own code. */
async function converted(path: string, run: ScriptCoverage): Promise<FileCoverageData> {
  const stripped = transformSync(readFileSync(path, "utf8"), { mode: "strip-only" }).code;
  const code = `${stripped}\n\n//# sourceURL=${run.url}`;
  const end = Math.max(...run.functions.flatMap((fn) => fn.ranges.map((range) => range.endOffset)));
  if (end !== code.length) {
    throw new NodeCoverageError(
      `${path}: the code that ran is ${String(end)} characters, the file stripped of its types ${String(code.length)}; it ran rewritten, or the file changed since`,
    );
  }
  const data = await convert({
    code,
    ast: parse(code, { ecmaVersion: "latest", sourceType: "module" }) as never,
    coverage: { url: pathToFileURL(path).href, functions: run.functions },
  });
  return Object.values(data)[0] as unknown as FileCoverageData;
}

/** *into* with *more*'s counts added. Two scripts of one file are the same code, so they convert
 * to the same maps, their counts listed in the same order; maps that differ are refused. */
export function summed(into: FileCoverageData, more: FileCoverageData): FileCoverageData {
  const maps = ({ statementMap, fnMap, branchMap }: FileCoverageData) => [
    statementMap,
    fnMap,
    branchMap,
  ];
  if (!isDeepStrictEqual(maps(into), maps(more))) {
    throw new NodeCoverageError(
      `${into.path}: two scripts of the file converted to different maps, so their counts cannot be summed`,
    );
  }
  const add = <T>(a: Record<string, T>, b: Record<string, T>, plus: (x: T, y: T) => T) => {
    const others = Object.values(b);
    return Object.fromEntries(
      Object.entries(a).map(([key, x], i) => [key, plus(x, others[i] as T)]),
    );
  };
  const counts = (x: number, y: number) => x + y;
  return {
    ...into,
    s: add(into.s, more.s, counts),
    f: add(into.f, more.f, counts),
    b: add(into.b, more.b, (x, y) => x.map((n, i) => n + (y[i] as number))),
  };
}

/** The istanbul coverage of *files* from the raw *scripts*, each file's scripts summed. Scripts of
 * other files are left out, unless Vitest loaded one as a test or setup file (`vitest=` in its
 * query): then the files measured missed it, and it is refused. */
export async function toIstanbul(
  scripts: readonly ScriptCoverage[],
  files: readonly string[],
): Promise<Record<string, FileCoverageData>> {
  const wanted = new Set(files);
  const runs = new Map<string, ScriptCoverage[]>();
  for (const run of scripts) {
    const path = fileOf(run.url);
    if (path === undefined) {
      continue;
    }
    if (!wanted.has(path)) {
      if (/[?&]vitest=/.test(run.url)) {
        throw new NodeCoverageError(
          `${path}: Vitest loaded it as a test or setup file, but the config's settings do not name it`,
        );
      }
      continue;
    }
    runs.set(path, [...(runs.get(path) ?? []), run]);
  }
  const report: Record<string, FileCoverageData> = {};
  for (const path of files) {
    const held = runs.get(path);
    if (held === undefined) {
      throw new NodeCoverageError(`${path}: no raw report holds it, so the run never loaded it`);
    }
    const each = await Promise.all(held.map((run) => converted(path, run)));
    report[path] = each.reduce(summed);
  }
  return report;
}

/** Where the files measured are found: the extension, its config and the config's projects. */
export interface Settings {
  root: string;
  configFile: string;
  projects: readonly unknown[];
  defaultExclude: readonly string[];
}

/** `tests/node-coverage-report.ts`'s work: its exit status. Every refusal is printed, and the status is 1. */
export async function report(
  argv: string[],
  settings: Settings,
  log: (line: string) => void,
  error: (line: string) => void,
): Promise<number> {
  try {
    const { values } = parseArgs({
      args: argv,
      options: {
        raw: { type: "string" },
        out: { type: "string" },
        project: { type: "string", multiple: true },
      },
    });
    const { raw, out, project } = values;
    if (raw === undefined || out === undefined || project === undefined) {
      throw new Error(
        "usage: node-coverage-report.ts --raw <folder> --out <folder> --project <name>...",
      );
    }
    const projects = projectFiles(settings.projects, project, settings.defaultExclude);
    const files = measuredFiles(settings.root, settings.configFile, projects);
    const measured = await toIstanbul(readRawReports(raw), files);
    mkdirSync(out, { recursive: true });
    writeFileSync(join(out, "coverage-final.json"), `${JSON.stringify(measured)}\n`);
    for (const [path, coverage] of Object.entries(measured)) {
      const statements = Object.values(coverage.s);
      const run = statements.filter((count) => count > 0).length;
      log(
        `${path.slice(settings.root.length + 1)}: ${String(run)} of ${String(statements.length)} statements run`,
      );
    }
    log(`${String(files.length)} files measured by Node's own coverage, written to ${out}`);
    return 0;
  } catch (failure) {
    error(`node coverage: ${(failure as Error).message}`);
    return 1;
  }
}
