/**
 * The build's logic with the bundler stood in (#286): esbuild runs its own process, which a unit
 * test may not start, so here its `build` is a mock that records what it was asked. The real build,
 * and the bundles it emits, are tested in `tests/integration/build.test.ts`.
 */
import { mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

const bundled = vi.hoisted(() => vi.fn<(options: unknown) => Promise<unknown>>());
vi.mock("esbuild", () => ({ build: bundled }));

const { build, ENTRY_POINTS, manifest } = await import("../build.ts");

let outdir = "";

beforeEach(async () => {
  outdir = await mkdtemp(join(tmpdir(), "steadyhand-build-unit-"));
  bundled.mockReset();
  bundled.mockResolvedValue({ errors: [], warnings: [] });
});

afterEach(async () => {
  await rm(outdir, { recursive: true, force: true });
});

const ROOT = join(import.meta.dirname, "..");
const pkg = JSON.parse(await readFile(join(ROOT, "package.json"), "utf8")) as {
  version: string;
  description: string;
};

test("the entry points are the content script, the side panel and the service worker", () => {
  expect(ENTRY_POINTS).toEqual(["content-script", "side-panel", "service-worker"]);
});

test("esbuild is asked once for one self-contained browser script per entry point", async () => {
  await build(outdir);
  expect(bundled.mock.calls).toEqual([
    [
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
        target: "es2024",
        charset: "utf8",
        legalComments: "none",
        logLevel: "warning",
      },
    ],
  ]);
});

test("the build empties its output folder first and writes the manifest beside the bundles", async () => {
  await writeFile(join(outdir, "stale.js"), "left over");
  await build(outdir);
  expect(await readdir(outdir)).toEqual(["manifest.json"]);
  expect(await readFile(join(outdir, "manifest.json"), "utf8")).toBe(
    `${JSON.stringify(manifest(pkg), null, 2)}\n`,
  );
});

test("a bundler failure fails the build and writes no manifest", async () => {
  bundled.mockRejectedValue(new Error("Build failed with 1 error"));
  await expect(build(outdir)).rejects.toThrow("Build failed with 1 error");
  expect(await readdir(outdir)).toEqual([]);
});

test("the manifest is Manifest V3 at the given version, asking for no permission", () => {
  expect(manifest({ version: "1.2.3", description: "d" })).toEqual({
    manifest_version: 3,
    name: "steadyhand",
    version: "1.2.3",
    description: "d",
    background: { service_worker: "service-worker.js" },
  });
});
