import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, expect, test } from "vitest";
import * as esbuild from "esbuild";
import { build, ENTRY_POINTS } from "../../build.ts";

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
  built ??= build(outdir, esbuild.build);
  await built;
  return outdir;
};

const bundle = async (name: string): Promise<string> =>
  readFile(join(await output(), `${name}.js`), "utf8");

test("the build emits each entry point's bundle, the manifest and the panel page, no more", async () => {
  expect((await readdir(await output())).sort()).toEqual([
    "content-script.js",
    "manifest.json",
    "service-worker.js",
    "side-panel.html",
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

// esbuild heads each module it bundles with a comment naming its path, so a workspace package the
// panel imports but the bundle left out (a bare import Chrome cannot load) has no such line.
test.each(["core", "readers", "history"])(
  "the side panel bundle carries @steadyhand/%s's code, which it imports through the workspace",
  async (name) => {
    expect(await bundle("side-panel")).toMatch(new RegExp(`^ {2}// packages/${name}/src/`, "m"));
  },
);

test("the built manifest has exactly spec §10.1's permissions, host matches and policy", async () => {
  const pkg = JSON.parse(
    await readFile(join(import.meta.dirname, "..", "..", "package.json"), "utf8"),
  ) as {
    version: string;
  };
  expect(JSON.parse(await readFile(join(await output(), "manifest.json"), "utf8"))).toEqual({
    manifest_version: 3,
    name: "steadyhand",
    version: pkg.version,
    description: "What the strategy you chose implies, read from what your broker's page shows.",
    minimum_chrome_version: "119",
    permissions: ["sidePanel", "storage"],
    background: { service_worker: "service-worker.js" },
    action: { default_title: "steadyhand" },
    side_panel: { default_path: "side-panel.html" },
    content_scripts: [
      {
        matches: ["https://broker.steadyhand.test/*"],
        js: ["content-script.js"],
        run_at: "document_idle",
      },
    ],
    content_security_policy: {
      extension_pages:
        "script-src 'self'; object-src 'none'; connect-src 'none'; base-uri 'none'; " +
        "form-action 'none'; frame-ancestors 'none'",
    },
  });
});
