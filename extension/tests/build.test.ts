import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, expect, test } from "vitest";
import { build, ENTRY_POINTS } from "../build.ts";

let outdir = "";
let built: Promise<void> | undefined;

beforeAll(async () => {
  outdir = await mkdtemp(join(tmpdir(), "steadyhand-build-"));
});

afterAll(async () => {
  await rm(outdir, { recursive: true, force: true });
});

/** The build, run once on first use, so a failing build fails each test that reads it by name. */
const output = async (): Promise<string> => {
  built ??= build(outdir);
  await built;
  return outdir;
};

const bundle = async (name: string): Promise<string> =>
  readFile(join(await output(), `${name}.js`), "utf8");

test("the build emits one bundle per entry point and the manifest, nothing else", async () => {
  expect((await readdir(await output())).sort()).toEqual([
    "content-script.js",
    "manifest.json",
    "service-worker.js",
    "side-panel.js",
  ]);
});

test.each(ENTRY_POINTS)("%s is one self-contained script, no module syntax left", async (name) => {
  const text = await bundle(name);
  expect(text.startsWith('"use strict";\n(() => {\n')).toBe(true);
  expect(text).not.toMatch(/^\s*(?:import|export)\b/m);
  // An external package left behind as a call Chrome cannot resolve.
  expect(text).not.toContain("require(");
});

test.each(["@steadyhand/core", "@steadyhand/readers", "@steadyhand/history"])(
  "the side panel bundle carries %s, which it imports through the workspace",
  async (name) => {
    expect(await bundle("side-panel")).toContain(`"${name}"`);
  },
);

test("the manifest is Manifest V3 at the workspace's version, asking for no permission", async () => {
  const pkg = JSON.parse(
    await readFile(join(import.meta.dirname, "..", "package.json"), "utf8"),
  ) as {
    version: string;
  };
  expect(JSON.parse(await readFile(join(await output(), "manifest.json"), "utf8"))).toEqual({
    manifest_version: 3,
    name: "steadyhand",
    version: pkg.version,
    description: "What the strategy you chose implies, read from what your broker's page shows.",
    background: { service_worker: "service-worker.js" },
  });
});
