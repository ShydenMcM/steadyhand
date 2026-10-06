# EXT S2 #220 The TypeScript Workspace, Its CI Job And Develop's Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up `extension/`, the TypeScript npm workspace the broker-view extension is built in, with its checks (strict TypeScript, ESLint's strict type-checked rules, Prettier, Vitest at 100% coverage, Playwright with no retries, esbuild with one bundle per entry point) run by a new `extension` CI job; make develop's deploy the extension zip, its build provenance attested and verified on the run that made it; retire the TestPyPI `publish-dev` job and the daily `yahoo-shape` schedule.

**Architecture:** Four packages under `extension/packages/` (`core`, `readers`, `history`, `shell`) depend one way only, as `package.json` declares and a test checks: shell on readers and history, both on core, core on `decimal.js` alone. Until their stories, each package names itself and the packages it is built on, so the workspace links, the type checker, the bundler and the coverage gate all have real code to judge. `extension/build.ts` bundles the shell's three entry points with esbuild, each one self-contained, and writes a manifest asking for no permission (EXT S14a adds the content script, the side panel and their exact permissions). The `extension` job carries the docs-only scope and lock steps like every gated job (Task 2). Dependabot covers the workspace and moves packages that pin each other in one group (Task 3). `deploy-dev` replaces `publish-dev`: after every gated job on a push to `develop`, it builds the zip from a clean install, attests it with `actions/attest`, verifies the attestation with `gh attestation verify` and checks the verdict names the zip's own digest, then keeps the zip as the run's artifact (Task 4).

**Tech Stack:** Node ≥ 24 (CI and this machine: 24.21.0, npm 11.19.0), TypeScript 6.0.3, ESLint 10.12.0 with typescript-eslint 8.71.1, Prettier 3.9.9, Vitest 5.0.3 with `@vitest/coverage-v8` 5.0.3 and Vite 8.3.3, `@playwright/test` 1.63.0, esbuild 0.28.2, `decimal.js` 10.6.0, `@types/node` 24.19.1; GitHub Actions `actions/setup-node` v7.0.0, `actions/attest` v4.2.2, `actions/upload-artifact` v7.0.1. Python 3.12 and 3.13 for the existing gates and the workflow guards.

**Spec:** `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md` §3 and §12.1, decision 21 (`yahoo-shape.yml` disabled), and the story #220 with #264's note on it (Prettier and any tool walking the tree must not read the fast-path files). Builds on `docs/superpowers/plans/2026-10-06-ext-s1-ci-fast-path.md` and `2026-10-06-ext-s1b-lock-fast-path.md`. Every code block below was generated from a commit that passed the whole gate, not typed.

## Global Constraints

- Node ≥ 24, refused below by `engine-strict`; every dependency pinned to one exact version; `core`'s only runtime dependency is `decimal.js` (spec §3).
- TypeScript `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`; `tsc --noEmit` in CI, because esbuild strips types without checking them (spec §3).
- 100% coverage on every measure for `core`, `readers` and `history`; one test per case (`test.each`, never a population looped inside one test); no retries anywhere: Playwright's `retries` is 0 and a test asserts it (spec §14.1).
- No install script runs: every `npm ci` is `--ignore-scripts`.
- Every `uses:` pinned to a full SHA with its `# vX.Y.Z` comment; Dependabot targets `develop` for every ecosystem (the supply-chain rules).
- Every gated job checks out two commits, runs the scope step second and the lock third, and skips every later step on a docs-only verdict; deploy jobs always run in full (#218, #264).

## Decisions taken in this plan

Each was settled from a primary source, not assumed; none changes what the story delivers.

1. **TypeScript 6.0.3, not 7.0.2.** typescript-eslint 8.71.1, which the strict type-checked rules need, declares `typescript >=4.8.4 <6.1.0` (read from npm on 2026-10-06). TypeScript 7 is the native port, and its peer range excludes it. A Dependabot PR moving TypeScript past 6.0 will fail `npm ci` on that PR until typescript-eslint supports it.
2. **`actions/attest`, not `actions/attest-build-provenance`.** AC6 names the latter; its README says that from v4 it "is simply a wrapper on top of `actions/attest`" and that new implementations should use `actions/attest`. With no predicate given, `actions/attest` makes the same SLSA build provenance. Its storage records apply only with `push-to-registry`, so the job needs `id-token: write`, `attestations: write` and `contents: read`, nothing more (read from the pinned `action.yml`).
3. **`yahoo-shape.yml` keeps `workflow_dispatch` and loses its schedule.** "Disabled" (decision 21) is read as "never runs on its own"; the Python packages keep their Yahoo layer (spec §15), and this keeps their live check runnable by hand. A test pins the triggers.
4. **The S2 zip's manifest asks for no permission.** The content script and the side panel are bundled but not declared; EXT S14a declares them with the exact permissions of spec §10.1.
5. **`vite` is a direct, pinned devDependency.** Vitest 5.0.3 declares it a required peer.
6. **The environment `dev`.** `deploy-dev` names it, which GitHub creates on the first run. It holds no secret and can reach no production system, so it needs no reviewer; the fast-path guard tells deploy jobs from gated ones by their `environment`.

## Review Focus

1. **A docs-only PR.** The `extension` job must still report success, with every step after the lock skipped. Pinned by `test_a_gated_job_reports_and_skips_every_later_step[extension]`, derived from the workflow (mutations W5, W6).
2. **A package declaring a dependency upward** (core on history). Pinned by `core is built on [] and on no other package` (mutation T19), which passes on any manifest with no dependency, so its red-phase pass is expected and the mutation is its proof.
3. **`npm install x` writing a range.** `.npmrc` sets `save-exact`, and `pins every dependency to one exact version` refuses a range in any of the five manifests (mutation T9).
4. **A bundle that leaves a workspace import unresolved.** Chrome cannot load a bare import or a `require(`. Pinned by the three `is one self-contained script` cases and the side panel's `carries @steadyhand/…` cases (mutations T15, T17).
5. **An attestation checked against the wrong ref or file.** Measured on the real runner before the PR (throwaway run 37470529900, on a scratch branch with a copy of `deploy-dev`): the verify passed and printed `verified: steadyhand-extension-<sha>.zip sha256:d2037a07…`; the same verify with `--source-ref refs/heads/develop` was refused (`expected SourceRepositoryRef to be refs/heads/develop, got refs/heads/scratch/220-deploy-probe`); and the digest check refused another file's digest. In the repository, `test_the_zip_is_attested_then_verified_as_this_workflow_on_develop` pins the command word by word (mutation W12).

## The gate

Each task ends green on CI's exact gate, run on its commit: `uv run --locked ruff check`, `ruff format --check`, `mypy`, `pytest -W error --cov` on Python 3.12 and 3.13, the `-m perf` step, and, from Task 2, inside `extension/`: `npm ci --ignore-scripts`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`, `npm run build`. Measured results:

- **Task 1:** extension: none
- **Task 1:** 2833cbb274d1fd6704e6fe655682cda3d66eb8cb ruff=0 format=0 mypy=0 pytest=0 perf=0 py313=0 :: 2355 passed, 29 deselected in 685.67s (0:11:25)  · coverage 100% · perf 12 passed, 2372 deselected in 42.55s  · py313 2355 passed, 29 deselected in 547.41s (0:09:07) 
- **Task 2:** extension: --ignore-scripts=0 lint=0 format:check=0 typecheck=0 test=0 build=0 :: 30 passed (30) · branches 100%
- **Task 2:** 6d6eaf53eb503cbee70fb7549608e9be19e9aefb ruff=0 format=0 mypy=0 pytest=0 perf=0 py313=0 :: 2370 passed, 29 deselected in 300.56s (0:05:00)  · coverage 100% · perf 12 passed, 2387 deselected in 19.71s  · py313 2370 passed, 29 deselected in 169.17s (0:02:49) 
- **Task 3:** extension: --ignore-scripts=0 lint=0 format:check=0 typecheck=0 test=0 build=0 :: 30 passed (30) · branches 100%
- **Task 3:** fc4297bfc3309a8efb94d0d7fd43cd4ae734fbbe ruff=0 format=0 mypy=0 pytest=0 perf=0 py313=0 :: 2375 passed, 29 deselected in 182.63s (0:03:02)  · coverage 100% · perf 12 passed, 2392 deselected in 15.99s  · py313 2375 passed, 29 deselected in 155.99s (0:02:35) 
- **Task 4:** extension: --ignore-scripts=0 lint=0 format:check=0 typecheck=0 test=0 build=0 :: 30 passed (30) · branches 100%
- **Task 4:** 7e9c52759de61b11e08a76bbf8227a6f017bb169 ruff=0 format=0 mypy=0 pytest=0 perf=0 py313=0 :: 2371 passed, 29 deselected in 161.51s (0:02:41)  · coverage 100% · perf 12 passed, 2388 deselected in 17.20s  · py313 2371 passed, 29 deselected in 148.76s (0:02:28) 

## The red phase

Each task writes its tests first, then the rest of its files in their **red form**: configuration and scaffolding as they stand before the task's work (no strict flags, no coverage thresholds, loose version ranges, empty dependency lists, `build()` throwing `not implemented`, the workflow as it was). Every new test is then run and must fail on its own assertion or on the stub's `not implemented`, never on an import or a missing name. A test that passes in red is named with the mutation that proves it. The replay checks that the tests plus the red form equal the tree the red phase was measured on, byte for byte (`<!-- check: red -->`), and that the implementation then equals the story commit (`<!-- check: gate -->`).

---

### Task 1: A one-path docs-only verdict says "1 path"

**Acceptance criteria (story text):** none directly; the handover's known wording defect, fixed in #220's first commit (`ci_scope.verdict_for` printed `1 paths`).

**Files:**
- Modify: `scripts/ci_scope.py` (`verdict_for`)
- Test: `tests/scripts/test_ci_scope.py`

**Interfaces:**
- Consumes: `ci_scope.verdict_for(found: list[Change]) -> Verdict`, unchanged.
- Produces: the same, with `reason` reading `docs-only: 1 path, …` for one path.

- [ ] **Step 1: Branch.** `git switch -c ext/s2-workspace origin/develop`
- [ ] **Step 2: Write the failing test.**

**`tests/scripts/test_ci_scope.py`** (changed: 1 edit)

<!-- edit: tests/scripts/test_ci_scope.py -->
Replace:
```python

def test_a_docs_only_verdict_counts_its_paths() -> None:
    verdict = verdict_for(edits("HANDOVER.md", "docs/superpowers/specs/s.md"))
    assert verdict == Verdict(True, "docs-only: 2 paths, all on the fast path")

```
with:
```python

@pytest.mark.parametrize(
    ("paths", "reason"),
    [
        pytest.param(("HANDOVER.md",), "docs-only: 1 path, all on the fast path", id="one"),
        pytest.param(
            ("HANDOVER.md", "docs/superpowers/specs/s.md"),
            "docs-only: 2 paths, all on the fast path",
            id="two",
        ),
    ],
)
def test_a_docs_only_verdict_counts_its_paths(paths: tuple[str, ...], reason: str) -> None:
    assert verdict_for(edits(*paths)) == Verdict(True, reason)

```


- [ ] **Step 3: The red form** (nothing to write: the code is unchanged until Step 5).



- [ ] **Step 4: Watch it fail.** `uv run pytest -p no:cacheprovider tests/scripts/test_ci_scope.py -k counts_its_paths`. Measured: 1 of 1 new case fails on its assertion, `'docs-only: 1 paths, all on the fast path' != 'docs-only: 1 path, all on the fast path'`; the existing two-path case passes.

<!-- check: red -->

- [ ] **Step 5: Implement.**

**`scripts/ci_scope.py`** (changed: 1 edit)

<!-- edit: scripts/ci_scope.py -->
Replace:
```python
            return Verdict(docs_only=False, reason=reason)
    return Verdict(docs_only=True, reason=f"docs-only: {len(found)} paths, all on the fast path")

```
with:
```python
            return Verdict(docs_only=False, reason=reason)
    paths = "1 path" if len(found) == 1 else f"{len(found)} paths"
    return Verdict(docs_only=True, reason=f"docs-only: {paths}, all on the fast path")

```


- [ ] **Step 6: Run the gate** (as **The gate** says).

<!-- check: gate -->

- [ ] **Step 7: Mutation W16** from **Mutation checks**.
- [ ] **Step 8: Commit** `fix(ci): #220 a one-path docs-only verdict says "1 path" (Refs #220)`.

### Task 2: The TypeScript workspace, its toolchain and the extension CI job

**Acceptance criteria (story text):** AC1 (workspace, engines, exact pins, core's one dependency), AC2 (strict TypeScript, ESLint strict type-checked, Prettier, `tsc --noEmit` in CI, each shown red by a planted violation), AC3 (100% coverage, Playwright `retries: 0` asserted, one bundle per entry point), AC4 (the `extension` job), AC8 (the fast path covers it).

**Files:**
- Create: `extension/` (`package.json`, `package-lock.json`, `.npmrc`, `.prettierrc.json`, `.prettierignore`, `tsconfig.json`, `eslint.config.js`, `vitest.config.ts`, `playwright.config.ts`, `build.ts`, `packages/{core,readers,history,shell}/package.json` and `src/`, `packages/{core,readers,history}/test/`, `tests/`)
- Create: `tests/meta/test_extension_ci.py`
- Modify: `.github/workflows/ci.yml` (the `extension` job), `.gitignore` (`node_modules/`, `coverage/`), `tests/meta/test_ci_fast_path.py` (the floors, measured: 5 gated jobs, 31 later steps)

**Interfaces:**
- Produces: `@steadyhand/core` (`PACKAGE`), `@steadyhand/readers` and `@steadyhand/history` (`PACKAGE`, `BUILT_ON: readonly string[]`), each exported from `src/index.ts`; `extension/build.ts`: `ENTRY_POINTS`, `manifest(pkg) -> Record<string, unknown>`, `build(outdir: string): Promise<void>`; `npm run lint | format:check | typecheck | test | build` inside `extension/`; the `extension` job in `ci.yml`.

- [ ] **Step 1: Write the failing tests.**

**`extension/packages/core/test/index.test.ts`** (new)

<!-- file: extension/packages/core/test/index.test.ts -->
```typescript
import { expect, test } from "vitest";
import { PACKAGE } from "../src/index.ts";

test("core names itself", () => {
  expect(PACKAGE).toBe("@steadyhand/core");
});
```

**`extension/packages/history/test/index.test.ts`** (new)

<!-- file: extension/packages/history/test/index.test.ts -->
```typescript
import { PACKAGE as CORE } from "@steadyhand/core";
import { expect, test } from "vitest";
import { BUILT_ON, PACKAGE } from "../src/index.ts";

test("history names itself", () => {
  expect(PACKAGE).toBe("@steadyhand/history");
});

test("history is built on core alone, reached through the workspace", () => {
  expect(BUILT_ON).toEqual([CORE]);
  expect(CORE).toBe("@steadyhand/core");
});
```

**`extension/packages/readers/test/index.test.ts`** (new)

<!-- file: extension/packages/readers/test/index.test.ts -->
```typescript
import { PACKAGE as CORE } from "@steadyhand/core";
import { expect, test } from "vitest";
import { BUILT_ON, PACKAGE } from "../src/index.ts";

test("readers names itself", () => {
  expect(PACKAGE).toBe("@steadyhand/readers");
});

test("readers is built on core alone, reached through the workspace", () => {
  expect(BUILT_ON).toEqual([CORE]);
  expect(CORE).toBe("@steadyhand/core");
});
```

**`extension/tests/build.test.ts`** (new)

<!-- file: extension/tests/build.test.ts -->
```typescript
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
```

**`extension/tests/toolchain.test.ts`** (new)

<!-- file: extension/tests/toolchain.test.ts -->
```typescript
import { expect, test } from "vitest";
import playwright from "../playwright.config.ts";

test("Playwright never retries a failed test", () => {
  expect(playwright.retries).toBe(0);
});
```

**`extension/tests/workspace.test.ts`** (new)

<!-- file: extension/tests/workspace.test.ts -->
```typescript
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
```

**`tests/meta/test_ci_fast_path.py`** (changed: 2 edits)

<!-- edit: tests/meta/test_ci_fast_path.py -->
Replace:
```python
}
# Measured on 2026-10-06 (#218, #264): 4 gated jobs whose later steps number 23, the lock included.
# Lower each only by a deliberate edit when the workflow shrinks.
GATED_FLOOR = 3
SKIPPED_STEPS_FLOOR = 22

```
with:
```python
}
# Measured on 2026-10-06 (#220): 5 gated jobs whose later steps number 31, the lock included.
# Lower each only by a deliberate edit when the workflow shrinks.
GATED_FLOOR = 4
SKIPPED_STEPS_FLOOR = 30

```

<!-- edit: tests/meta/test_ci_fast_path.py -->
Replace:
```python
    assert "lint" in GATED
    assert "publish-dev" in DEPLOYS
```
with:
```python
    assert "lint" in GATED
    assert "extension" in GATED
    assert "publish-dev" in DEPLOYS
```

**`tests/meta/test_extension_ci.py`** (new)

<!-- file: tests/meta/test_extension_ci.py -->
```python
"""The ``extension`` job runs the TypeScript workspace's checks in CI (#220, spec §12.1).

Each step after the scope and the lock runs one npm script inside ``extension/``, and each script
runs the tool the spec names, so a renamed script or a step dropped from the job goes red here.
"""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
JOBS: dict[str, dict[str, Any]] = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())[
    "jobs"
]
MANIFEST = ROOT / "extension/package.json"

# The npm commands the job runs, in order, and the tool behind each script (AC4).
COMMANDS = [
    "npm ci --ignore-scripts",
    "npm run lint",
    "npm run format:check",
    "npm run typecheck",
    "npm test",
    "npm run build",
]
TOOLS = {
    "lint": "eslint . --max-warnings 0",
    "format:check": "prettier --check .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run --coverage",
    "build": "node build.ts",
}


def job() -> dict[str, Any]:
    """The extension job, looked up per test so its absence fails each test by name."""
    assert "extension" in JOBS, sorted(JOBS)
    found: dict[str, Any] = JOBS["extension"]
    return found


def manifest() -> dict[str, Any]:
    found: dict[str, Any] = json.loads(MANIFEST.read_text())
    return found


def npm_steps() -> list[dict[str, Any]]:
    return [step for step in job()["steps"] if str(step.get("run", "")).startswith("npm ")]


def test_the_job_runs_the_workspace_checks_in_order() -> None:
    assert [step["run"] for step in npm_steps()] == COMMANDS


def test_every_npm_step_runs_inside_the_workspace() -> None:
    steps = npm_steps()
    assert len(steps) == len(COMMANDS)
    assert [step for step in steps if step.get("working-directory") != "extension"] == []


@pytest.mark.parametrize(("script", "command"), TOOLS.items())
def test_each_script_runs_the_tool_the_spec_names(script: str, command: str) -> None:
    assert manifest()["scripts"].get(script) == command


def test_node_comes_from_setup_node_at_the_engine_floor() -> None:
    setup = [
        step
        for step in job()["steps"]
        if str(step.get("uses", "")).startswith("actions/setup-node@")
    ]
    assert len(setup) == 1
    assert setup[0]["with"]["node-version"] == "24"
    assert manifest().get("engines") == {"node": ">=24"}
```


- [ ] **Step 2: Write the workspace in its red form.** Then `cd extension && npm ci --ignore-scripts`.

**`.gitignore`** (changed: 1 edit)

<!-- edit: .gitignore -->
Replace:
```
*.egg-info/

```
with:
```
*.egg-info/

# Node (extension/)
node_modules/
coverage/

```

**`extension/.npmrc`** (new)

<!-- file: extension/.npmrc -->
```
save-exact=true
```

**`extension/.prettierignore`** (new)

<!-- file: extension/.prettierignore -->
```
dist/
coverage/
package-lock.json
```

**`extension/.prettierrc.json`** (new)

<!-- file: extension/.prettierrc.json -->
```json
{
  "printWidth": 100
}
```

**`extension/build.ts`** (new)

<!-- file: extension/build.ts -->
```typescript
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
  throw new Error("not implemented: manifest");
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
  throw new Error("not implemented: build");
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
```

**`extension/eslint.config.js`** (new)

<!-- file: extension/eslint.config.js -->
```javascript
import js from "@eslint/js";
import { defineConfig, globalIgnores } from "eslint/config";
import tseslint from "typescript-eslint";

export default defineConfig(
  globalIgnores(["dist/", "coverage/"]),
  js.configs.recommended,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
);
```

**`extension/package-lock.json`** (generated by `npm install`, 3167 lines; copied from its git blob, never pasted)

<!-- copy: extension/package-lock.json blob=9c07f6e43ee4868472d7de76f0ddc5de3af9832b -->
```bash
git cat-file blob 9c07f6e43ee4868472d7de76f0ddc5de3af9832b > extension/package-lock.json
```

**`extension/package.json`** (new)

<!-- file: extension/package.json -->
```json
{
  "name": "steadyhand-extension",
  "version": "0.1.0",
  "private": true,
  "description": "What the strategy you chose implies, read from what your broker's page shows.",
  "license": "Apache-2.0",
  "type": "module",
  "workspaces": [
    "packages/*"
  ],
  "scripts": {},
  "devDependencies": {
    "@eslint/js": "^10.0.1",
    "@playwright/test": "^1.63.0",
    "@types/node": "^24.19.1",
    "@vitest/coverage-v8": "^5.0.3",
    "esbuild": "^0.28.2",
    "eslint": "^10.12.0",
    "prettier": "^3.9.9",
    "typescript": "^6.0.3",
    "typescript-eslint": "^8.71.1",
    "vite": "^8.3.3",
    "vitest": "^5.0.3"
  }
}
```

**`extension/packages/core/package.json`** (new)

<!-- file: extension/packages/core/package.json -->
```json
{
  "name": "@steadyhand/core",
  "version": "0.1.0",
  "private": true,
  "license": "Apache-2.0",
  "type": "module",
  "exports": "./src/index.ts",
  "dependencies": {}
}
```

**`extension/packages/core/src/index.ts`** (new)

<!-- file: extension/packages/core/src/index.ts -->
```typescript
/** The package's own name. The layers above read it to show they reach core through the workspace. */
export const PACKAGE = "";
```

**`extension/packages/history/package.json`** (new)

<!-- file: extension/packages/history/package.json -->
```json
{
  "name": "@steadyhand/history",
  "version": "0.1.0",
  "private": true,
  "license": "Apache-2.0",
  "type": "module",
  "exports": "./src/index.ts",
  "dependencies": {}
}
```

**`extension/packages/history/src/index.ts`** (new)

<!-- file: extension/packages/history/src/index.ts -->
```typescript
import { PACKAGE as CORE } from "@steadyhand/core";

/** The package's own name. */
export const PACKAGE = "";

/** The workspace packages this one is built on: history sits on core (spec §3). */
export const BUILT_ON: readonly string[] = [];
```

**`extension/packages/readers/package.json`** (new)

<!-- file: extension/packages/readers/package.json -->
```json
{
  "name": "@steadyhand/readers",
  "version": "0.1.0",
  "private": true,
  "license": "Apache-2.0",
  "type": "module",
  "exports": "./src/index.ts",
  "dependencies": {}
}
```

**`extension/packages/readers/src/index.ts`** (new)

<!-- file: extension/packages/readers/src/index.ts -->
```typescript
import { PACKAGE as CORE } from "@steadyhand/core";

/** The package's own name. */
export const PACKAGE = "";

/** The workspace packages this one is built on: readers sits on core (spec §3). */
export const BUILT_ON: readonly string[] = [];
```

**`extension/packages/shell/package.json`** (new)

<!-- file: extension/packages/shell/package.json -->
```json
{
  "name": "@steadyhand/shell",
  "version": "0.1.0",
  "private": true,
  "license": "Apache-2.0",
  "type": "module",
  "dependencies": {}
}
```

**`extension/packages/shell/src/content-script.ts`** (new)

<!-- file: extension/packages/shell/src/content-script.ts -->
```typescript
// The content script (spec §10.2) arrives with EXT S14a; this entry point gives it its bundle.
export {};
```

**`extension/packages/shell/src/service-worker.ts`** (new)

<!-- file: extension/packages/shell/src/service-worker.ts -->
```typescript
// The service worker arrives with EXT S14a; this entry point gives it its bundle.
export {};
```

**`extension/packages/shell/src/side-panel.ts`** (new)

<!-- file: extension/packages/shell/src/side-panel.ts -->
```typescript
import * as history from "@steadyhand/history";
import * as readers from "@steadyhand/readers";

// EXT S14a builds the panel. Until then the page records the packages it was built from, which
// shows the bundle carries the whole workspace: a bare package import would not load in Chrome.
const packages = new Set([
  ...readers.BUILT_ON,
  readers.PACKAGE,
  ...history.BUILT_ON,
  history.PACKAGE,
]);
document.documentElement.dataset["packages"] = [...packages].join(" ");
```

**`extension/playwright.config.ts`** (new)

<!-- file: extension/playwright.config.ts -->
```typescript
import { defineConfig } from "@playwright/test";

// A retry turns a real failure into a pass (Shyden's global rule), so there are none, anywhere.
export default defineConfig({
  testDir: "tests/browser",
  forbidOnly: true,
});
```

**`extension/tsconfig.json`** (new)

<!-- file: extension/tsconfig.json -->
```json
{
  "compilerOptions": {
    "target": "ES2024",
    "lib": ["ES2024", "DOM"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "types": ["node"],
    "noEmit": true,
    "allowJs": true,
    "checkJs": true,
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "noImplicitOverride": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": false
  },
  "include": ["packages/*/src", "packages/*/test", "tests", "*.ts", "*.js"]
}
```

**`extension/vitest.config.ts`** (new)

<!-- file: extension/vitest.config.ts -->
```typescript
import { defineConfig } from "vitest/config";

/** The packages held to 100% coverage (spec §14.1); the shell is proved by browser tests. */
export const COVERED = ["core", "readers", "history"] as const;

export default defineConfig({
  test: {
    include: ["packages/*/test/**/*.test.ts", "tests/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: COVERED.map((name) => `packages/${name}/src/**/*.ts`),
      reporter: ["text"],
    },
  },
});
```


- [ ] **Step 3: Watch them fail.** `npx vitest run` inside `extension/` (on the red form `npm ci` installs 152 packages: `decimal.js` arrives with the implementation, at the gate's `npm ci`), then `uv run pytest -p no:cacheprovider tests/meta/test_extension_ci.py tests/meta/test_ci_fast_path.py`. Measured: 37 of 39 new tests fail. The 8 build tests fail on `Error: not implemented: build`; every other one fails on its own assertion (`expected '' to be '@steadyhand/core'`, `expected [ 'packages/*' ] to deeply equal [ 'packages/core', …(3) ]`, `expected undefined to be +0`, `AssertionError: ['audit', 'build', 'lint', 'publish-dev', 'test']`, …). Two pass, as they must on any tree: `core is built on [] and on no other package` (an absence, proved by mutation T19) and `every locked package comes from the npm registry with a sha512 integrity` (the lock is generated, proved by mutation T13).

<!-- check: red -->

- [ ] **Step 4: Implement.**

**`.github/workflows/ci.yml`** (changed: 1 edit)

<!-- edit: .github/workflows/ci.yml -->
Replace:
```yaml

  publish-dev:
```
with:
```yaml

  # The TypeScript extension (spec §3, §12.1). Every tool runs inside extension/, so none walks
  # into the fast-path files the lock makes unreadable (#264).
  extension:
    name: extension
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          fetch-depth: 2
      - name: "Scope: may this docs-only change skip the rest?"
        id: scope
        env:
          EVENT_NAME: ${{ github.event_name }}
        run: python3 scripts/ci_scope.py "$EVENT_NAME"
      - name: "Lock the docs-only fast path: no later step may read it"
        if: steps.scope.outputs.docs_only != 'true'
        run: python3 scripts/lock_fast_path.py
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        if: steps.scope.outputs.docs_only != 'true'
        with:
          node-version: "24"
          cache: npm
          cache-dependency-path: extension/package-lock.json
      # No install script runs: a dependency's postinstall is code nobody reviewed.
      - run: npm ci --ignore-scripts
        if: steps.scope.outputs.docs_only != 'true'
        working-directory: extension
      - run: npm run lint
        if: steps.scope.outputs.docs_only != 'true'
        working-directory: extension
      - run: npm run format:check
        if: steps.scope.outputs.docs_only != 'true'
        working-directory: extension
      - run: npm run typecheck
        if: steps.scope.outputs.docs_only != 'true'
        working-directory: extension
      - run: npm test
        if: steps.scope.outputs.docs_only != 'true'
        working-directory: extension
      - run: npm run build
        if: steps.scope.outputs.docs_only != 'true'
        working-directory: extension

  publish-dev:
```

**`extension/.npmrc`** (changed: 1 edit)

<!-- edit: extension/.npmrc -->
Replace:
```
save-exact=true
```
with:
```
engine-strict=true
save-exact=true
```

**`extension/build.ts`** (changed: 2 edits)

<!-- edit: extension/build.ts -->
Replace:
```typescript
export function manifest(pkg: PackageJson): Record<string, unknown> {
  throw new Error("not implemented: manifest");
  return {
```
with:
```typescript
export function manifest(pkg: PackageJson): Record<string, unknown> {
  return {
```

<!-- edit: extension/build.ts -->
Replace:
```typescript
export async function build(outdir: string): Promise<void> {
  throw new Error("not implemented: build");
  const pkg = JSON.parse(await readFile(join(ROOT, "package.json"), "utf8")) as PackageJson;
```
with:
```typescript
export async function build(outdir: string): Promise<void> {
  const pkg = JSON.parse(await readFile(join(ROOT, "package.json"), "utf8")) as PackageJson;
```

**`extension/eslint.config.js`** (changed: 1 edit)

<!-- edit: extension/eslint.config.js -->
Replace:
```javascript
  js.configs.recommended,
  {
```
with:
```javascript
  js.configs.recommended,
  tseslint.configs.strictTypeChecked,
  {
```

**`extension/package.json`** (changed: 1 edit)

<!-- edit: extension/package.json -->
Replace:
```json
  "workspaces": [
    "packages/*"
  ],
  "scripts": {},
  "devDependencies": {
    "@eslint/js": "^10.0.1",
    "@playwright/test": "^1.63.0",
    "@types/node": "^24.19.1",
    "@vitest/coverage-v8": "^5.0.3",
    "esbuild": "^0.28.2",
    "eslint": "^10.12.0",
    "prettier": "^3.9.9",
    "typescript": "^6.0.3",
    "typescript-eslint": "^8.71.1",
    "vite": "^8.3.3",
    "vitest": "^5.0.3"
  }
```
with:
```json
  "workspaces": [
    "packages/core",
    "packages/readers",
    "packages/history",
    "packages/shell"
  ],
  "engines": {
    "node": ">=24"
  },
  "scripts": {
    "lint": "eslint . --max-warnings 0",
    "format:check": "prettier --check .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run --coverage",
    "build": "node build.ts"
  },
  "devDependencies": {
    "@eslint/js": "10.0.1",
    "@playwright/test": "1.63.0",
    "@types/node": "24.19.1",
    "@vitest/coverage-v8": "5.0.3",
    "esbuild": "0.28.2",
    "eslint": "10.12.0",
    "prettier": "3.9.9",
    "typescript": "6.0.3",
    "typescript-eslint": "8.71.1",
    "vite": "8.3.3",
    "vitest": "5.0.3"
  }
```

**`extension/packages/core/package.json`** (changed: 1 edit)

<!-- edit: extension/packages/core/package.json -->
Replace:
```json
  "exports": "./src/index.ts",
  "dependencies": {}
}
```
with:
```json
  "exports": "./src/index.ts",
  "dependencies": {
    "decimal.js": "10.6.0"
  }
}
```

**`extension/packages/core/src/index.ts`** (changed: 1 edit)

<!-- edit: extension/packages/core/src/index.ts -->
Replace:
```typescript
/** The package's own name. The layers above read it to show they reach core through the workspace. */
export const PACKAGE = "";
```
with:
```typescript
/** The package's own name. The layers above read it to show they reach core through the workspace. */
export const PACKAGE = "@steadyhand/core";
```

**`extension/packages/history/package.json`** (changed: 1 edit)

<!-- edit: extension/packages/history/package.json -->
Replace:
```json
  "exports": "./src/index.ts",
  "dependencies": {}
}
```
with:
```json
  "exports": "./src/index.ts",
  "dependencies": {
    "@steadyhand/core": "0.1.0"
  }
}
```

**`extension/packages/history/src/index.ts`** (changed: 1 edit)

<!-- edit: extension/packages/history/src/index.ts -->
Replace:
```typescript
/** The package's own name. */
export const PACKAGE = "";

/** The workspace packages this one is built on: history sits on core (spec §3). */
export const BUILT_ON: readonly string[] = [];
```
with:
```typescript
/** The package's own name. */
export const PACKAGE = "@steadyhand/history";

/** The workspace packages this one is built on: history sits on core (spec §3). */
export const BUILT_ON: readonly string[] = [CORE];
```

**`extension/packages/readers/package.json`** (changed: 1 edit)

<!-- edit: extension/packages/readers/package.json -->
Replace:
```json
  "exports": "./src/index.ts",
  "dependencies": {}
}
```
with:
```json
  "exports": "./src/index.ts",
  "dependencies": {
    "@steadyhand/core": "0.1.0"
  }
}
```

**`extension/packages/readers/src/index.ts`** (changed: 1 edit)

<!-- edit: extension/packages/readers/src/index.ts -->
Replace:
```typescript
/** The package's own name. */
export const PACKAGE = "";

/** The workspace packages this one is built on: readers sits on core (spec §3). */
export const BUILT_ON: readonly string[] = [];
```
with:
```typescript
/** The package's own name. */
export const PACKAGE = "@steadyhand/readers";

/** The workspace packages this one is built on: readers sits on core (spec §3). */
export const BUILT_ON: readonly string[] = [CORE];
```

**`extension/packages/shell/package.json`** (changed: 1 edit)

<!-- edit: extension/packages/shell/package.json -->
Replace:
```json
  "type": "module",
  "dependencies": {}
}
```
with:
```json
  "type": "module",
  "dependencies": {
    "@steadyhand/history": "0.1.0",
    "@steadyhand/readers": "0.1.0"
  }
}
```

**`extension/playwright.config.ts`** (changed: 1 edit)

<!-- edit: extension/playwright.config.ts -->
Replace:
```typescript
  testDir: "tests/browser",
  forbidOnly: true,
```
with:
```typescript
  testDir: "tests/browser",
  retries: 0,
  forbidOnly: true,
```

**`extension/tsconfig.json`** (changed: 1 edit)

<!-- edit: extension/tsconfig.json -->
Replace:
```json
    "isolatedModules": true,
    "noImplicitOverride": true,
```
with:
```json
    "isolatedModules": true,
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
```

**`extension/vitest.config.ts`** (changed: 1 edit)

<!-- edit: extension/vitest.config.ts -->
Replace:
```typescript
      reporter: ["text"],
    },
```
with:
```typescript
      reporter: ["text"],
      thresholds: { branches: 100, functions: 100, lines: 100, statements: 100 },
    },
```


- [ ] **Step 5: Run the gate.**

<!-- check: gate -->

- [ ] **Step 6: Mutations T1–T19 and W1–W6** from **Mutation checks**. T1–T4 are AC2's and AC3's planted violations: tsc, ESLint, Prettier and the coverage threshold each go red.
- [ ] **Step 7: Commit** `feat(extension): #220 the TypeScript workspace, its toolchain and the extension CI job (Refs #220)`.

### Task 3: Dependabot keeps the extension's npm packages current

**Acceptance criteria (story text):** AC5 (the `npm` ecosystem for `/extension`, targeting `develop`, asserted by the supply-chain test).

**Files:**
- Modify: `.github/dependabot.yml`, `tests/meta/test_supply_chain.py`

**Interfaces:**
- Produces: `test_supply_chain.npm_locks()`, `exact_peers(lock: Path) -> list[tuple[str, str]]`, `group_of(name, groups) -> str | None`, `update_for(ecosystem, directory) -> dict`.

The guard derives the ecosystems from the lock files git lists, and derives from the lock which direct dependencies pin each other exactly: vitest and `@vitest/coverage-v8` each declare the other's exact version as a peer, so a Dependabot PR moving one alone cannot install. They share a group above the catch-all, as `actions/cache` and its sub-paths do.

- [ ] **Step 1: Write the failing tests.**

**`tests/meta/test_supply_chain.py`** (changed: 6 edits)

<!-- edit: tests/meta/test_supply_chain.py -->
Replace:
```python

import re
```
with:
```python

import fnmatch
import json
import re
```

<!-- edit: tests/meta/test_supply_chain.py -->
Replace:
```python

import yaml
```
with:
```python

import pytest
import yaml
```

<!-- edit: tests/meta/test_supply_chain.py -->
Replace:
```python

def ecosystems_present() -> set[str]:
```
with:
```python

def npm_locks() -> list[Path]:
    """Every npm lock file git lists, outside node_modules (#220)."""
    return [path for path in tracked(ROOT, "package-lock.json") if "node_modules" not in path.parts]


def ecosystems_present() -> set[str]:
```

<!-- edit: tests/meta/test_supply_chain.py -->
Replace:
```python
        present.add("github-actions")
    return present

```
with:
```python
        present.add("github-actions")
    if npm_locks():
        present.add("npm")
    return present


def update_for(ecosystem: str, directory: str) -> dict[str, Any]:
    found = [
        update
        for update in dependabot()["updates"]
        if update["package-ecosystem"] == ecosystem and update["directory"] == directory
    ]
    assert len(found) == 1, (ecosystem, directory, found)
    update: dict[str, Any] = found[0]
    return update

```

<!-- edit: tests/meta/test_supply_chain.py -->
Replace:
```python
    present = ecosystems_present()
    assert present == {"uv", "github-actions"}
    configured = {update["package-ecosystem"] for update in dependabot()["updates"]}
```
with:
```python
    present = ecosystems_present()
    assert present == {"uv", "github-actions", "npm"}
    configured = {update["package-ecosystem"] for update in dependabot()["updates"]}
```

<!-- edit: tests/meta/test_supply_chain.py -->
Replace:
```python

def test_every_dependabot_update_targets_develop_weekly() -> None:
    updates = dependabot()["updates"]
    assert len(updates) >= 2
    wrong = [
```
with:
```python

def test_the_npm_locks_are_the_extension_workspace_alone() -> None:
    assert [path.relative_to(ROOT).as_posix() for path in npm_locks()] == [
        "extension/package-lock.json"
    ]


@pytest.mark.parametrize("lock", npm_locks(), ids=lambda path: path.relative_to(ROOT).as_posix())
def test_every_npm_lock_has_its_own_dependabot_update(lock: Path) -> None:
    update = update_for("npm", f"/{lock.parent.relative_to(ROOT).as_posix()}")
    assert update["target-branch"] == "develop"


def exact_peers(lock: Path) -> list[tuple[str, str]]:
    """Each pair of direct dependencies where one's peer range is the other's exact version, as
    the lock records it: a Dependabot PR moving one alone cannot install (#220)."""
    packages: dict[str, dict[str, Any]] = json.loads(lock.read_text(encoding="utf-8"))["packages"]
    direct = {
        name
        for path, entry in packages.items()
        if not path.startswith("node_modules/")
        for field in ("dependencies", "devDependencies")
        for name in entry.get(field, {})
        if not name.startswith("@steadyhand/")
    }
    return sorted(
        (name, peer)
        for name in direct
        for peer, spec in packages[f"node_modules/{name}"].get("peerDependencies", {}).items()
        if peer in direct and re.fullmatch(r"\d+\.\d+\.\d+", spec)
    )


def group_of(name: str, groups: dict[str, dict[str, Any]]) -> str | None:
    """The first group whose patterns match *name*, as Dependabot assigns it."""
    for group, spec in groups.items():
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in spec.get("patterns", [])):
            return group
    return None


NPM_LOCK = ROOT / "extension/package-lock.json"


def test_the_exact_peer_pairs_are_the_ones_measured() -> None:
    # Measured on 2026-10-06 (#220): vitest and @vitest/coverage-v8 each pin the other.
    assert exact_peers(NPM_LOCK) == [
        ("@vitest/coverage-v8", "vitest"),
        ("vitest", "@vitest/coverage-v8"),
    ]


@pytest.mark.parametrize(("name", "peer"), exact_peers(NPM_LOCK))
def test_packages_pinned_to_each_other_move_in_one_group(name: str, peer: str) -> None:
    groups: dict[str, dict[str, Any]] = update_for("npm", "/extension")["groups"]
    group = group_of(name, groups)
    assert group is not None, f"{name} is in no group, so it moves without {peer}"
    assert group_of(peer, groups) == group
    # The catch-all comes after: Dependabot puts an update in the first group that matches.
    catch_all = next(found for found, spec in groups.items() if "update-types" in spec)
    assert list(groups).index(group) < list(groups).index(catch_all)


def test_every_dependabot_update_targets_develop_weekly() -> None:
    updates = dependabot()["updates"]
    assert len(updates) >= 3
    wrong = [
```


- [ ] **Step 2: The red form** (nothing to write: `dependabot.yml` is unchanged until Step 4).



- [ ] **Step 3: Watch them fail.** `uv run pytest -p no:cacheprovider tests/meta/test_supply_chain.py`. Measured: 5 of 7 new tests fail on their assertions (`{'github-actions', 'npm', 'uv'} <= {'github-actions', 'uv'}`, `('npm', '/extension', [])`, `assert 2 >= 3`). Two pass on any `dependabot.yml`, because they read the lock: `test_the_npm_locks_are_the_extension_workspace_alone` (mutation W17) and `test_the_exact_peer_pairs_are_the_ones_measured` (mutation W18).

<!-- check: red -->

- [ ] **Step 4: Implement.**

**`.github/dependabot.yml`** (changed: 1 edit)

<!-- edit: .github/dependabot.yml -->
Replace:
```yaml
        update-types: ["patch"]
```
with:
```yaml
        update-types: ["patch"]

  - package-ecosystem: "npm"
    directory: "/extension"
    target-branch: "develop"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "chore(deps)"
    groups:
      # vitest and @vitest/coverage-v8 each pin the other's exact version, so a PR moving one
      # alone cannot install. This group moves them together; it stays above the catch-all,
      # because the first matching group wins.
      vitest:
        patterns: ["vitest", "@vitest/*"]
      npm-minor-and-patch:
        update-types: ["minor", "patch"]
```


- [ ] **Step 5: Run the gate.**

<!-- check: gate -->

- [ ] **Step 6: Mutations W7–W9, W17, W18.**
- [ ] **Step 7: Commit** `build(deps): #220 Dependabot keeps the extension's npm packages current (Refs #220)`.

### Task 4: Develop deploys the attested extension zip; publish-dev and the yahoo-shape schedule retire

**Acceptance criteria (story text):** AC6 (the zip, attested and verified on the develop run), AC7 (`publish-dev` removed, `yahoo-shape.yml` disabled, every doc naming them updated).

**Files:**
- Modify: `.github/workflows/ci.yml` (`publish-dev` becomes `deploy-dev`), `.github/workflows/yahoo-shape.yml`, `pyproject.toml`, `packages/steadyhand-idx/src/steadyhand_idx/yahoo.py` (a docstring), `tests/idx/test_yahoo_live.py` and `tests/meta/test_coverage_exclusions.py` (docstrings), `tests/meta/test_ci_fast_path.py`, `tests/meta/test_supply_chain.py` (the TestPyPI index test goes with the job)
- Create: `tests/meta/test_deploy_dev.py`
- Delete: `scripts/set_dev_version.py`, `tests/scripts/test_set_dev_version.py` (only `publish-dev` ran it)

**Interfaces:**
- Produces: the `deploy-dev` job; its step outputs `steps.zip.outputs.path`.

`publish-dev`'s install check retried ten times with `sleep 30`, a retry the global rule forbids; it goes with the job. The historical plans that name `publish-dev` are records and stay as written; `HANDOVER.md` is updated by the story's handover PR.

- [ ] **Step 1: Write the failing tests.**

**`tests/idx/test_yahoo_live.py`** (changed: 1 edit)

<!-- edit: tests/idx/test_yahoo_live.py -->
Replace:
```python

Marked ``live``: it talks to Yahoo, so it never runs on a pull request. The daily yahoo-shape
workflow runs it and opens an issue when it fails. The comparison is on the UNADJUSTED result,
so a split Yahoo applies after the recording does not break it; a changed format, changed
prices or a new unreported adjustment does. And a ticker Yahoo does not know is still answered
as a stock it cannot serve (#200), so a run goes on without it rather than stopping.
"""
```
with:
```python

Marked ``live``: it talks to Yahoo, so it never runs on a pull request. The yahoo-shape workflow,
started by hand since #220, runs it and opens an issue when it fails. The comparison is on the
UNADJUSTED result, so a split Yahoo applies after the recording does not break it; a changed format,
changed prices or a new unreported adjustment does. And a ticker Yahoo does not know is still
answered as a stock it cannot serve (#200), so a run goes on without it rather than stopping.
"""
```

**`tests/meta/test_ci_fast_path.py`** (changed: 1 edit)

<!-- edit: tests/meta/test_ci_fast_path.py -->
Replace:
```python
    assert "extension" in GATED
    assert "publish-dev" in DEPLOYS
    assert len(GATED) >= GATED_FLOOR
```
with:
```python
    assert "extension" in GATED
    assert DEPLOYS == ["deploy-dev"]
    assert len(GATED) >= GATED_FLOOR
```

**`tests/meta/test_coverage_exclusions.py`** (changed: 1 edit)

<!-- edit: tests/meta/test_coverage_exclusions.py -->
Replace:
```python
Spec §10.5 asks for 100% branch coverage. The network call cannot run on a pull request, so it is
excluded and run instead by the daily yahoo-shape workflow. Any second exclusion is a hole in
the 100%, so this guard fails on it. It reads comments on purpose: the pragma is a comment.
```
with:
```python
Spec §10.5 asks for 100% branch coverage. The network call cannot run on a pull request, so it is
excluded and run instead by the yahoo-shape workflow, by hand. Any second exclusion is a hole in
the 100%, so this guard fails on it. It reads comments on purpose: the pragma is a comment.
```

**`tests/meta/test_deploy_dev.py`** (new)

<!-- file: tests/meta/test_deploy_dev.py -->
```python
"""Develop's deploy is the extension zip, its build provenance attested and verified (#220).

Spec §12.1: the Python TestPyPI ``publish-dev`` job is retired, and so is the daily
``yahoo-shape`` schedule, which checks a data source the extension does not use (decision 21).
"""

import shlex
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
# PyYAML reads the bare key `on` as the boolean True, so a key may be a bool.
CI: dict[str | bool, Any] = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
JOBS: dict[str, dict[str, Any]] = CI["jobs"]
GATED = sorted(name for name, job in JOBS.items() if "environment" not in job)


def deploy() -> dict[str, Any]:
    """The deploy job, looked up per test so its absence fails each test by name."""
    assert "deploy-dev" in JOBS, sorted(JOBS)
    job: dict[str, Any] = JOBS["deploy-dev"]
    return job


def step(name: str) -> dict[str, Any]:
    found: list[dict[str, Any]] = [s for s in deploy()["steps"] if s.get("name") == name]
    assert len(found) == 1, (name, found)
    return found[0]


def test_the_deploy_runs_on_a_push_to_develop_after_every_gated_job() -> None:
    assert deploy()["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/develop'"
    assert sorted(deploy()["needs"]) == GATED
    assert "extension" in GATED


def test_the_deploy_holds_only_the_permissions_an_attestation_needs() -> None:
    assert deploy()["permissions"] == {
        "contents": "read",
        "id-token": "write",
        "attestations": "write",
    }


def test_the_deploy_builds_the_zip_from_a_clean_install() -> None:
    runs = [s.get("run") for s in deploy()["steps"] if s.get("working-directory") == "extension"]
    assert runs == ["npm ci --ignore-scripts", "npm run build"]
    zipped = step("Zip the built extension")
    assert zipped["working-directory"] == "extension/dist"
    assert 'zip -X -r -q "${ZIP}" .' in zipped["run"]


def test_the_zip_is_attested_then_verified_as_this_workflow_on_develop() -> None:
    names = [s.get("name") for s in deploy()["steps"]]
    attest = step("Attest the zip's build provenance")
    assert attest["uses"].startswith("actions/attest@")
    assert attest["with"] == {"subject-path": "${{ steps.zip.outputs.path }}"}
    verify = step("Verify the attestation")
    assert verify["env"]["ZIP"] == "${{ steps.zip.outputs.path }}"
    lines = verify["run"].splitlines()
    assert shlex.split(lines[0]) == [
        "gh",
        "attestation",
        "verify",
        "${ZIP}",
        "--repo",
        "${GITHUB_REPOSITORY}",
        "--signer-workflow",
        "${GITHUB_REPOSITORY}/.github/workflows/ci.yml",
        "--source-ref",
        "refs/heads/develop",
        "--format",
        "json",
        ">",
        "${RUNNER_TEMP}/verified.json",
    ]
    # The verdict names this zip: its own digest is among the subjects verified.
    assert lines[1] == 'read -r digest _ < <(sha256sum "${ZIP}")'
    assert shlex.split(lines[2]) == [
        "jq",
        "-e",
        "--arg",
        "digest",
        "${digest}",
        "any(.[].verificationResult.statement.subject[]; .digest.sha256 == $digest)",
        "${RUNNER_TEMP}/verified.json",
    ]
    assert names.index("Attest the zip's build provenance") < names.index("Verify the attestation")


def test_the_verified_zip_is_kept_as_it_is_not_zipped_again() -> None:
    names = [s.get("name") for s in deploy()["steps"]]
    upload = step("Keep the zip")
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["with"]["archive"] is False
    assert upload["with"]["path"] == "${{ steps.zip.outputs.path }}"
    assert upload["with"]["if-no-files-found"] == "error"
    assert names.index("Verify the attestation") < names.index("Keep the zip")


def test_nothing_publishes_to_testpypi_any_more() -> None:
    texts = {path.name: path.read_text(encoding="utf-8") for path in WORKFLOWS.glob("*.yml")}
    assert len(texts) >= 2
    assert "publish-dev" not in JOBS
    assert [name for name, text in texts.items() if "pypi" in text.lower()] == []


def test_the_yahoo_shape_check_runs_only_by_hand() -> None:
    shape: dict[str | bool, Any] = yaml.safe_load(
        (WORKFLOWS / "yahoo-shape.yml").read_text(encoding="utf-8")
    )
    assert shape[True] == {"workflow_dispatch": None}
```

**`tests/meta/test_supply_chain.py`** (changed: 2 edits)

<!-- edit: tests/meta/test_supply_chain.py -->
Replace:
```python
import re
import shlex
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path
```
with:
```python
import re
from collections.abc import Iterator
from pathlib import Path
```

<!-- edit: tests/meta/test_supply_chain.py -->
Replace:
```python
    assert names.index(sub_path[0]) < names.index(patch[0])


INDEX_FLAGS = ("--index", "--default-index", "--index-url", "--extra-index-url", "-i")


def shell_words(script: str) -> list[str]:
    """A ``run`` script as the shell splits it: continuations joined, ``--flag=value`` split."""
    words = shlex.split(script.replace("\\\n", " "))
    return [part for word in words for part in (word.split("=", 1) if word[:2] == "--" else [word])]


def index_flags(words: list[str]) -> list[tuple[str, str]]:
    return [(flag, value) for flag, value in pairwise(words) if flag in INDEX_FLAGS]


def test_the_testpypi_check_takes_every_dependency_from_pypi_first() -> None:
    """Anyone can upload to TestPyPI, and a ``yfinance`` that is not the real one lives there.

    PyPI is searched first, so a name PyPI carries never comes from TestPyPI; only steadyhand's
    own dev builds, which PyPI does not have, fall through to it (#57). No strategy flag may
    widen that to a best-match across both indexes.
    """
    ci = yaml.safe_load((WORKFLOWS / "ci.yml").read_text())
    steps = [
        step
        for step in ci["jobs"]["publish-dev"]["steps"]
        if step.get("name") == "Verify both packages install from TestPyPI"
    ]
    assert len(steps) == 1, steps
    scopes = (ci, ci["jobs"]["publish-dev"], steps[0])
    # UV_INDEX, UV_DEFAULT_INDEX, UV_INDEX_STRATEGY, PIP_INDEX_URL...: all spell INDEX.
    assert [name for scope in scopes for name in scope.get("env", {}) if "INDEX" in name] == []
    words = shell_words(steps[0]["run"])
    assert index_flags(words) == [
        ("--index", "https://pypi.org/simple/"),
        ("--default-index", "https://test.pypi.org/simple/"),
    ]
    assert "--index-strategy" not in words
```
with:
```python
    assert names.index(sub_path[0]) < names.index(patch[0])
```

Delete `tests/scripts/test_set_dev_version.py`:

<!-- delete: tests/scripts/test_set_dev_version.py -->
```bash
git rm -q tests/scripts/test_set_dev_version.py
```


- [ ] **Step 2: Everything but the workflows**, which stay as Task 3 left them until Step 4: the docstrings and `pyproject.toml` that named the retired jobs, and the two files only `publish-dev` used.

**`packages/steadyhand-idx/src/steadyhand_idx/yahoo.py`** (changed: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
def download_history(ticker: str, start: date, end: date) -> YahooHistory:  # pragma: no cover
    """Ask Yahoo for one ticker's history (network; run daily by the yahoo-shape workflow).

```
with:
```python
def download_history(ticker: str, start: date, end: date) -> YahooHistory:  # pragma: no cover
    """Ask Yahoo for one ticker's history (network; run by hand by the yahoo-shape workflow).

```

**`pyproject.toml`** (changed: 2 edits)

<!-- edit: pyproject.toml -->
Replace:
```toml
[tool.ruff.lint.isort]
known-first-party = ["steadyhand", "steadyhand_idx", "set_dev_version", "ci_scope", "lock_fast_path"]

```
with:
```toml
[tool.ruff.lint.isort]
known-first-party = ["steadyhand", "steadyhand_idx", "ci_scope", "lock_fast_path"]

```

<!-- edit: pyproject.toml -->
Replace:
```toml
markers = [
    "live: talks to Yahoo; run by the daily yahoo-shape workflow with -m live, never on a PR",
    "perf: times the engine, paper runs and start-up; CI runs it with -m perf, without coverage",
```
with:
```toml
markers = [
    "live: talks to Yahoo; run by the yahoo-shape workflow, by hand, with -m live, never on a PR",
    "perf: times the engine, paper runs and start-up; CI runs it with -m perf, without coverage",
```

Delete `scripts/set_dev_version.py`:

<!-- delete: scripts/set_dev_version.py -->
```bash
git rm -q scripts/set_dev_version.py
```


- [ ] **Step 3: Watch them fail.** `uv run pytest -p no:cacheprovider tests/meta/test_deploy_dev.py tests/meta/test_ci_fast_path.py`. Measured: 8 of 8 new tests fail on their assertions (`AssertionError: ['audit', 'build', 'extension', 'lint', 'publish-dev', 'test']` from the job lookup, `assert ['publish-dev'] == ['deploy-dev']`, `assert 'publish-dev' not in {…}`, `{'schedule': …, 'workflow_dispatch': None} == {'workflow_dispatch': None}`).

<!-- check: red -->

- [ ] **Step 4: Implement.**

**`.github/workflows/ci.yml`** (changed: 2 edits)

<!-- edit: .github/workflows/ci.yml -->
Replace:
```yaml

  publish-dev:
    name: publish-dev
    if: github.event_name == 'push' && github.ref == 'refs/heads/develop'
    needs: [lint, test, audit, build]
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    environment:
      name: testpypi
      url: https://test.pypi.org/project/steadyhand/
    permissions:
      contents: read
      id-token: write
    steps:
```
with:
```yaml

  # Develop's deploy (spec §12.1): the extension zip, its build provenance attested and then
  # verified here, on the run that made it. It always runs in full (#218).
  deploy-dev:
    name: deploy-dev
    if: github.event_name == 'push' && github.ref == 'refs/heads/develop'
    needs: [lint, test, audit, build, extension]
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    environment:
      name: dev
    permissions:
      contents: read
      id-token: write
      attestations: write
    steps:
```

<!-- edit: .github/workflows/ci.yml -->
Replace:
```yaml
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: "3.12"
      - name: Set the development version
        id: version
        env:
          RUN_NUMBER: ${{ github.run_number }}
        run: |
          version="$(uv run --no-project python scripts/set_dev_version.py "${RUN_NUMBER}")"
          echo "version=${version}" >> "${GITHUB_OUTPUT}"
      - run: uv build --all-packages --out-dir dist
      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2
        with:
          repository-url: https://test.pypi.org/legacy/
          packages-dir: dist/
          # A re-run reuses the run number, so the version: skip what the first attempt uploaded.
          skip-existing: true
      - name: Verify both packages install from TestPyPI
        env:
          VERSION: ${{ steps.version.outputs.version }}
        run: |
          for attempt in 1 2 3 4 5 6 7 8 9 10; do
            rm -rf "${RUNNER_TEMP}/verify"
            uv venv "${RUNNER_TEMP}/verify"
            # PyPI first: uv takes each name from the first index that has it, so real
            # dependencies (yfinance) come from PyPI and only our dev builds, which PyPI lacks,
            # from TestPyPI. Anyone can upload to TestPyPI, so it must never be asked first.
            if uv pip install --refresh --python "${RUNNER_TEMP}/verify" \
                --index https://pypi.org/simple/ \
                --default-index https://test.pypi.org/simple/ \
                "steadyhand==${VERSION}" "steadyhand-idx==${VERSION}"; then
              "${RUNNER_TEMP}/verify/bin/python" -c 'import sys, steadyhand, steadyhand_idx; assert steadyhand.__version__ == steadyhand_idx.__version__ == sys.argv[1], (steadyhand.__version__, steadyhand_idx.__version__)' "${VERSION}"
              exit 0
            fi
            echo "attempt ${attempt}: not installable yet"
            sleep 30
          done
          echo "steadyhand ${VERSION} never became installable from TestPyPI" >&2
          exit 1
```
with:
```yaml
          persist-credentials: false
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version: "24"
          cache: npm
          cache-dependency-path: extension/package-lock.json
      - run: npm ci --ignore-scripts
        working-directory: extension
      - run: npm run build
        working-directory: extension
      - name: Zip the built extension
        id: zip
        working-directory: extension/dist
        env:
          ZIP: ${{ runner.temp }}/steadyhand-extension-${{ github.sha }}.zip
        run: |
          zip -X -r -q "${ZIP}" .
          unzip -l "${ZIP}"
          echo "path=${ZIP}" >> "${GITHUB_OUTPUT}"
      - name: Attest the zip's build provenance
        uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2
        with:
          subject-path: ${{ steps.zip.outputs.path }}
      - name: Verify the attestation
        env:
          GH_TOKEN: ${{ github.token }}
          ZIP: ${{ steps.zip.outputs.path }}
        # gh prints nothing on success, so the JSON verdict is kept and checked to name this zip.
        run: |
          gh attestation verify "${ZIP}" --repo "${GITHUB_REPOSITORY}" --signer-workflow "${GITHUB_REPOSITORY}/.github/workflows/ci.yml" --source-ref refs/heads/develop --format json > "${RUNNER_TEMP}/verified.json"
          read -r digest _ < <(sha256sum "${ZIP}")
          jq -e --arg digest "${digest}" 'any(.[].verificationResult.statement.subject[]; .digest.sha256 == $digest)' "${RUNNER_TEMP}/verified.json"
          echo "verified: ${ZIP##*/} sha256:${digest}"
      - name: Keep the zip
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          path: ${{ steps.zip.outputs.path }}
          archive: false
          if-no-files-found: error
```

**`.github/workflows/yahoo-shape.yml`** (changed: 1 edit)

<!-- edit: .github/workflows/yahoo-shape.yml -->
Replace:
```yaml

# Spec §9.2: once a day, ask Yahoo for the recorded fixture ranges and check that the answer still
# converts to the same unadjusted prices. A changed format, changed prices or a new unreported
# adjustment opens an issue, so it is noticed before it breaks a user's run. It is not a PR gate:
# Yahoo being down must not block a merge.

on:
  schedule:
    - cron: "30 1 * * *" # 08:30 WIB, before the market opens
  workflow_dispatch:
```
with:
```yaml

# Spec §9.2: ask Yahoo for the recorded fixture ranges and check that the answer still converts to
# the same unadjusted prices. A changed format, changed prices or a new unreported adjustment opens
# an issue. It is not a PR gate: Yahoo being down must not block a merge.
#
# It runs only by hand since #220: the extension reads the user's broker, never Yahoo, so its daily
# schedule was retired with publish-dev (broker-view spec §12.1, decision 21). The Python packages
# keep their Yahoo layer, and this check still serves them when someone works on it.

on:
  workflow_dispatch:
```


- [ ] **Step 5: Run the gate.**

<!-- check: gate -->

- [ ] **Step 6: Mutations W10–W15.**
- [ ] **Step 7: Commit** `feat(ci): #220 develop deploys the attested extension zip; publish-dev and the yahoo-shape schedule retire (Refs #220)`.

## Mutation checks

Each mutation is applied to the final tree, its anchor matching exactly once, and the named check is run. A prediction is the exact set of tests that fail; "the tool" means the tool itself exits non-zero with every test passing. Predictions were written before any run.

| Id | File | Change | Check | Predicted to fail | Run |
|---|---|---|---|---|---|
| T1 | `extension/packages/core/src/index.ts` | `const planted: string[] = [];` | tsc | the tool | red (exit 2, 0 tests), as predicted |
| T2 | `extension/packages/core/src/index.ts` | `export const planted = (): void => {` | eslint | the tool | red (exit 1, 0 tests), as predicted |
| T3 | `extension/packages/core/src/index.ts` | `export const PACKAGE =   "@steadyhand/core";` | prettier | the tool | red (exit 1, 0 tests), as predicted |
| T4 | `extension/packages/core/src/index.ts` | `` | npm-test | the tool | red (exit 1, 0 tests), as predicted |
| T5 | `extension/tsconfig.json` | `"noUncheckedIndexedAccess": false` | vitest | workspace.test.ts > TypeScript runs strict, with checked indexes and exact optional properties | red (exit 1, 30 tests), as predicted |
| T6 | `extension/eslint.config.js` | `tseslint.configs.recommendedTypeChecked,` | vitest | workspace.test.ts > ESLint applies every rule set of typescript-eslint's strict, type-checked config | red (exit 1, 30 tests), as predicted |
| T7 | `extension/vitest.config.ts` | `branches: 99,` | vitest | workspace.test.ts > Vitest fails below 100% coverage on every measure | red (exit 1, 30 tests), as predicted |
| T8 | `extension/playwright.config.ts` | `retries: 1,` | vitest | toolchain.test.ts > Playwright never retries a failed test | red (exit 1, 30 tests), as predicted |
| T9 | `extension/packages/core/package.json` | `"decimal.js": "^10.6.0"` | vitest | workspace.test.ts > packages/core/package.json pins every dependency to one exact version | red (exit 1, 30 tests), as predicted |
| T10 | `extension/packages/core/package.json` | `"decimal.js": "10.6.0",` | vitest | workspace.test.ts > core's only runtime dependency is decimal.js | red (exit 1, 30 tests), as predicted |
| T11 | `extension/package.json` | `"node": ">=22"` | vitest | workspace.test.ts > Node 24 or later is required, and npm refuses to install on anything older | red (exit 1, 30 tests), as predicted |
| T12 | `extension/.npmrc` | `removed: engine-strict=true` | vitest | workspace.test.ts > Node 24 or later is required, and npm refuses to install on anything older | red (exit 1, 30 tests), as predicted |
| T13 | `extension/package-lock.json` | `"resolved": "https://example.org/decimal.js-10.6.0.tgz"` | vitest | workspace.test.ts > every locked package comes from the npm registry with a sha512 integrity | red (exit 1, 30 tests), as predicted |
| T14 | `extension/packages/readers/package.json` | `"@steadyhand/core": "0.1.0",` | vitest | workspace.test.ts > readers is built on ["core"] and on no other package | red (exit 1, 30 tests), as predicted |
| T15 | `extension/build.ts` | `format: "esm",` | vitest | build.test.ts > content-script is one self-contained script, no module syntax left; build.test.ts > side-panel is one self-contained script, no module syntax left; build.test.ts > service-worker is one self-contained script, no module syntax left | red (exit 1, 30 tests), as predicted |
| T16 | `extension/build.ts` | `["content-script", "side-panel"]` | vitest | build.test.ts > the build emits one bundle per entry point and the manifest, nothing else | red (exit 1, 29 tests), as predicted |
| T17 | `extension/build.ts` | `external: ["@steadyhand/*"],` | vitest | build.test.ts > side-panel is one self-contained script, no module syntax left; build.test.ts > the side panel bundle carries @steadyhand/core, which it imports through the workspace | red (exit 1, 30 tests), as predicted |
| T18 | `extension/build.ts` | `permissions: ["tabs"],` | vitest | build.test.ts > the manifest is Manifest V3 at the workspace's version, asking for no permission | red (exit 1, 30 tests), as predicted |
| W1 | `.github/workflows/ci.yml` | `removed: - run: npm run typecheck` | pytest | test_the_job_runs_the_workspace_checks_in_order; test_every_npm_step_runs_inside_the_workspace | red (exit 1, 671 tests), as predicted |
| W2 | `.github/workflows/ci.yml` | `- run: npm ci` | pytest | test_the_job_runs_the_workspace_checks_in_order | red (exit 1, 671 tests), as predicted |
| W3 | `.github/workflows/ci.yml` | `- run: npm run lint` | pytest | test_every_npm_step_runs_inside_the_workspace | red (exit 1, 671 tests), as predicted |
| W4 | `extension/package.json` | `"typecheck": "tsc"` | pytest | test_each_script_runs_the_tool_the_spec_names[typecheck-tsc --noEmit] | red (exit 1, 671 tests), as predicted |
| W5 | `.github/workflows/ci.yml` | `- uses: actions/setup-node@` | pytest | test_a_gated_job_locks_the_fast_path_before_any_other_step[extension] | red (exit 1, 671 tests), as predicted |
| W6 | `.github/workflows/ci.yml` | `- run: npm run build` | pytest | test_a_gated_job_reports_and_skips_every_later_step[extension]; test_the_skip_covers_every_later_step_of_every_gated_job | red (exit 1, 671 tests), as predicted |
| W7 | `.github/dependabot.yml` | `- package-ecosystem: "pip"` | pytest | test_dependabot_covers_every_ecosystem_in_the_repo; test_every_npm_lock_has_its_own_dependabot_update[extension/package-lock.json]; test_packages_pinned_to_each_other_move_in_one_group[@vitest/coverage-v8-vitest]; test_packages_pinned_to_each_other_move_in_one_group[vitest-@vitest/coverage-v8] | red (exit 1, 671 tests), as predicted |
| W8 | `.github/dependabot.yml` | `npm-minor-and-patch:` | pytest | test_packages_pinned_to_each_other_move_in_one_group[@vitest/coverage-v8-vitest]; test_packages_pinned_to_each_other_move_in_one_group[vitest-@vitest/coverage-v8] | red (exit 1, 671 tests), as predicted |
| W9 | `.github/dependabot.yml` | `patterns: ["vitest"]` | pytest | test_packages_pinned_to_each_other_move_in_one_group[@vitest/coverage-v8-vitest]; test_packages_pinned_to_each_other_move_in_one_group[vitest-@vitest/coverage-v8] | red (exit 1, 671 tests), as predicted |
| W10 | `.github/workflows/ci.yml` | `needs: [lint, test, audit, build]` | pytest | test_the_deploy_runs_on_a_push_to_develop_after_every_gated_job | red (exit 1, 671 tests), as predicted |
| W11 | `.github/workflows/ci.yml` | `packages: write` | pytest | test_the_deploy_holds_only_the_permissions_an_attestation_needs | red (exit 1, 671 tests), as predicted |
| W12 | `.github/workflows/ci.yml` | `--format json` | pytest | test_the_zip_is_attested_then_verified_as_this_workflow_on_develop | red (exit 1, 671 tests), as predicted |
| W13 | `.github/workflows/ci.yml` | `archive: true` | pytest | test_the_verified_zip_is_kept_as_it_is_not_zipped_again | red (exit 1, 671 tests), as predicted |
| W14 | `.github/workflows/yahoo-shape.yml` | `schedule:` | pytest | test_the_yahoo_shape_check_runs_only_by_hand | red (exit 1, 671 tests), as predicted |
| W15 | `.github/workflows/ci.yml` | `- run: echo https://test.pypi.org/legacy/` | pytest | test_nothing_publishes_to_testpypi_any_more | red (exit 1, 671 tests), as predicted |
| W16 | `scripts/ci_scope.py` | `paths = f"{len(found)} paths"` | pytest | test_a_docs_only_verdict_counts_its_paths[one] | red (exit 1, 671 tests), as predicted |
| T19 | `extension/packages/core/package.json` | `"@steadyhand/history": "0.1.0",` | vitest | workspace.test.ts > core is built on [] and on no other package; workspace.test.ts > core's only runtime dependency is decimal.js | red (exit 1, 30 tests), as predicted |
| W17 | `tests/fixtures/stray/package-lock.json` | `(new file)` | pytest | test_the_npm_locks_are_the_extension_workspace_alone; test_every_npm_lock_has_its_own_dependabot_update[tests/fixtures/stray/package-lock.json] | red (exit 1, 672 tests), as predicted |
| W18 | `extension/package-lock.json` | `"vitest": "^5.0.3"` | pytest | test_the_exact_peer_pairs_are_the_ones_measured | red (exit 1, 670 tests), as predicted |

## After the merge

1. Read the develop run by name: every gated job green, `deploy-dev` green, its `Verify the attestation` step printing `verified: steadyhand-extension-<sha>.zip sha256:<digest>`, and the run's artifact digest equal to it (`gh api repos/ShydenMcM/steadyhand/actions/runs/<id>/artifacts`).
2. Ask Shyden (AC4) to add `extension` to `develop`'s required status checks; that write is his. Read the protection back.
3. Tell Shyden the TestPyPI environment `testpypi` and its trusted publisher are no longer used; removing them is his choice.
4. Delete the throwaway branch `scratch/220-deploy-probe`.

## Review log

- **Pass 1 (2026-10-06):** replay, controls and a full read. Found and fixed: (1) the gate markers shared a line with prose, so the replay checked no final tree; on their own lines it checks all eight. (2) The red commits took in the untracked `node_modules/` of the tree they were made in; each now adds only its own files. (3) The table filler crashed on a mutation that only removes lines (W1, T12). (4) Task 4's second step was labelled "the red form" while it also deletes two files and edits docstrings; relabelled. (5) Whether `npm ci` installs on Task 2's red form was unmeasured: it does (152 packages, `decimal.js` arriving with the implementation), and the red phase re-run on that install gave the same 37 of 39. Earlier, while building: the first red run showed the build tests as *skipped* (a throwing `beforeAll` skips the file), so the build became lazy and each test fails by name; the red manifests still carried the layer dependencies and scripts, so five tests passed in red until they were taken back; `test_extension_ci.py` read the job at import, so its red run would have died at collection; a looped Dependabot check was caught by `test_one_test_per_case.py` and parametrized; the side panel's three package checks were one looped test and became three; and the self-contained check could not see a `require(` left by an external package, so it now does (mutation T17). The replay control (one planted character) turned five trees red; the filler refused a missing gate line, a failing step and a missing mutation.
- **Pass 2 (2026-10-06):** the plan filled from the logs (gates 1–4 every step 0; 37 of 37 mutations as predicted on the final head `7e9c527`), replayed again to eight identical trees; no placeholder; every test function the prose names is defined in the final tree, and every quoted Vitest title is one the red and mutation logs ran; every mutation id is assigned to the task whose code it mutates (T1–T19 and W1–W6 Task 2, W7–W9, W17, W18 Task 3, W10–W15 Task 4, W16 Task 1). Nothing found. **Approved** (Shyden's rule: plans reviewed to zero, then self-approved).
