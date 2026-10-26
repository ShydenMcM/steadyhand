import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import * as esbuild from "esbuild";
import type { BuildOptions } from "esbuild";

const ROOT = import.meta.dirname;

/** The extension's entry points (spec §3): each becomes one self-contained bundle. */
export const ENTRY_POINTS = ["content-script", "side-panel", "service-worker"] as const;

/**
 * The oldest Chrome the extension runs on (#382). The code is compiled against the ES2024 library
 * (`tsconfig.json` `lib`), and Chrome 119 is the first with all of it: `Promise.withResolvers`
 * arrived in 119, `Object.groupBy` and `Map.groupBy` in 117 (MDN browser-compat-data, read
 * 2026-10-26). The extension calls no `chrome.*` API yet; the side panel (spec §10.1) needs 114.
 * Raise this when the code first uses something newer. esbuild checks the bundle's syntax
 * against the same Chrome.
 */
const MINIMUM_CHROME = "119";

interface PackageJson {
  version: string;
  description: string;
}

/**
 * The smallest manifest Chrome loads: no permission and no host access. EXT S14a adds the
 * content script, the side panel and their exact permissions (spec §10.1).
 */
export function manifest(pkg: PackageJson): Record<string, unknown> {
  return {
    manifest_version: 3,
    name: "steadyhand",
    version: pkg.version,
    description: pkg.description,
    minimum_chrome_version: MINIMUM_CHROME,
    background: { service_worker: "service-worker.js" },
  };
}

/** The bundler: esbuild's `build`, which the program passes in; a unit test passes a stand-in, as no
 * test mocks a module (#394). */
export type Bundle = (options: BuildOptions) => Promise<unknown>;

/** Builds the unpacked extension into `outdir` with `bundle`, emptying the folder first. */
export async function build(outdir: string, bundle: Bundle): Promise<void> {
  const pkg = JSON.parse(await readFile(join(ROOT, "package.json"), "utf8")) as PackageJson;
  await rm(outdir, { recursive: true, force: true });
  await mkdir(outdir, { recursive: true });
  await bundle({
    absWorkingDir: ROOT,
    entryPoints: ENTRY_POINTS.map((name) => ({
      in: `packages/shell/src/${name}.ts`,
      out: name,
    })),
    outdir,
    bundle: true,
    format: "iife",
    platform: "browser",
    target: ["es2024", `chrome${MINIMUM_CHROME}`],
    charset: "utf8",
    legalComments: "none",
    logLevel: "warning",
  });
  await writeFile(join(outdir, "manifest.json"), `${JSON.stringify(manifest(pkg), null, 2)}\n`);
}

/** Build into *outdir* with *bundle* when Node runs this file as its program (`npm run build`), and
 * do nothing when it is imported: a unit test runs both arms in-process (#374 AC6), so the program
 * passes esbuild's own `build` and a test a stand-in (#394). */
export async function main(
  isProgram: boolean | undefined,
  outdir: string,
  bundle: Bundle,
): Promise<void> {
  if (isProgram) {
    await build(outdir, bundle);
  }
}

await main(import.meta.main, join(ROOT, "dist"), esbuild.build);
