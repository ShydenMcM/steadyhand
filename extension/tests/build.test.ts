/**
 * The build's logic with the bundler stood in (#286): esbuild runs its own process, which a unit
 * test may not start, so here the bundler `build` is given is a stand-in that records what it was
 * asked (#394: no module mocks; the program passes esbuild's own `build`). The real build, and the
 * bundles it emits, are tested in `tests/integration/build.test.ts`.
 */
import { mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, expect, test } from "vitest";
import { build, ENTRY_POINTS, main, manifest } from "../build.ts";

let outdir = "";

beforeEach(async () => {
  outdir = await mkdtemp(join(tmpdir(), "steadyhand-build-unit-"));
});

afterEach(async () => {
  await rm(outdir, { recursive: true, force: true });
});

const ROOT = join(import.meta.dirname, "..");
const pkg = JSON.parse(await readFile(join(ROOT, "package.json"), "utf8")) as {
  version: string;
  description: string;
};

/** A bundler that records each call's options and resolves as esbuild does with no error. */
function recorder(): { asked: unknown[]; bundle: (options: unknown) => Promise<unknown> } {
  const asked: unknown[] = [];
  return {
    asked,
    bundle: (options) => {
      asked.push(options);
      return Promise.resolve({ errors: [], warnings: [] });
    },
  };
}

test("the entry points are the content script, the side panel and the service worker", () => {
  expect(ENTRY_POINTS).toEqual(["content-script", "side-panel", "service-worker"]);
});

test("the bundler is asked once for one self-contained browser script per entry point", async () => {
  const { asked, bundle } = recorder();
  await build(outdir, bundle);
  expect(asked).toEqual([
    {
      absWorkingDir: ROOT,
      entryPoints: [
        { in: "packages/shell/src/content-script.ts", out: "content-script" },
        { in: "packages/shell/src/side-panel.ts", out: "side-panel" },
        { in: "packages/shell/src/service-worker.ts", out: "service-worker" },
      ],
      outdir,
      bundle: true,
      format: "iife",
      platform: "browser",
      target: ["es2024", "chrome119"],
      charset: "utf8",
      legalComments: "none",
      logLevel: "warning",
    },
  ]);
});

test("the build empties its output folder first and writes the manifest beside the bundles", async () => {
  await writeFile(join(outdir, "stale.js"), "left over");
  await build(outdir, recorder().bundle);
  expect(await readdir(outdir)).toEqual(["manifest.json"]);
  expect(await readFile(join(outdir, "manifest.json"), "utf8")).toBe(
    `${JSON.stringify(manifest(pkg), null, 2)}\n`,
  );
});

test("a bundler failure fails the build and writes no manifest", async () => {
  const failing = () => Promise.reject(new Error("Build failed with 1 error"));
  await expect(build(outdir, failing)).rejects.toThrow("Build failed with 1 error");
  expect(await readdir(outdir)).toEqual([]);
});

test("the manifest is Manifest V3 at the given version, asking for no permission", () => {
  expect(manifest({ version: "1.2.3", description: "d" })).toEqual({
    manifest_version: 3,
    name: "steadyhand",
    version: "1.2.3",
    description: "d",
    minimum_chrome_version: "119",
    background: { service_worker: "service-worker.js" },
  });
});

test("run as a program, it builds into the folder it is given with the bundler it is given", async () => {
  const { asked, bundle } = recorder();
  await main(true, outdir, bundle);
  expect(asked.map((options) => (options as { outdir: string }).outdir)).toEqual([outdir]);
  expect(await readdir(outdir)).toEqual(["manifest.json"]);
});

test.each([false, undefined])("not run as a program (%s), it builds nothing", async (isProgram) => {
  const { asked, bundle } = recorder();
  await main(isProgram, outdir, bundle);
  expect(asked).toEqual([]);
  expect(await readdir(outdir)).toEqual([]);
});
