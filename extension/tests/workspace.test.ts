import { readFileSync } from "node:fs";
import { join } from "node:path";
import tseslint from "typescript-eslint";
import { expect, test } from "vitest";
import eslint from "../eslint.config.js";
import vitest from "../vitest.config.ts";

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

test("Node 24 or later is required, and npm refuses to install on anything older", () => {
  expect(manifest("package.json").engines).toEqual({ node: ">=24" });
  expect(read(".npmrc").split("\n")).toContain("engine-strict=true");
});

test.each(Object.entries(LAYERS))("%s is built on %j and on no other package", (name, below) => {
  const deps = Object.keys(manifest(`packages/${name}/package.json`).dependencies ?? {});
  expect(deps.filter((dep) => dep.startsWith("@steadyhand/")).sort()).toEqual(
    below.map((layer) => `@steadyhand/${layer}`),
  );
});

test("core's only runtime dependency is decimal.js", () => {
  expect(Object.keys(manifest("packages/core/package.json").dependencies ?? {})).toEqual([
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
  // Measured on 2026-10-06 (#220): 198 packages fetched, every platform's binaries included.
  // Lower it only by a deliberate edit when the dependencies shrink.
  expect(fetched.length).toBeGreaterThanOrEqual(197);
  const loose = fetched.filter(
    ([, entry]) =>
      !entry.resolved?.startsWith("https://registry.npmjs.org/") ||
      !entry.integrity?.startsWith("sha512-"),
  );
  expect(loose.map(([path]) => path)).toEqual([]);
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

test("ESLint applies every rule set of typescript-eslint's strict, type-checked config", () => {
  const strict = tseslint.configs.strictTypeChecked;
  expect(strict.length).toBeGreaterThan(0);
  expect(strict.filter((config) => !eslint.includes(config))).toEqual([]);
});

test("Vitest fails below 100% coverage on every measure", () => {
  expect(vitest.test?.coverage).toMatchObject({
    provider: "v8",
    thresholds: { branches: 100, functions: 100, lines: 100, statements: 100 },
  });
});
