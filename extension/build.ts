import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import * as esbuild from "esbuild";

const ROOT = import.meta.dirname;

/** The extension's entry points (spec §3): each becomes one self-contained bundle. */
export const ENTRY_POINTS = ["content-script", "side-panel", "service-worker"] as const;

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
    background: { service_worker: "service-worker.js" },
  };
}

/** Builds the unpacked extension into `outdir`, emptying it first. */
export async function build(outdir: string): Promise<void> {
  const pkg = JSON.parse(await readFile(join(ROOT, "package.json"), "utf8")) as PackageJson;
  await rm(outdir, { recursive: true, force: true });
  await mkdir(outdir, { recursive: true });
  await esbuild.build({
    absWorkingDir: ROOT,
    entryPoints: ENTRY_POINTS.map((name) => ({
      in: `packages/shell/src/${name}.ts`,
      out: name,
    })),
    outdir,
    bundle: true,
    format: "iife",
    platform: "browser",
    target: "es2024",
    charset: "utf8",
    legalComments: "none",
    logLevel: "warning",
  });
  await writeFile(join(outdir, "manifest.json"), `${JSON.stringify(manifest(pkg), null, 2)}\n`);
}

if (import.meta.main) {
  await build(join(ROOT, "dist"));
}
