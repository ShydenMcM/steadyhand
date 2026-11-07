import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, expect, test } from "vitest";
import * as esbuild from "esbuild";
import { build, ENTRY_POINTS } from "../../build.ts";
import { adviceWords, scan, webScripts } from "../lib/bundle-scan.ts";

// The scan of the real build (#240 AC1-AC4, spec §11, §12.3). Each forbidden form, planted, is
// found by the unit suite (tests/bundle-scan.test.ts); here every bundle the build ships, and the
// panel page, are held to it. The lessons ship inside the panel's bundle, so its wording check
// is theirs too.

let outdir = "";
let built: Promise<void> | undefined;

beforeAll(async () => {
  outdir = await mkdtemp(join(tmpdir(), "steadyhand-scan-"));
});

afterAll(async () => {
  await rm(outdir, { recursive: true, force: true });
});

/** A file the build wrote; the build runs once, on first use. */
const shipped = async (name: string): Promise<string> => {
  built ??= build(outdir, esbuild.build);
  await built;
  return readFile(join(outdir, name), "utf8");
};

test.each(ENTRY_POINTS)("%s reaches no network and runs no code made from text", async (name) => {
  const verdict = scan(await shipped(`${name}.js`), name === "content-script");
  expect(verdict.found).toEqual([]);
  expect(verdict.judged).toBeGreaterThan(0);
});

test.each(ENTRY_POINTS)("%s holds no advice words", async (name) => {
  expect(adviceWords(await shipped(`${name}.js`))).toEqual([]);
});

test("the panel page loads no script from the web and holds no advice words", async () => {
  const page = await shipped("side-panel.html");
  expect(webScripts(page)).toEqual([]);
  expect(adviceWords(page)).toEqual([]);
});
