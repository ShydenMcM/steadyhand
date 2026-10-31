import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "vitest";

const ROOT = join(import.meta.dirname, "..");

interface Manifest {
  name: string;
  engines?: Record<string, string>;
  workspaces?: string[];
  dependencies?: Record<string, string>;
  devDependencies?: Record<string, string>;
}

const read = (path: string): string => readFileSync(join(ROOT, path), "utf8");
const manifest = (path: string): Manifest => JSON.parse(read(path)) as Manifest;

/** Spec §3: the workspace's packages and the ones each is built on (shell, then readers and
 * history, then core). */
const LAYERS: Record<string, string[]> = {
  core: [],
  readers: ["core"],
  history: ["core"],
  shell: ["history", "readers"],
};
const MANIFESTS = ["package.json", ...Object.keys(LAYERS).map((p) => `packages/${p}/package.json`)];
const EXACT = /^\d+\.\d+\.\d+$/;

test("the workspace holds exactly the four packages of spec §3", () => {
  expect(manifest("package.json").workspaces).toEqual(
    Object.keys(LAYERS).map((name) => `packages/${name}`),
  );
});

// Node 26.3 or later (Shyden, 2026-10-08, every project, #287); 26.0 to 26.2 are left out, as
// eslint-plugin-astro's range leaves them out. 24.16 stays because Dependabot's npm updater installs
// on Node 24 (dependabot-core npm_and_yarn/Dockerfile, `ARG NODEJS_VERSION=24`, read 2026-10-08),
// and engine-strict would refuse its installs. The 24 half goes when Dependabot moves.
const ENGINES = { node: "^24.16.0 || >=26.3.0" };

test("Node 26.3 or later is required, or 24.16 for Dependabot, and npm refuses anything else", () => {
  expect(manifest("package.json").engines).toEqual(ENGINES);
  expect(read(".npmrc").split("\n")).toContain("engine-strict=true");
});

test("the lock records the manifest's engines range", () => {
  const lock = JSON.parse(read("package-lock.json")) as { packages: Record<string, Manifest> };
  expect(lock.packages[""]?.engines).toEqual(ENGINES);
});

test.each(Object.entries(LAYERS))("%s is built on %j and on no other package", (name, below) => {
  const deps = Object.keys(manifest(`packages/${name}/package.json`).dependencies as object);
  expect(deps.filter((dep) => dep.startsWith("@steadyhand/")).sort()).toEqual(
    below.map((layer) => `@steadyhand/${layer}`),
  );
});

test("core's only runtime dependency is decimal.js", () => {
  expect(Object.keys(manifest("packages/core/package.json").dependencies as object)).toEqual([
    "decimal.js",
  ]);
});

test.each(MANIFESTS)("%s pins every dependency to one exact version", (path) => {
  const { dependencies = {}, devDependencies = {} } = manifest(path);
  const specs = Object.entries({ ...dependencies, ...devDependencies });
  expect(specs.length).toBeGreaterThan(0);
  expect(specs.filter(([, spec]) => !EXACT.test(spec))).toEqual([]);
});

test("every locked package comes from the npm registry with a sha512 integrity", () => {
  const lock = JSON.parse(read("package-lock.json")) as {
    packages: Record<string, { link?: boolean; resolved?: string; integrity?: string }>;
  };
  const fetched = Object.entries(lock.packages).filter(
    ([path, entry]) => path.startsWith("node_modules/") && !entry.link,
  );
  const loose = fetched.filter(
    ([, entry]) =>
      !entry.resolved?.startsWith("https://registry.npmjs.org/") ||
      !entry.integrity?.startsWith("sha512-"),
  );
  expect(loose).toEqual([]);
});

test("TypeScript runs strict, with checked indexes and exact optional properties", () => {
  const { compilerOptions } = JSON.parse(read("tsconfig.json")) as {
    compilerOptions: Record<string, unknown>;
  };
  expect(compilerOptions).toMatchObject({
    strict: true,
    noUncheckedIndexedAccess: true,
    exactOptionalPropertyTypes: true,
    noEmit: true,
  });
});
