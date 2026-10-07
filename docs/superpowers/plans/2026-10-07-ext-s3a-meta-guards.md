# EXT S3a #221 TypeScript Meta-Guards And Recorded Floors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the extension's TypeScript the meta-guards the Python packages already have, before the first feature story: one recorded floors file checked for equality and raised only by a recorder that never runs in CI; one shared reader through which every guard reads source; import direction between the four packages; no browser global and no `number` in `core`; and no literal floor in any TypeScript test. Every guard carries the population it judged, a recorded floor, an independent cross-check, fail-closed parsing and planted forms that go red.

**Architecture:** Everything lives under `extension/tests/`. `tests/lib/` holds the guard libraries, covered at 100% like the packages: `population.ts` (`searched`, the empty-population refusal), `floors.ts` (read, assert, merge and record the floors in `tests/floors.json`), `source.ts` (the one place that calls the TypeScript compiler: parse, nodes, tokens, code text with literals emptied, the pre-scanner, a type-checked program), `walk.ts` (the files under a folder, and the same files as git lists them), `imports.ts`, `core-rules.ts` and `literal-floors.ts`. Each guard's test file asserts over the real tree and over planted samples. `npm run floors:record` (`tests/record-floors.ts`) runs the suite in record mode and raises every floor that grew, printing each delta; Python reads every workflow and asserts nothing in CI runs it.

**Tech Stack:** TypeScript 6.0.3 (its compiler API is the tokenizer and the type checker), Vitest 5.0.3 (`TestRunner.getCurrentTest()` names a floor's owner), Node 24 (`node tests/record-floors.ts` runs TypeScript directly), Python 3.12 and 3.13 for the workflow guard.

**Spec:** `docs/superpowers/specs/2026-10-06-broker-view-extension-design.md` §3, §4.1 and §14.2, and the story #221 with Shyden's two decisions on it (issuecomment-6022943400, issuecomment-6023126439). Builds on `docs/superpowers/plans/2026-10-06-ext-s2-workspace.md`. Every code block below was generated from a commit that passed the whole gate, not typed.

## Global Constraints

- One test per case (`test.each`, never a population looped inside one test); no retries.
- Every guard's absence assertion carries its population inside the verdict (`searched(findings, { of, what })`) and checks that population's recorded floor in the same test, one floor id per test.
- A floor is never a literal in a test: it lives in `tests/floors.json`, checked for equality, raised only by `npm run floors:record`, lowered only by a deliberate edit.
- Every guard reads source through `tests/lib/source.ts` alone; nothing else imports `typescript` or calls its readers.
- 100% coverage on every measure, now including `tests/lib/**`.
- No install script runs: every `npm ci` is `--ignore-scripts`.

## Decisions taken in this plan

Each was settled from a primary source or by Shyden, not assumed.

1. **The no-`number` guard judges all of `core`, by words and by types** (Shyden, #221, both decisions). The written-word reading refuses the `number` keyword in any type position, the `Number` global, `parseFloat` and `parseInt`, and numeric literals with a fraction or exponent; whole literals stay allowed, as Python allows `int`. A type-checker pass then refuses every variable, parameter, property, getter and function result in `packages/core/src` whose type, written or inferred, holds a `number` (a literal type, a union, an array or a type argument), because `const fee = 100` declares a `number` without the word. A callback passed straight to a call has its result exempt and its parameters judged.
2. **AC1's literal floors are the TypeScript tests'.** Python's 29 literal floors (20 files) move to the floors file in #272 (5 points), which depends on this story.
3. **A floor's owner is the runner's current test, never `expect.getState()`.** Measured on 2026-10-06: inside a hook, `expect.getState().currentTestName` still names the test that ran last, so `floors.ts` asks `TestRunner.getCurrentTest()`, which is `undefined` in every hook and makes a floor asserted there a refusal. Vitest 5 has no `vitest/suite` export.
4. **A numeric literal is judged by its source text.** `NumericLiteral.text` is normalised (`1e3` reads `1000`), so `core-rules.ts` reads `getText()`.
5. **An object literal's type is `ObjectFlags.Anonymous` (16), not `ObjectLiteral`** (measured), so the type pass recurses into anonymous object types to judge their fields.
6. **The node walk uses `getChildren()`, which enters JSDoc; `forEachChild` does not.** `ts.preProcessFile` is the import reader's independent cross-check, file by file; it finds the nine syntactic forms the tests plant (the tenth planted case, a relative path into another package, is the first form with a relative specifier).
7. **The `searched` helper #222's AC3 asks for is `tests/lib/population.ts`, built here** because every guard in this story needs it; #222 builds on it rather than adding a second.

## Review Focus

1. **Most future stories move a floor.** `source.files`, `compiler-home.imports`, `compiler-home.uses` and the three `literal-floors.*` floors count over every TypeScript file in `extension/`, so a story adding a test or a module goes red on them until `npm run floors:record` is run and its printed deltas are read against the diff and committed. That is the design (a ratchet both ways), not friction to remove.
2. **Every Dependabot npm PR that changes the lock's package count goes red on `workspace.locked-packages`** until `npm run floors:record` is committed on its branch. Dependabot cannot run it, so such a PR needs a person (or an agent) to record on its branch.
3. **A floor asserted in a hook, or from two tests.** The recorder refuses both by name (mutations F4, F6), as it refuses a recorded id no test asserted any more (F5).
4. **The recorder in CI.** `floorBreach` throws when `CI` is set in record mode (F3), and `tests/meta/test_extension_ci.py` reads every workflow's keys and values and every other npm script (P1-P4).
5. **A test that builds a compiler program costs about half a second.** Measured alone on 2026-10-07: `a file with no error is compiled, and its checker reads its types` 660 ms, the compiler-error case 392 ms. Once, while building Task 4's commit with the machine at load averages 10.6, 19.6 and 23.8 on six cores, it ran past Vitest's 5 s default and timed out; re-run under the lock, it passed. The lock's holder notes then seemed to show another session's heavy run beside this one, but a note outlives its run until a later run has to wait (two dead shells' notes were read back at 00:15 UTC, staggered by 25 s), so the load came from work the test lock does not govern. The timeout is not raised: a test that passes alone in 0.7 s and starves at load 20 is a machine finding, and a timeout in CI would be a code finding.

## The gate

Each task ends green on CI's exact gate, run on its commit: `uv run --locked ruff check`, `ruff format --check`, `mypy`, `pytest -W error --cov` on Python 3.12 and 3.13, the `-m perf` step, and inside `extension/`: `npm ci --ignore-scripts`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`, `npm run build`. Measured results:

- **Task 1:** extension: --ignore-scripts=0 lint=0 format:check=0 typecheck=0 test=0 build=0 :: 62 passed (62) · branches 100%
- **Task 1:** 3a5108d1ea541d803a8909a2b3f5f3aba7f25954 ruff=0 format=0 mypy=0 pytest=0 perf=0 py313=0 :: 2379 passed, 29 deselected in 204.57s (0:03:24)  · coverage 100% · perf 12 passed, 2396 deselected in 17.13s  · py313 2379 passed, 29 deselected in 170.88s (0:02:50) 
- **Task 2:** extension: --ignore-scripts=0 lint=0 format:check=0 typecheck=0 test=0 build=0 :: 120 passed (120) · branches 100%
- **Task 2:** f3095707502f300a28c650255e0002b5d63e77a9 ruff=0 format=0 mypy=0 pytest=0 perf=0 py313=0 :: 2379 passed, 29 deselected in 185.48s (0:03:05)  · coverage 100% · perf 12 passed, 2396 deselected in 18.76s  · py313 2379 passed, 29 deselected in 151.05s (0:02:31) 
- **Task 3:** extension: --ignore-scripts=0 lint=0 format:check=0 typecheck=0 test=0 build=0 :: 179 passed (179) · branches 100%
- **Task 3:** ce77b2f2a3f72e4e22cd0a2d6e5952e9a35e8567 ruff=0 format=0 mypy=0 pytest=0 perf=0 py313=0 :: 2379 passed, 29 deselected in 186.43s (0:03:06)  · coverage 100% · perf 12 passed, 2396 deselected in 16.17s  · py313 2379 passed, 29 deselected in 169.90s (0:02:49) 
- **Task 4:** extension: --ignore-scripts=0 lint=0 format:check=0 typecheck=0 test=0 build=0 :: 270 passed (270) · branches 100%
- **Task 4:** 195defe8671bb62215ce18ecf4e1647dbb00e29c ruff=0 format=0 mypy=0 pytest=0 perf=0 py313=0 :: 2379 passed, 29 deselected in 161.87s (0:02:41)  · coverage 100% · perf 12 passed, 2396 deselected in 21.63s  · py313 2379 passed, 29 deselected in 175.74s (0:02:55) 
- **Task 5:** extension: --ignore-scripts=0 lint=0 format:check=0 typecheck=0 test=0 build=0 :: 353 passed (353) · branches 100%
- **Task 5:** c0e13f87e20abb57063091a5a30b9f5b00560f5b ruff=0 format=0 mypy=0 pytest=0 perf=0 py313=0 :: 2379 passed, 29 deselected in 185.70s (0:03:05)  · coverage 100% · perf 12 passed, 2396 deselected in 17.34s  · py313 2379 passed, 29 deselected in 159.14s (0:02:39) 

## The red phase

Each task writes its tests first, then its libraries in their **red form**: every top-level function's body throws `not implemented: <name>`, and everything else (imports, classes, types, constants) is as the implementation has it; `filesUnder` returns `[]` instead, because tests call it at module level, where a throw fails the whole file at collection rather than each test by name. Files the task changes are as they stood before it (`package.json`, `vitest.config.ts`, `tests/floors.json`). Every new test is run and must fail on its own assertion or on a stub's `not implemented`. A test that passes in red is named with the mutation that proves it. The replay checks that the tests plus the red form equal the tree the red phase was measured on, byte for byte (`<!-- check: red -->`), and that the implementation then equals the story commit (`<!-- check: gate -->`).

## The floors each task records

Each task's `tests/floors.json` below is the file `npm run floors:record` wrote on the task's tree, starting from the previous task's file (from `{}` in Task 1); the recorder printed these lines. Running it again on the finished task prints `no floor moved`, which is how a task confirms its file. Measured:

- **Task 1:** `workspace.locked-packages: new, 198`.
- **Task 2:** `compiler-home.uses: new, 23`, `source.files: new, 24`.
- **Task 3:** `compiler-home.imports: new, 73`, `compiler-home.uses: 23 → 41 (+18)`, `import-direction.files: new, 9`, `import-direction.imports: new, 12`, `source.files: 24 → 26 (+2)`.
- **Task 4:** `browser-globals.identifiers: new, 1`, `compiler-home.imports: 73 → 83 (+10)`, `compiler-home.uses: 41 → 123 (+82)`, `core.files: new, 1`, `number-types.values: new, 1`, `number-words.nodes: new, 7`, `source.files: 26 → 28 (+2)`.
- **Task 5:** `compiler-home.imports: 83 → 90 (+7)`, `compiler-home.uses: 123 → 175 (+52)`, `literal-floors.assertions: new, 135`, `literal-floors.files: new, 20`, `literal-floors.variables: new, 247`, `source.files: 28 → 30 (+2)`.

Each delta reads against its task's diff: `source.files` counts every TypeScript and JavaScript file in `extension/` and rises by the two files a task adds; `compiler-home.imports` counts every import in the workspace and `compiler-home.uses` every `ts` identifier outside `tests/lib/source.ts`, so each rises by what the task's new library and test carry.

---

### Task 1: Recorded floors, the recorder, and the recorder never in CI

**Acceptance criteria (story text):** AC1 (one floors file checked for equality; a recorder that raises, never lowers, prints every delta and never runs in CI), AC5(a) and (b) (the population inside the verdict; a floor at the measured figure).

**Files:**
- Create: `extension/tests/lib/population.ts`, `extension/tests/lib/floors.ts`, `extension/tests/record-floors.ts`, `extension/tests/floors.json`
- Test: `extension/tests/population.test.ts`, `extension/tests/floors.test.ts`; modify `extension/tests/workspace.test.ts` (its literal floor `197` becomes the recorded `workspace.locked-packages`), `tests/meta/test_extension_ci.py`
- Modify: `extension/package.json` (`floors:record`), `extension/vitest.config.ts` (coverage includes `tests/lib/**`)

**Interfaces:**
- Produces: `population.ts`: `BlindGuardError`, `searched<T>(findings: T, { of, what }): T`. `floors.ts`: `FLOORS_PATH`, `RECORD_ENV`, `Floors`, `Measurement`, `parseFloors(text)`, `readFloors(path?)`, `floorBreach(id, measured, env?, floorsPath?) -> string | undefined`, `Merged`, `mergeFloors(recorded, measurements) -> Merged`, `parseMeasurements(text)`, `recordFloors(floorsPath, run, log) -> number`. `npm run floors:record`.

- [ ] **Step 1: Branch.** `git switch -c ext/s3a-meta-guards origin/develop`
- [ ] **Step 2: Write the failing tests.**

**`extension/tests/floors.test.ts`** (new)

<!-- file: extension/tests/floors.test.ts -->
```typescript
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeAll, describe, expect, test } from "vitest";
import {
  FLOORS_PATH,
  floorBreach,
  type Measurement,
  mergeFloors,
  parseFloors,
  parseMeasurements,
  RECORD_ENV,
  readFloors,
  recordFloors,
} from "./lib/floors.ts";

const scratches: string[] = [];

/** A fresh directory for one test, removed after it. */
const scratch = (): string => {
  const directory = mkdtempSync(join(tmpdir(), "steadyhand-floors-test-"));
  scratches.push(directory);
  return directory;
};

afterEach(() => {
  scratches.splice(0).forEach((directory) => {
    rmSync(directory, { recursive: true, force: true });
  });
});

/** A floors file holding `floors`, in a fresh directory. */
const floorsFile = (floors: Record<string, number>): string => {
  const path = join(scratch(), "floors.json");
  writeFileSync(path, `${JSON.stringify(floors, null, 2)}\n`);
  return path;
};

const at = (test: string, id: string, measured: number): Measurement => ({ id, measured, test });

test("the recorded floors file holds whole numbers of zero or more, by id", () => {
  expect(() => readFloors(FLOORS_PATH)).not.toThrow();
});

test.each([
  ["an array", "[1]", "the floors file is not an object of floor ids"],
  ["null", "null", "the floors file is not an object of floor ids"],
  ["a fraction", '{"a.files": 1.5}', "floor a.files: 1.5 is not a whole number of zero or more"],
  ["a negative", '{"a.files": -1}', "floor a.files: -1 is not a whole number of zero or more"],
  ["a string", '{"a.files": "3"}', 'floor a.files: "3" is not a whole number of zero or more'],
])("a floors file holding %s is refused", (_, text, message) => {
  expect(() => parseFloors(text)).toThrow(message);
});

test("a floors file of whole numbers reads as written", () => {
  expect(parseFloors('{"a.files": 0, "b.tests": 12}')).toEqual({ "a.files": 0, "b.tests": 12 });
});

test("a measurement equal to its record breaks nothing", () => {
  expect(floorBreach("a.files", 3, {}, floorsFile({ "a.files": 3 }))).toBeUndefined();
});

test("growth breaks the floor until it is recorded, naming the delta", () => {
  expect(floorBreach("a.files", 4, {}, floorsFile({ "a.files": 3 }))).toBe(
    "floor a.files: measured 4, recorded 3 (+1); read the growth against the diff, then run " +
      "npm run floors:record",
  );
});

test("a loss breaks the floor and says a reader may have gone blind", () => {
  expect(floorBreach("a.files", 2, {}, floorsFile({ "a.files": 3 }))).toBe(
    "floor a.files: measured 2, recorded 3 (-1); a reader may have gone blind to part of its " +
      "population. If it really shrank, lower the figure in tests/floors.json by a deliberate edit",
  );
});

test("an id with no record breaks the floor, naming the recorder", () => {
  expect(floorBreach("a.files", 3, {}, floorsFile({}))).toBe(
    "floor a.files: none recorded, measured 3; run npm run floors:record",
  );
});

test("recording appends the measurement and the test that asserted it, and judges nothing", () => {
  const measurements = join(scratch(), "m.jsonl");
  const floors = floorsFile({ "a.files": 3 });
  expect(floorBreach("a.files", 9, { [RECORD_ENV]: measurements }, floors)).toBeUndefined();
  const [line] = parseMeasurements(readFileSync(measurements, "utf8"));
  expect(line).toMatchObject({ id: "a.files", measured: 9 });
  expect(line?.test).toMatch(
    /^tests\/floors\.test\.ts > recording appends the measurement and the test that asserted it, and judges nothing$/u,
  );
});

test("recording refuses to run in CI, so CI can never pass a floor unjudged", () => {
  const env = { [RECORD_ENV]: join(scratch(), "m.jsonl"), CI: "true" };
  expect(() => floorBreach("a.files", 3, env, floorsFile({}))).toThrow(
    "floors are recorded on a developer's machine, never in CI",
  );
});

/** What recording a floor from a hook does: run before any test, and after one (2026-10-06:
 * there `expect.getState()` still named the test before, so the runner is asked instead). */
const recordFromAHook = (): unknown => {
  try {
    floorBreach("a.files", 3, { [RECORD_ENV]: join(scratch(), "m.jsonl") });
    return undefined;
  } catch (error) {
    return error;
  }
};

const OUTSIDE = new Error(
  "a floor is asserted inside a test, so the recorder can tell who owns it",
);

let fromTheFileHook: unknown;
beforeAll(() => {
  fromTheFileHook = recordFromAHook();
});

test("a floor recorded from a hook before any test is refused", () => {
  expect(fromTheFileHook).toEqual(OUTSIDE);
});

describe("after a test has run", () => {
  let fromASuiteHook: unknown;
  beforeAll(() => {
    fromASuiteHook = recordFromAHook();
  });

  test("a floor recorded from a suite's hook is refused, not credited to the test before", () => {
    expect(fromASuiteHook).toEqual(OUTSIDE);
  });
});

test("the recorder records a new floor", () => {
  expect(mergeFloors({}, [at("t1", "a.files", 3)])).toEqual({
    floors: { "a.files": 3 },
    moved: ["a.files: new, 3"],
    refused: [],
  });
});

test("the recorder raises a floor that grew, printing its delta", () => {
  expect(mergeFloors({ "a.files": 3 }, [at("t1", "a.files", 5)])).toEqual({
    floors: { "a.files": 5 },
    moved: ["a.files: 3 → 5 (+2)"],
    refused: [],
  });
});

test("the recorder leaves an unchanged floor alone and prints nothing for it", () => {
  expect(mergeFloors({ "a.files": 3 }, [at("t1", "a.files", 3)])).toEqual({
    floors: { "a.files": 3 },
    moved: [],
    refused: [],
  });
});

test("the recorder never lowers a floor", () => {
  expect(mergeFloors({ "a.files": 3 }, [at("t1", "a.files", 2)]).refused).toEqual([
    "floor a.files: measured 2, below its record of 3; the recorder never lowers a floor. " +
      "Lower it by a deliberate edit if the population really shrank",
  ]);
});

test("the recorder refuses an id asserted from two places", () => {
  expect(mergeFloors({}, [at("t1", "a.files", 3), at("t2", "a.files", 3)]).refused).toEqual([
    "floor a.files is asserted from 2 places: t1; t2",
  ]);
});

test("the recorder refuses an id measured twice with two figures in one test", () => {
  expect(mergeFloors({}, [at("t1", "a.files", 3), at("t1", "a.files", 4)]).refused).toEqual([
    "floor a.files measured 3 and 4 in one run",
  ]);
});

test("the recorder refuses a recorded id that no test asserts any more", () => {
  expect(mergeFloors({ "a.files": 3, "b.tests": 1 }, [at("t1", "a.files", 3)]).refused).toEqual([
    "floor b.tests is recorded, but no test asserted it; remove it by a deliberate edit",
  ]);
});

test("the recorder writes the floors sorted by id", () => {
  const merged = mergeFloors({}, [at("t1", "b.tests", 1), at("t2", "a.files", 2)]);
  expect(Object.keys(merged.floors)).toEqual(["a.files", "b.tests"]);
  expect(merged.moved).toEqual(["a.files: new, 2", "b.tests: new, 1"]);
});

test("measurements read one JSON object a line", () => {
  const text = `${JSON.stringify(at("t1", "a.files", 3))}\n${JSON.stringify(at("t2", "b", 1))}\n`;
  expect(parseMeasurements(text)).toEqual([at("t1", "a.files", 3), at("t2", "b", 1)]);
});

test("a malformed measurement is refused by its line number", () => {
  expect(() => parseMeasurements('{"id": "a.files", "measured": 1.5, "test": "t1"}\n')).toThrow(
    'measurement 1 is not {id, measured, test}: {"id": "a.files", "measured": 1.5, "test": "t1"}',
  );
});

/** A suite run that writes `measurements` and exits `status`, in place of the real suite. */
const suite =
  (measurements: readonly Measurement[], status = 0) =>
  (path: string): number => {
    writeFileSync(path, measurements.map((m) => `${JSON.stringify(m)}\n`).join(""));
    return status;
  };

test("a recording writes the raised floors and prints each one that moved", () => {
  const path = floorsFile({ "a.files": 3 });
  const lines: string[] = [];
  expect(recordFloors(path, suite([at("t1", "a.files", 4)]), (l) => lines.push(l))).toBe(0);
  expect(readFileSync(path, "utf8")).toBe('{\n  "a.files": 4\n}\n');
  expect(lines).toEqual(["a.files: 3 → 4 (+1)"]);
});

test("a recording where nothing moved says so", () => {
  const path = floorsFile({ "a.files": 3 });
  const lines: string[] = [];
  expect(recordFloors(path, suite([at("t1", "a.files", 3)]), (l) => lines.push(l))).toBe(0);
  expect(lines).toEqual(["no floor moved"]);
});

test("a recording whose suite failed writes nothing", () => {
  const path = floorsFile({ "a.files": 3 });
  const lines: string[] = [];
  expect(recordFloors(path, suite([at("t1", "a.files", 9)], 1), (l) => lines.push(l))).toBe(1);
  expect(readFloors(path)).toEqual({ "a.files": 3 });
  expect(lines).toEqual(["the suite exited 1: nothing recorded"]);
});

test("a recording with a refusal prints it and writes nothing", () => {
  const path = floorsFile({ "a.files": 3 });
  const lines: string[] = [];
  expect(recordFloors(path, suite([at("t1", "a.files", 2)]), (l) => lines.push(l))).toBe(1);
  expect(readFloors(path)).toEqual({ "a.files": 3 });
  expect(lines).toEqual([
    "floor a.files: measured 2, below its record of 3; the recorder never lowers a floor. " +
      "Lower it by a deliberate edit if the population really shrank",
    "nothing recorded",
  ]);
});
```

**`extension/tests/population.test.ts`** (new)

<!-- file: extension/tests/population.test.ts -->
```typescript
import { expect, test } from "vitest";
import { BlindGuardError, searched } from "./lib/population.ts";

test("a verdict over a population of none is refused, naming what was not judged", () => {
  expect(() => searched([], { of: 0, what: "core modules" })).toThrow(
    new BlindGuardError("judged no core modules: an empty finding over nothing proves nothing"),
  );
});

test("a verdict over a population of one or more is the findings themselves", () => {
  const findings = ["line 3: window"];
  expect(searched(findings, { of: 1, what: "core modules" })).toBe(findings);
});

test("the refusal is a BlindGuardError by name", () => {
  expect(new BlindGuardError("x").name).toBe("BlindGuardError");
});
```

**`extension/tests/workspace.test.ts`** (changed: 2 edits)

<!-- edit: extension/tests/workspace.test.ts -->
Replace:
```typescript
import eslint from "../eslint.config.js";
import vitest from "../vitest.config.ts";
```
with:
```typescript
import eslint from "../eslint.config.js";
import { floorBreach } from "./lib/floors.ts";
import vitest from "../vitest.config.ts";
```

<!-- edit: extension/tests/workspace.test.ts -->
Replace:
```typescript
  );
  // Measured on 2026-10-06 (#220): 198 packages fetched, every platform's binaries included.
  // Lower it only by a deliberate edit when the dependencies shrink.
  expect(fetched.length).toBeGreaterThanOrEqual(197);
  const loose = fetched.filter(
```
with:
```typescript
  );
  expect(floorBreach("workspace.locked-packages", fetched.length)).toBeUndefined();
  const loose = fetched.filter(
```

**`tests/meta/test_extension_ci.py`** (changed: 4 edits)

<!-- edit: tests/meta/test_extension_ci.py -->
Replace:
```python
import json
from pathlib import Path
```
with:
```python
import json
from collections.abc import Iterator
from pathlib import Path
```

<!-- edit: tests/meta/test_extension_ci.py -->
Replace:
```python
import yaml

```
with:
```python
import yaml
from population import searched, tracked

```

<!-- edit: tests/meta/test_extension_ci.py -->
Replace:
```python
MANIFEST = ROOT / "extension/package.json"

```
with:
```python
MANIFEST = ROOT / "extension/package.json"
WORKFLOWS = ROOT / ".github/workflows"

# The floors recorder and its record mode (#221): neither may run in CI, or a floor would pass
# unjudged.
RECORDER = ("floors:record", "record-floors", "STEADYHAND_FLOORS_RECORD")

```

<!-- edit: tests/meta/test_extension_ci.py -->
Replace:
```python
    assert manifest().get("engines") == {"node": ">=24"}
```
with:
```python
    assert manifest().get("engines") == {"node": ">=24"}


def strings_in(node: Any) -> Iterator[str]:  # noqa: ANN401 - parsed YAML is untyped
    """Every key and every string value in a parsed workflow: a run line, an env name, an input."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from strings_in(value)
    elif isinstance(node, list):
        for item in node:
            yield from strings_in(item)
    elif isinstance(node, str):
        yield node


def recorder_mentions(workflow: Any) -> list[str]:  # noqa: ANN401 - parsed YAML is untyped
    """Every key or value in *workflow* that names the floors recorder or its record mode."""
    return [text for text in strings_in(workflow) if any(word in text for word in RECORDER)]


@pytest.mark.parametrize(
    "workflow",
    [
        pytest.param({"jobs": {"j": {"steps": [{"run": "npm run floors:record"}]}}}, id="run"),
        pytest.param(
            {"jobs": {"j": {"steps": [{"run": "node tests/record-floors.ts"}]}}}, id="path"
        ),
        pytest.param({"env": {"STEADYHAND_FLOORS_RECORD": "measurements.jsonl"}}, id="env-name"),
    ],
)
def test_the_recorder_is_found_wherever_a_workflow_names_it(workflow: dict[str, Any]) -> None:
    assert len(recorder_mentions(workflow)) == 1


def test_no_workflow_runs_the_floors_recorder() -> None:
    files = sorted([*tracked(WORKFLOWS, ".yml"), *tracked(WORKFLOWS, ".yaml")])
    parsed = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in files]
    read = sum(len(list(strings_in(workflow))) for workflow in parsed)
    found = [text for workflow in parsed for text in recorder_mentions(workflow)]
    assert searched(found, of=read, what="workflow keys and values") == []


def test_no_other_npm_script_reaches_the_floors_recorder() -> None:
    scripts: dict[str, str] = manifest()["scripts"]
    assert scripts.get("floors:record") == "node tests/record-floors.ts"
    others = {name: body for name, body in scripts.items() if name != "floors:record"}
    found = [name for name, body in others.items() if any(word in body for word in RECORDER)]
    assert searched(found, of=len(others), what="npm scripts") == []
```


- [ ] **Step 3: Write the red form.**

**`extension/tests/lib/floors.ts`** (new)

<!-- file: extension/tests/lib/floors.ts -->
```typescript
/**
 * The recorded floors: one measured figure per population a guard judges (spec §14.2).
 *
 * Shyden's rule (2026-10-02): a floor is the measured figure, checked for EQUALITY, so a guard
 * that goes blind to part of its population fails, and so does growth until it is recorded. A
 * floor typed into a test drifts the day after it is measured, so every figure lives in
 * `tests/floors.json`, written only by `npm run floors:record`, which raises a figure and never
 * lowers one, and never runs in CI.
 */
import { appendFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { type RunnerTestCase, TestRunner } from "vitest";

export const FLOORS_PATH = join(import.meta.dirname, "..", "floors.json");

/** Set by the recorder only: each floor then appends its measurement here instead of judging. */
export const RECORD_ENV = "STEADYHAND_FLOORS_RECORD";

export type Floors = Readonly<Record<string, number>>;

/** One floor measured while recording, with the test that asserted it. */
export interface Measurement {
  id: string;
  measured: number;
  test: string;
}

/** The floors in `text`; anything but whole numbers of zero or more is refused by id. */
export const parseFloors = (text: string): Floors => {
  throw new Error("not implemented: parseFloors");
};

export const readFloors = (path: string = FLOORS_PATH): Floors => {
  throw new Error("not implemented: readFloors");
};

/**
 * The test asserting a floor right now, by its full name; a floor asserted outside a test is
 * refused. Measured on 2026-10-06: inside a hook, `expect.getState()` still names the test that
 * ran last, so the runner's own current test is asked instead, which is `undefined` in a hook.
 */
const currentTest = (): string => {
  throw new Error("not implemented: currentTest");
};

/**
 * Why `measured` breaks floor `id`, or `undefined` when it equals the recorded figure. Use it as
 * `expect(floorBreach(id, population.length)).toBeUndefined()`, in the test whose search judged
 * that population.
 */
export const floorBreach = (
  id: string,
  measured: number,
  env: Readonly<Record<string, string | undefined>> = process.env,
  floorsPath: string = FLOORS_PATH,
): string | undefined => {
  throw new Error("not implemented: floorBreach");
};

/** What the recorder would write, every floor that moved, and every reason to write nothing. */
export interface Merged {
  floors: Record<string, number>;
  moved: string[];
  refused: string[];
}

/**
 * The floors after `measurements`: a figure rises to its measurement and never falls. An id
 * asserted by two tests, a figure measured below its record, and a recorded id no test asserted
 * any more are refused, because each is a decision for a person, not the recorder.
 */
export const mergeFloors = (recorded: Floors, measurements: readonly Measurement[]): Merged => {
  throw new Error("not implemented: mergeFloors");
};

/** The measurements one recording run wrote, one JSON object a line; a malformed line is refused. */
export const parseMeasurements = (text: string): Measurement[] => {
  throw new Error("not implemented: parseMeasurements");
};

/**
 * One recording: run the suite with `RECORD_ENV` set, then write the raised floors, or nothing.
 * `run` takes the measurements path and returns the suite's exit status. The recorder never
 * runs in CI, so its own test passes a run that writes measurements instead of the real suite.
 * Returns the recorder's exit status.
 */
export const recordFloors = (
  floorsPath: string,
  run: (measurementsPath: string) => number,
  log: (line: string) => void,
): number => {
  throw new Error("not implemented: recordFloors");
};
```

**`extension/tests/lib/population.ts`** (new)

<!-- file: extension/tests/lib/population.ts -->
```typescript
/**
 * What a guard proves it saw, for the guards that can pass by finding nothing (spec §14.2).
 *
 * Shyden's rule (2026-10-02): such a guard proves what it inspected, counted at the level it
 * judges. `searched` puts that count inside the verdict, so an empty finding never stands alone.
 * The Python guards' `tests/meta/population.py` is its twin.
 */

/** A verdict over a population of none: it says nothing, so it is refused. */
export class BlindGuardError extends Error {
  override name = "BlindGuardError";
}

/** `findings`, once `of` members of the population (`what`) were judged. */
export const searched = <T>(findings: T, { of, what }: { of: number; what: string }): T => {
  throw new Error("not implemented: searched");
};
```


- [ ] **Step 4: Watch them fail.** `npx vitest run` inside `extension/`, then `uv run pytest -p no:cacheprovider tests/meta/test_extension_ci.py`. Measured: 33 of 38 new tests fail. The vitest ones fail on a stub (`Error: not implemented: mergeFloors` 8, `floorBreach` 6, `recordFloors` 4, `searched`, `parseFloors`, `parseMeasurements`) or on their own assertion where they expect a refusal and get the stub's error instead (`expected [Function] to throw error including 'the floors file is…'`); the converted `workspace.test.ts` case fails on `not implemented: floorBreach`; the Python case for npm scripts fails on `assert None == 'node tests/record-floors.ts'`. Five pass, as they must on this tree: `the refusal is a BlindGuardError by name` (the class is kept in the red form; mutation F7), and four Python cases whose detector is the test file itself, `test_the_recorder_is_found_wherever_a_workflow_names_it[env-name|path|run]` and `test_no_workflow_runs_the_floors_recorder` (mutations P2, P1, P1, P3).

<!-- check: red -->

- [ ] **Step 5: Implement.**

**`extension/package.json`** (changed: 1 edit)

<!-- edit: extension/package.json -->
Replace:
```json
    "test": "vitest run --coverage",
    "build": "node build.ts"
  },
```
with:
```json
    "test": "vitest run --coverage",
    "build": "node build.ts",
    "floors:record": "node tests/record-floors.ts"
  },
```

**`extension/tests/floors.json`** (new)

<!-- file: extension/tests/floors.json -->
```json
{
  "workspace.locked-packages": 198
}
```

**`extension/tests/lib/floors.ts`** (changed: 5 edits)

<!-- edit: extension/tests/lib/floors.ts -->
Replace:
```typescript
export const parseFloors = (text: string): Floors => {
  throw new Error("not implemented: parseFloors");
};

export const readFloors = (path: string = FLOORS_PATH): Floors => {
  throw new Error("not implemented: readFloors");
};

```
with:
```typescript
export const parseFloors = (text: string): Floors => {
  const parsed: unknown = JSON.parse(text);
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("the floors file is not an object of floor ids");
  }
  for (const [id, figure] of Object.entries(parsed)) {
    if (!Number.isSafeInteger(figure) || (figure as number) < 0) {
      throw new Error(
        `floor ${id}: ${JSON.stringify(figure)} is not a whole number of zero or more`,
      );
    }
  }
  return parsed as Floors;
};

export const readFloors = (path: string = FLOORS_PATH): Floors =>
  parseFloors(readFileSync(path, "utf8"));

```

<!-- edit: extension/tests/lib/floors.ts -->
Replace:
```typescript
const currentTest = (): string => {
  throw new Error("not implemented: currentTest");
};
```
with:
```typescript
const currentTest = (): string => {
  const running = TestRunner.getCurrentTest<RunnerTestCase | undefined>();
  if (running === undefined) {
    throw new Error("a floor is asserted inside a test, so the recorder can tell who owns it");
  }
  return running.fullName;
};
```

<!-- edit: extension/tests/lib/floors.ts -->
Replace:
```typescript
): string | undefined => {
  throw new Error("not implemented: floorBreach");
};
```
with:
```typescript
): string | undefined => {
  const recording = env[RECORD_ENV];
  if (recording !== undefined) {
    if (env.CI !== undefined) {
      throw new Error("floors are recorded on a developer's machine, never in CI");
    }
    const line: Measurement = { id, measured, test: currentTest() };
    appendFileSync(recording, `${JSON.stringify(line)}\n`);
    return undefined;
  }
  const recorded = readFloors(floorsPath)[id];
  if (recorded === undefined) {
    return `floor ${id}: none recorded, measured ${String(measured)}; run npm run floors:record`;
  }
  if (measured > recorded) {
    return (
      `floor ${id}: measured ${String(measured)}, recorded ${String(recorded)} (+${String(measured - recorded)}); ` +
      "read the growth against the diff, then run npm run floors:record"
    );
  }
  if (measured < recorded) {
    return (
      `floor ${id}: measured ${String(measured)}, recorded ${String(recorded)} (${String(measured - recorded)}); ` +
      "a reader may have gone blind to part of its population. If it really shrank, lower " +
      "the figure in tests/floors.json by a deliberate edit"
    );
  }
  return undefined;
};
```

<!-- edit: extension/tests/lib/floors.ts -->
Replace:
```typescript
export const mergeFloors = (recorded: Floors, measurements: readonly Measurement[]): Merged => {
  throw new Error("not implemented: mergeFloors");
};

/** The measurements one recording run wrote, one JSON object a line; a malformed line is refused. */
export const parseMeasurements = (text: string): Measurement[] => {
  throw new Error("not implemented: parseMeasurements");
};

```
with:
```typescript
export const mergeFloors = (recorded: Floors, measurements: readonly Measurement[]): Merged => {
  const byId = new Map<string, Measurement[]>();
  for (const measurement of measurements) {
    byId.set(measurement.id, [...(byId.get(measurement.id) ?? []), measurement]);
  }
  const floors: Record<string, number> = { ...recorded };
  const moved: string[] = [];
  const refused: string[] = [];
  for (const [id, found] of [...byId].sort(([a], [b]) => a.localeCompare(b))) {
    const tests = [...new Set(found.map((m) => m.test))];
    const figures = [...new Set(found.map((m) => m.measured))];
    const figure = Math.max(...figures);
    const before = recorded[id];
    if (tests.length > 1) {
      refused.push(
        `floor ${id} is asserted from ${String(tests.length)} places: ${tests.join("; ")}`,
      );
    } else if (figures.length > 1) {
      refused.push(`floor ${id} measured ${figures.join(" and ")} in one run`);
    } else if (before === undefined) {
      moved.push(`${id}: new, ${String(figure)}`);
      floors[id] = figure;
    } else if (figure > before) {
      moved.push(`${id}: ${String(before)} → ${String(figure)} (+${String(figure - before)})`);
      floors[id] = figure;
    } else if (figure < before) {
      refused.push(
        `floor ${id}: measured ${String(figure)}, below its record of ${String(before)}; the recorder never ` +
          "lowers a floor. Lower it by a deliberate edit if the population really shrank",
      );
    }
  }
  for (const id of Object.keys(recorded).filter((known) => !byId.has(known))) {
    refused.push(
      `floor ${id} is recorded, but no test asserted it; remove it by a deliberate edit`,
    );
  }
  const sorted = Object.fromEntries(Object.entries(floors).sort(([a], [b]) => a.localeCompare(b)));
  return { floors: sorted, moved, refused };
};

/** The measurements one recording run wrote, one JSON object a line; a malformed line is refused. */
export const parseMeasurements = (text: string): Measurement[] =>
  text
    .split("\n")
    .filter((line) => line !== "")
    .map((line, index) => {
      const parsed = JSON.parse(line) as Partial<Measurement>;
      if (
        typeof parsed.id !== "string" ||
        !Number.isSafeInteger(parsed.measured) ||
        typeof parsed.test !== "string"
      ) {
        throw new Error(`measurement ${String(index + 1)} is not {id, measured, test}: ${line}`);
      }
      return parsed as Measurement;
    });

```

<!-- edit: extension/tests/lib/floors.ts -->
Replace:
```typescript
): number => {
  throw new Error("not implemented: recordFloors");
};
```
with:
```typescript
): number => {
  const scratch = mkdtempSync(join(tmpdir(), "steadyhand-floors-"));
  try {
    const measurementsPath = join(scratch, "measurements.jsonl");
    writeFileSync(measurementsPath, "");
    const status = run(measurementsPath);
    if (status !== 0) {
      log(`the suite exited ${String(status)}: nothing recorded`);
      return 1;
    }
    const merged = mergeFloors(
      readFloors(floorsPath),
      parseMeasurements(readFileSync(measurementsPath, "utf8")),
    );
    if (merged.refused.length > 0) {
      merged.refused.forEach((reason) => {
        log(reason);
      });
      log("nothing recorded");
      return 1;
    }
    writeFileSync(floorsPath, `${JSON.stringify(merged.floors, null, 2)}\n`);
    (merged.moved.length > 0 ? merged.moved : ["no floor moved"]).forEach((line) => {
      log(line);
    });
    return 0;
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
};
```

**`extension/tests/lib/population.ts`** (changed: 1 edit)

<!-- edit: extension/tests/lib/population.ts -->
Replace:
```typescript
export const searched = <T>(findings: T, { of, what }: { of: number; what: string }): T => {
  throw new Error("not implemented: searched");
};
```
with:
```typescript
export const searched = <T>(findings: T, { of, what }: { of: number; what: string }): T => {
  if (of < 1) {
    throw new BlindGuardError(`judged no ${what}: an empty finding over nothing proves nothing`);
  }
  return findings;
};
```

**`extension/tests/record-floors.ts`** (new)

<!-- file: extension/tests/record-floors.ts -->
```typescript
/**
 * `npm run floors:record`: run the whole suite in record mode, then raise each floor that grew,
 * printing every one that moved with its delta. It never lowers a floor and never runs in CI
 * (`tests/meta/test_extension_ci.py` reads every workflow and asserts it).
 */
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { FLOORS_PATH, RECORD_ENV, recordFloors } from "./lib/floors.ts";

const VITEST = join(import.meta.dirname, "..", "node_modules", "vitest", "vitest.mjs");

process.exitCode = recordFloors(
  FLOORS_PATH,
  (measurementsPath) =>
    spawnSync(process.execPath, [VITEST, "run"], {
      stdio: "inherit",
      env: { ...process.env, [RECORD_ENV]: measurementsPath },
    }).status ?? 1,
  (line) => {
    console.log(line);
  },
);
```

**`extension/vitest.config.ts`** (changed: 1 edit)

<!-- edit: extension/vitest.config.ts -->
Replace:
```typescript
      provider: "v8",
      include: COVERED.map((name) => `packages/${name}/src/**/*.ts`),
      reporter: ["text"],
```
with:
```typescript
      provider: "v8",
      include: [...COVERED.map((name) => `packages/${name}/src/**/*.ts`), "tests/lib/**/*.ts"],
      reporter: ["text"],
```


- [ ] **Step 6: Confirm the floors and run the gate.** `cd extension && npm run floors:record` prints `no floor moved` (the file above was recorded from `{}`: `workspace.locked-packages: new, 198`); then the gate.

<!-- check: gate -->

- [ ] **Step 7: Commit** `feat(extension): #221 recorded floors, the recorder, and the recorder never in CI (Refs #221)`.

### Task 2: One source reader and type checker, the git-listed walk, one home for the compiler's readers

**Acceptance criteria (story text):** AC2 (one shared tokenizer; a forbidden name planted in a comment, a string, a template and a regex literal is not read as code, and one planted in code after each is), AC5(c) and (d) (a cross-check counting the same population another way; fail-closed parsing).

**Files:**
- Create: `extension/tests/lib/source.ts`, `extension/tests/lib/walk.ts`
- Test: `extension/tests/source.test.ts`
- Modify: `extension/tests/floors.json`

**Interfaces:**
- Produces: `source.ts`: `ts` (the compiler, re-exported), `EXTENSION`, `UnreadableSourceError`, `parse(text, fileName) -> ts.SourceFile` (refuses a syntax error by name, line and column, and a file that is neither TypeScript nor JavaScript), `readSource(path)`, `lineOf(file, node)`, `nodes(file)`, `tokens(file)`, `codeText(file)` (literals emptied, code kept), `typeChecked(paths, configPath?) -> { checker, files }` (refuses a config it cannot read, a config with an error, a path the program did not compile and a file with a compiler error, each by name). `walk.ts`: `filesUnder(directory, suffixes)`, `gitListed(directory, suffixes)`.

- [ ] **Step 1: Write the failing tests.**

**`extension/tests/source.test.ts`** (new)

<!-- file: extension/tests/source.test.ts -->
```typescript
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test } from "vitest";
import { floorBreach } from "./lib/floors.ts";
import { searched } from "./lib/population.ts";
import {
  codeText,
  lineOf,
  nodes,
  parse,
  readSource,
  tokens,
  ts,
  typeChecked,
  UnreadableSourceError,
} from "./lib/source.ts";
import { filesUnder, gitListed } from "./lib/walk.ts";

/** Every source file of the workspace a guard may read: TypeScript and JavaScript, tests too. */
const SUFFIXES = [".ts", ".js"] as const;
const FILES = filesUnder(".", SUFFIXES);

/** Where a name is NOT code (AC2): each way the workspace writes a comment, string or regex. */
const CARRIERS: readonly (readonly [string, string])[] = [
  ["a line comment", "// window\n"],
  ["a block comment", "/* window */"],
  ["a JSDoc comment", "/** @param window the page */"],
  ["a double-quoted string", '"window";'],
  ["a single-quoted string", "'window';"],
  ["a template", "`window`;"],
  ["a template's text around a substitution", "`window ${0} window`;"],
  ["a regex literal", "/window/u;"],
  ["a regex holding a slash in a character class", "/[/]window/u;"],
  ["a regex literal after a return", "() => { return /window/u; };"],
];

/** The identifiers named `window` the parse tree reads in `text`. */
const windowsRead = (text: string): number =>
  nodes(parse(text, "sample.ts")).filter((node) => ts.isIdentifier(node) && node.text === "window")
    .length;

/** The times `window` stands as a word in `text`'s code text. */
const windowsInCodeText = (text: string): number =>
  codeText(parse(text, "sample.ts"))
    .split(" ")
    .filter((word) => word === "window").length;

test.each(CARRIERS)("a name inside %s is not read as code", (_, carrier) => {
  expect(windowsRead(carrier)).toBe(0);
  expect(windowsInCodeText(carrier)).toBe(0);
});

test.each(CARRIERS)("a name in code after %s is read as code", (_, carrier) => {
  expect(windowsRead(`${carrier}\nwindow;`)).toBe(1);
  expect(windowsInCodeText(`${carrier}\nwindow;`)).toBe(1);
});

test("a name inside a template's substitution is code", () => {
  expect(windowsRead("`text ${window} text`;")).toBe(1);
  expect(windowsInCodeText("`text ${window} text`;")).toBe(1);
});

test("code text empties every literal and keeps the code around it", () => {
  const file = parse('const a = "x" + `y ${b} z` + /w/u; // c\n', "sample.ts");
  expect(codeText(file)).toBe('const a = "" + `${ b }` + /(?:)/ ;');
});

test("a file with a syntax error is refused by name, line and column", () => {
  expect(() => parse("const = 1;\n", "broken.ts")).toThrow(
    new UnreadableSourceError(
      "broken.ts(1,7): error TS1134: Variable declaration expected.\n" +
        "broken.ts(1,9): error TS1134: Variable declaration expected.",
    ),
  );
});

test("a file that is neither TypeScript nor JavaScript is refused by name", () => {
  expect(() => parse("# notes\n", "notes.md")).toThrow(
    new UnreadableSourceError("notes.md: not a TypeScript or JavaScript file"),
  );
});

test("the refusal is an UnreadableSourceError by name", () => {
  expect(new UnreadableSourceError("x").name).toBe("UnreadableSourceError");
});

test("JavaScript is read as JavaScript", () => {
  expect(codeText(parse("export const a = 1;\n", "sample.mjs"))).toBe("export const a = 1 ;");
});

test("a node's line is counted from 1", () => {
  const file = parse("\n\nwindow;\n", "sample.ts");
  const [found] = nodes(file).filter(ts.isIdentifier);
  expect(found === undefined ? 0 : lineOf(file, found)).toBe(3);
});

/** Write `files` into a fresh directory, run `check` on their paths and the directory, then remove it. */
const inScratch = <T>(
  files: Readonly<Record<string, string>>,
  check: (paths: string[], scratch: string) => T,
): T => {
  const scratch = mkdtempSync(join(tmpdir(), "steadyhand-source-"));
  try {
    const paths = Object.entries(files).map(([name, text]) => {
      const path = join(scratch, name);
      writeFileSync(path, text);
      return path;
    });
    return check(paths, scratch);
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
};

test("a file with no error is compiled, and its checker reads its types", () => {
  inScratch({ "fine.ts": 'export const name = "x";\n' }, (paths) => {
    const { checker, files } = typeChecked(paths);
    expect(files.map(({ fileName }) => fileName)).toEqual(paths);
    const declared = files.flatMap((file) => nodes(file).filter(ts.isVariableDeclaration));
    expect(
      declared.map(({ name }) => checker.typeToString(checker.getTypeAtLocation(name))),
    ).toEqual(['"x"']);
  });
});

test("a file with a compiler error is refused by name, not judged", () => {
  inScratch({ "broken.ts": "export const a: string = 1;\n" }, (paths) => {
    expect(() => typeChecked(paths)).toThrow(
      /broken\.ts\(1,14\): error TS2322: Type 'number' is not assignable to type 'string'\./u,
    );
  });
});

test("a path the program did not compile is refused by name", () => {
  const missing = join(tmpdir(), "steadyhand-no-such-dir", "missing.ts");
  expect(() => typeChecked([missing])).toThrow(
    new UnreadableSourceError(`${missing}: not compiled`),
  );
});

test("a config that cannot be read is refused by name", () => {
  expect(() => typeChecked([], join(tmpdir(), "steadyhand-no-such-dir", "tsconfig.json"))).toThrow(
    /error TS5083: Cannot read file '.*steadyhand-no-such-dir\/tsconfig\.json'\./u,
  );
});

test("a config with an error is refused by name", () => {
  inScratch({ "tsconfig.json": '{ "compilerOptions": { "strictest": true } }\n' }, (_, scratch) => {
    expect(() => typeChecked([], join(scratch, "tsconfig.json"))).toThrow(
      /error TS5025: Unknown compiler option 'strictest'\. Did you mean 'strict'\?/u,
    );
  });
});

test("the files read are the ones git lists, and as many as recorded", () => {
  expect(FILES).toEqual(gitListed(".", SUFFIXES));
  expect(floorBreach("source.files", FILES.length)).toBeUndefined();
});

/** The kinds both walks reach: names, literals and type keywords, not punctuation. */
const CROSS_CHECKED = [
  ts.SyntaxKind.Identifier,
  ts.SyntaxKind.PrivateIdentifier,
  ts.SyntaxKind.StringLiteral,
  ts.SyntaxKind.NumericLiteral,
  ts.SyntaxKind.BigIntLiteral,
  ts.SyntaxKind.NoSubstitutionTemplateLiteral,
  ts.SyntaxKind.TemplateHead,
  ts.SyntaxKind.TemplateMiddle,
  ts.SyntaxKind.TemplateTail,
  ts.SyntaxKind.RegularExpressionLiteral,
  ts.SyntaxKind.NumberKeyword,
];

/** How many of each cross-checked kind `found` holds, by kind name. */
const tally = (found: readonly ts.Node[]): Record<string, number> =>
  Object.fromEntries(
    CROSS_CHECKED.map((kind) => [
      ts.SyntaxKind[kind],
      found.filter((node) => node.kind === kind).length,
    ]),
  );

test.each(FILES)("%s: the node walk and the token walk read the same names", (path) => {
  const file = readSource(path);
  expect(tally(nodes(file))).toEqual(tally(tokens(file)));
});

/** The compiler's own readers: called anywhere but `source.ts`, a guard would read source its own way. */
const READERS = new Set([
  "createSourceFile",
  "createScanner",
  "createProgram",
  "createLanguageService",
  "transpileModule",
  "preProcessFile",
]);

/** How `node`, an identifier named `ts`, is used: `ts.<name>`, a plain import, or another way. */
const useOf = (node: ts.Identifier): string => {
  const { parent } = node;
  if (ts.isPropertyAccessExpression(parent) && parent.expression === node) {
    return `ts.${parent.name.text}`;
  }
  if (ts.isQualifiedName(parent) && parent.left === node) {
    return `ts.${parent.right.text}`;
  }
  if (ts.isImportSpecifier(parent) && parent.propertyName === undefined) {
    return "import";
  }
  return "another way";
};

test("only tests/lib/source.ts calls the compiler's readers, and ts is reached only as ts.X", () => {
  const uses = FILES.filter((path) => path !== "tests/lib/source.ts").flatMap((path) => {
    const file = readSource(path);
    return nodes(file)
      .filter((node): node is ts.Identifier => ts.isIdentifier(node) && node.text === "ts")
      .map((node) => ({ path, line: lineOf(file, node), use: useOf(node) }));
  });
  const found = uses
    .filter(({ use }) => use === "another way" || READERS.has(use.slice("ts.".length)))
    .map(({ path, line, use }) => `${path} line ${String(line)}: ${use}`);
  expect(searched(found, { of: uses.length, what: "uses of ts" })).toEqual([]);
  expect(floorBreach("compiler-home.uses", uses.length)).toBeUndefined();
});
```


- [ ] **Step 2: Write the red form.**

**`extension/tests/lib/source.ts`** (new)

<!-- file: extension/tests/lib/source.ts -->
```typescript
/**
 * The one way a guard reads source (spec §14.2, Shyden's source-text rule): the TypeScript
 * compiler's own parse tree, so a name inside a comment, a string, a template's text or a regex
 * literal is never read as code. A hand-written stripper gets regex literals and template
 * substitutions wrong in exactly the places a guard looks, so no guard strips text itself. This
 * module is the only one that imports the compiler (a guard checks it); guards take `ts` from here.
 */
import { readFileSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import ts from "typescript";

export { ts };

/** The workspace's root, `extension/`: every path a guard reports is relative to it. */
export const EXTENSION = join(import.meta.dirname, "..", "..");

/** A file the reader cannot classify, refused by name rather than skipped. */
export class UnreadableSourceError extends Error {
  override name = "UnreadableSourceError";
}

const KINDS: Readonly<Record<string, ts.ScriptKind>> = {
  ".ts": ts.ScriptKind.TS,
  ".mts": ts.ScriptKind.TS,
  ".cts": ts.ScriptKind.TS,
  ".js": ts.ScriptKind.JS,
  ".mjs": ts.ScriptKind.JS,
  ".cjs": ts.ScriptKind.JS,
};

const FORMAT: ts.FormatDiagnosticsHost = {
  getCanonicalFileName: (name) => name,
  getCurrentDirectory: () => EXTENSION,
  getNewLine: () => "\n",
};

/** The parse tree of `text`; a file of another kind or with a syntax error is refused by name. */
export const parse = (text: string, fileName: string): ts.SourceFile => {
  throw new Error("not implemented: parse");
};

/** The parse tree of the file at `path`, relative to `extension/`. */
export const readSource = (path: string): ts.SourceFile => {
  throw new Error("not implemented: readSource");
};

/** The line `node` starts on, counted from 1. */
export const lineOf = (file: ts.SourceFile, node: ts.Node): number => {
  throw new Error("not implemented: lineOf");
};

/** Every node of `file`, depth first, by the compiler's child walk: the walk every guard judges. */
export const nodes = (file: ts.SourceFile): ts.Node[] => {
  throw new Error("not implemented: nodes");
};

const isJSDoc = (node: ts.Node): boolean => {
  throw new Error("not implemented: isJSDoc");
};

/**
 * Every token of `file` in order, read through the tree's token lists (`getChildren`), JSDoc and
 * the end-of-file token left out: a second walk, independent of `nodes`, that cross-checks it.
 */
export const tokens = (file: ts.SourceFile): ts.Node[] => {
  throw new Error("not implemented: tokens");
};

/** What each literal's content becomes in `codeText`, so a name inside one is never code. */
const BLANKED: Partial<Record<ts.SyntaxKind, string>> = {
  [ts.SyntaxKind.StringLiteral]: '""',
  [ts.SyntaxKind.NoSubstitutionTemplateLiteral]: "``",
  [ts.SyntaxKind.TemplateHead]: "`${",
  [ts.SyntaxKind.TemplateMiddle]: "}${",
  [ts.SyntaxKind.TemplateTail]: "}`",
  [ts.SyntaxKind.RegularExpressionLiteral]: "/(?:)/",
};

/**
 * `file`'s code as text, one space between tokens, with every comment removed and every string,
 * template text and regex literal emptied: the text an independent cross-check counts in.
 */
export const codeText = (file: ts.SourceFile): string => {
  throw new Error("not implemented: codeText");
};

/**
 * The type checker over `paths` (relative to `extension/`, or absolute), compiled with the
 * workspace's own `tsconfig.json`. A config that cannot be read, a path the program did not
 * compile and a file with any compiler error are refused by name: types inferred around an error
 * are not the types the code has.
 */
export const typeChecked = (
  paths: readonly string[],
  configPath: string = join(EXTENSION, "tsconfig.json"),
): { checker: ts.TypeChecker; files: ts.SourceFile[] } => {
  throw new Error("not implemented: typeChecked");
};
```

**`extension/tests/lib/walk.ts`** (new)

<!-- file: extension/tests/lib/walk.ts -->
```typescript
/**
 * The files a guard judges, found two ways: walked on disk, and listed by git. A guard asserts the
 * two are equal, so a walk that narrows (a folder left out, one suffix missed) fails by name.
 */
import { execFileSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { join, sep } from "node:path";
import { EXTENSION } from "./source.ts";

/** Folders the build and the tools write, never source. */
const SKIPPED = new Set(["node_modules", "dist", "coverage"]);

const named = (path: string, suffixes: readonly string[]): boolean => {
  throw new Error("not implemented: named");
};

/** Every file under `directory` (relative to `extension/`) whose name ends in one of `suffixes`. */
export const filesUnder = (directory: string, suffixes: readonly string[]): string[] => {
  return [];
};

/** The same files as git lists them, independent of the walk. */
export const gitListed = (directory: string, suffixes: readonly string[]): string[] => {
  throw new Error("not implemented: gitListed");
};
```


- [ ] **Step 3: Watch them fail.** `npx vitest run tests/source.test.ts`. Measured: 33 of 34 new tests fail: 24 on `Error: not implemented: parse`, one each on `typeChecked` and `gitListed`, the compiler-home case on `BlindGuardError: judged no uses of ts` (`filesUnder` returns `[]` in red), and the refusal cases on their own assertion, each getting the stub's error where it expects its refusal (`expected [Function] to throw error matching /error TS5083: …/ but got 'not implemented: typeChecked'`). One passes, as it must: `the refusal is an UnreadableSourceError by name` (the class is kept; mutation S6).

<!-- check: red -->

- [ ] **Step 4: Implement.**

**`extension/tests/floors.json`** (changed: 1 edit)

<!-- edit: extension/tests/floors.json -->
Replace:
```json
{
  "workspace.locked-packages": 198
```
with:
```json
{
  "compiler-home.uses": 23,
  "source.files": 24,
  "workspace.locked-packages": 198
```

**`extension/tests/lib/source.ts`** (changed: 4 edits)

<!-- edit: extension/tests/lib/source.ts -->
Replace:
```typescript
export const parse = (text: string, fileName: string): ts.SourceFile => {
  throw new Error("not implemented: parse");
};

/** The parse tree of the file at `path`, relative to `extension/`. */
export const readSource = (path: string): ts.SourceFile => {
  throw new Error("not implemented: readSource");
};

/** The line `node` starts on, counted from 1. */
export const lineOf = (file: ts.SourceFile, node: ts.Node): number => {
  throw new Error("not implemented: lineOf");
};

/** Every node of `file`, depth first, by the compiler's child walk: the walk every guard judges. */
export const nodes = (file: ts.SourceFile): ts.Node[] => {
  throw new Error("not implemented: nodes");
};

const isJSDoc = (node: ts.Node): boolean => {
  throw new Error("not implemented: isJSDoc");
};

```
with:
```typescript
export const parse = (text: string, fileName: string): ts.SourceFile => {
  const kind = KINDS[extname(fileName)];
  if (kind === undefined) {
    throw new UnreadableSourceError(`${fileName}: not a TypeScript or JavaScript file`);
  }
  const { diagnostics = [] } = ts.transpileModule(text, { fileName, reportDiagnostics: true });
  if (diagnostics.length > 0) {
    throw new UnreadableSourceError(ts.formatDiagnostics(diagnostics, FORMAT).trim());
  }
  return ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true, kind);
};

/** The parse tree of the file at `path`, relative to `extension/`. */
export const readSource = (path: string): ts.SourceFile =>
  parse(readFileSync(join(EXTENSION, path), "utf8"), path);

/** The line `node` starts on, counted from 1. */
export const lineOf = (file: ts.SourceFile, node: ts.Node): number =>
  file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1;

/** Every node of `file`, depth first, by the compiler's child walk: the walk every guard judges. */
export const nodes = (file: ts.SourceFile): ts.Node[] => {
  const found: ts.Node[] = [];
  const visit = (node: ts.Node): void => {
    found.push(node);
    ts.forEachChild(node, visit);
  };
  ts.forEachChild(file, visit);
  return found;
};

const isJSDoc = (node: ts.Node): boolean =>
  node.kind >= ts.SyntaxKind.FirstJSDocNode && node.kind <= ts.SyntaxKind.LastJSDocNode;

```

<!-- edit: extension/tests/lib/source.ts -->
Replace:
```typescript
export const tokens = (file: ts.SourceFile): ts.Node[] => {
  throw new Error("not implemented: tokens");
};
```
with:
```typescript
export const tokens = (file: ts.SourceFile): ts.Node[] => {
  const found: ts.Node[] = [];
  const visit = (node: ts.Node): void => {
    if (isJSDoc(node)) {
      return;
    }
    const children = node.getChildren(file);
    if (children.length > 0) {
      children.forEach(visit);
    } else if (node.kind <= ts.SyntaxKind.LastToken && node.kind !== ts.SyntaxKind.EndOfFileToken) {
      found.push(node);
    }
  };
  visit(file);
  return found;
};
```

<!-- edit: extension/tests/lib/source.ts -->
Replace:
```typescript
 */
export const codeText = (file: ts.SourceFile): string => {
  throw new Error("not implemented: codeText");
};

```
with:
```typescript
 */
export const codeText = (file: ts.SourceFile): string =>
  tokens(file)
    .map((token) => BLANKED[token.kind] ?? token.getText(file))
    .join(" ");

```

<!-- edit: extension/tests/lib/source.ts -->
Replace:
```typescript
): { checker: ts.TypeChecker; files: ts.SourceFile[] } => {
  throw new Error("not implemented: typeChecked");
};
```
with:
```typescript
): { checker: ts.TypeChecker; files: ts.SourceFile[] } => {
  let unreadable = `${configPath}: not read`;
  const config = ts.getParsedCommandLineOfConfigFile(configPath, undefined, {
    ...ts.sys,
    onUnRecoverableConfigFileDiagnostic: (diagnostic) => {
      unreadable = ts.formatDiagnostics([diagnostic], FORMAT).trim();
    },
  });
  if (config === undefined) {
    throw new UnreadableSourceError(unreadable);
  }
  if (config.errors.length > 0) {
    throw new UnreadableSourceError(ts.formatDiagnostics(config.errors, FORMAT).trim());
  }
  const roots = paths.map((path) => resolve(EXTENSION, path));
  const program = ts.createProgram(roots, config.options);
  const files = roots.map((root) => {
    const file = program.getSourceFile(root);
    if (file === undefined) {
      throw new UnreadableSourceError(`${root}: not compiled`);
    }
    const errors = [
      ...program.getSyntacticDiagnostics(file),
      ...program.getSemanticDiagnostics(file),
    ];
    if (errors.length > 0) {
      throw new UnreadableSourceError(ts.formatDiagnostics(errors, FORMAT).trim());
    }
    return file;
  });
  return { checker: program.getTypeChecker(), files };
};
```

**`extension/tests/lib/walk.ts`** (changed: 1 edit)

<!-- edit: extension/tests/lib/walk.ts -->
Replace:
```typescript

const named = (path: string, suffixes: readonly string[]): boolean => {
  throw new Error("not implemented: named");
};

/** Every file under `directory` (relative to `extension/`) whose name ends in one of `suffixes`. */
export const filesUnder = (directory: string, suffixes: readonly string[]): string[] => {
  return [];
};

/** The same files as git lists them, independent of the walk. */
export const gitListed = (directory: string, suffixes: readonly string[]): string[] => {
  throw new Error("not implemented: gitListed");
};
```
with:
```typescript

const named = (path: string, suffixes: readonly string[]): boolean =>
  suffixes.some((suffix) => path.endsWith(suffix));

/** Every file under `directory` (relative to `extension/`) whose name ends in one of `suffixes`. */
export const filesUnder = (directory: string, suffixes: readonly string[]): string[] =>
  readdirSync(join(EXTENSION, directory), { recursive: true, encoding: "utf8" })
    .map((found) => join(directory, found).split(sep).join("/"))
    .filter((path) => named(path, suffixes) && !path.split("/").some((part) => SKIPPED.has(part)))
    .sort();

/** The same files as git lists them, independent of the walk. */
export const gitListed = (directory: string, suffixes: readonly string[]): string[] =>
  execFileSync("git", ["ls-files", "-z", "--", directory], { cwd: EXTENSION, encoding: "utf8" })
    .split("\0")
    .filter((path) => path !== "" && named(path, suffixes))
    .sort();
```


- [ ] **Step 5: Confirm the floors and run the gate.** `npm run floors:record` prints `no floor moved` (recorded from Task 1's file: `compiler-home.uses: new, 23`, `source.files: new, 24`); then the gate.

<!-- check: gate -->

- [ ] **Step 6: Commit** `feat(extension): #221 one source reader and type checker, the git-listed walk, one home for the compiler's readers (Refs #221)`.

### Task 3: Import direction between the layers, one home for the compiler import

**Acceptance criteria (story text):** AC3's first half (every import of each package read from the parse tree; `core` importing `history`, `readers` or `shell`, or any package importing `shell`, refused by file and line).

**Files:**
- Create: `extension/tests/lib/imports.ts`
- Test: `extension/tests/import-direction.test.ts`
- Modify: `extension/tests/lib/source.ts` (`preScannedImports`, the cross-check this task's reader is held to), `extension/tests/floors.json`

**Interfaces:**
- Consumes: `source.ts`, `walk.ts`.
- Produces: `source.ts`: `preScannedImports(text) -> string[]` (the compiler's own import pre-scanner). `imports.ts`: `Import`, `importsOf(file) -> Import[]`, `LAYERS`, `Layer`, `UPSTREAM`, `layerOf(path)`, `targetOf(path, specifier) -> Layer | "external"`, `upstreamImports(path, file) -> string[]`.

- [ ] **Step 1: Write the failing tests.**

**`extension/tests/import-direction.test.ts`** (new)

<!-- file: extension/tests/import-direction.test.ts -->
```typescript
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "vitest";
import { floorBreach } from "./lib/floors.ts";
import { importsOf, layerOf, targetOf, upstreamImports } from "./lib/imports.ts";
import { searched } from "./lib/population.ts";
import {
  EXTENSION,
  parse,
  preScannedImports,
  readSource,
  UnreadableSourceError,
} from "./lib/source.ts";
import { filesUnder, gitListed } from "./lib/walk.ts";

const SUFFIXES = [".ts", ".js"] as const;
const PACKAGE_FILES = filesUnder("packages", SUFFIXES);
const WORKSPACE_FILES = filesUnder(".", SUFFIXES);

/** Each way the workspace can import a module (AC3), naming shell. */
const FORMS: readonly (readonly [string, string])[] = [
  ["an import", 'import { a } from "@steadyhand/shell";'],
  ["a type-only import", 'import type { A } from "@steadyhand/shell";'],
  ["a side-effect import", 'import "@steadyhand/shell";'],
  ["an export from", 'export { a } from "@steadyhand/shell";'],
  ["an export of everything from", 'export * from "@steadyhand/shell";'],
  ["an import-equals require", 'import a = require("@steadyhand/shell");'],
  ["a dynamic import", 'await import("@steadyhand/shell");'],
  ["a require call", 'require("@steadyhand/shell");'],
  ["a type's import", 'type A = import("@steadyhand/shell").A;'],
  ["a relative path into another package", 'import { a } from "../../shell/src/side-panel.ts";'],
];

test.each(FORMS)("%s from core is refused by file and line", (_, code) => {
  const path = "packages/core/src/sample.ts";
  expect(upstreamImports(path, parse(`\n${code}\n`, path))).toEqual([
    expect.stringMatching(/^packages\/core\/src\/sample\.ts line 2: core imports shell \(/u),
  ]);
});

test.each([
  ["core", "history"],
  ["core", "readers"],
  ["core", "shell"],
  ["readers", "shell"],
  ["history", "shell"],
])("%s importing %s is refused", (from, to) => {
  const path = `packages/${from}/src/sample.ts`;
  expect(upstreamImports(path, parse(`import "@steadyhand/${to}";\n`, path))).toEqual([
    `${path} line 1: ${from} imports ${to} (@steadyhand/${to})`,
  ]);
});

test.each([
  ["readers", "core"],
  ["history", "core"],
  ["readers", "history"],
  ["history", "readers"],
  ["shell", "readers"],
  ["shell", "history"],
  ["shell", "core"],
  ["core", "core"],
])("%s importing %s is allowed", (from, to) => {
  const path = `packages/${from}/src/sample.ts`;
  expect(upstreamImports(path, parse(`import "@steadyhand/${to}";\n`, path))).toEqual([]);
});

test("a module from outside the workspace is external, never a layer", () => {
  expect(targetOf("packages/core/src/a.ts", "decimal.js")).toBe("external");
});

test("an import whose module is not a written string is refused by name", () => {
  const path = "packages/core/src/sample.ts";
  expect(() => importsOf(parse("const name = 'x';\nawait import(name);\n", path))).toThrow(
    new UnreadableSourceError(
      "packages/core/src/sample.ts line 2: the module this import names is not written as a " +
        "string, so its direction cannot be judged",
    ),
  );
});

test("a workspace name that is no package is refused by name", () => {
  expect(() => targetOf("packages/core/src/a.ts", "@steadyhand/ledger")).toThrow(
    new UnreadableSourceError(
      "packages/core/src/a.ts: @steadyhand/ledger names no package of the workspace",
    ),
  );
});

test("a relative path leaving the packages is refused by name", () => {
  expect(() => targetOf("packages/core/src/a.ts", "../../../build.ts")).toThrow(
    new UnreadableSourceError(
      "packages/core/src/a.ts: ../../../build.ts reaches outside the packages",
    ),
  );
});

test("a file outside the packages has no layer to judge, and is refused by name", () => {
  expect(layerOf("tests/a.ts")).toBeUndefined();
  expect(() => upstreamImports("tests/a.ts", parse("export {};\n", "tests/a.ts"))).toThrow(
    new UnreadableSourceError("tests/a.ts: not in a package, so it has no layer to judge"),
  );
});

test("the package files read are the ones git lists, and as many as recorded", () => {
  expect(PACKAGE_FILES).toEqual(gitListed("packages", SUFFIXES));
  expect(floorBreach("import-direction.files", PACKAGE_FILES.length)).toBeUndefined();
});

test.each(WORKSPACE_FILES)(
  "%s: the tree reader finds the imports the pre-scanner finds",
  (path) => {
    const text = readFileSync(join(EXTENSION, path), "utf8");
    expect(importsOf(parse(text, path)).map(({ specifier }) => specifier)).toEqual(
      preScannedImports(text),
    );
  },
);

test("no package imports a package above it", () => {
  const imports = PACKAGE_FILES.flatMap((path) => importsOf(readSource(path)));
  const found = PACKAGE_FILES.flatMap((path) => upstreamImports(path, readSource(path)));
  expect(searched(found, { of: imports.length, what: "imports in the packages" })).toEqual([]);
  expect(floorBreach("import-direction.imports", imports.length)).toBeUndefined();
});

test("only tests/lib/source.ts imports the TypeScript compiler", () => {
  const imports = WORKSPACE_FILES.flatMap((path) =>
    importsOf(readSource(path)).map(({ specifier, line }) => ({ path, specifier, line })),
  );
  const compiler = imports.filter(({ specifier }) => specifier === "typescript");
  expect(compiler.map(({ path }) => path)).toContain("tests/lib/source.ts");
  const found = compiler
    .filter(({ path }) => path !== "tests/lib/source.ts")
    .map(({ path, line }) => `${path} line ${String(line)}: imports typescript`);
  expect(searched(found, { of: imports.length, what: "imports in the workspace" })).toEqual([]);
  expect(floorBreach("compiler-home.imports", imports.length)).toBeUndefined();
});
```


- [ ] **Step 2: Write the red form.**

**`extension/tests/lib/imports.ts`** (new)

<!-- file: extension/tests/lib/imports.ts -->
```typescript
/**
 * Every import a file makes, read from the parse tree (spec §3: the dependency rule is a test).
 * Each way the workspace can name another module is read: `import … from`, a side-effect import,
 * `export … from`, `import x = require(…)`, a dynamic `import(…)`, `require(…)` and a type's
 * `import(…)`. One whose module is not a string written in the code cannot be judged, so it is
 * refused by name.
 */
import { posix } from "node:path";
import { lineOf, nodes, ts, UnreadableSourceError } from "./source.ts";

/** One module named by a file, and the line naming it. */
export interface Import {
  specifier: string;
  line: number;
}

const literalOf = (file: ts.SourceFile, node: ts.Node, written: ts.Node | undefined): string => {
  throw new Error("not implemented: literalOf");
};

const isRequire = (node: ts.CallExpression): boolean => {
  throw new Error("not implemented: isRequire");
};

/** The module `node` names, if it is one of the import forms; `undefined` for any other node. */
const specifierOf = (file: ts.SourceFile, node: ts.Node): string | undefined => {
  throw new Error("not implemented: specifierOf");
};

/** Every import in `file`, in order. */
export const importsOf = (file: ts.SourceFile): Import[] => {
  throw new Error("not implemented: importsOf");
};

/** The workspace's packages, from the bottom layer up (spec §3). */
export const LAYERS = ["core", "readers", "history", "shell"] as const;
export type Layer = (typeof LAYERS)[number];

/** The layers each package may NOT import: core imports no other package, nothing imports shell. */
export const UPSTREAM: Readonly<Record<Layer, readonly Layer[]>> = {
  core: ["readers", "history", "shell"],
  readers: ["shell"],
  history: ["shell"],
  shell: [],
};

const isLayer = (name: string | undefined): name is Layer => {
  throw new Error("not implemented: isLayer");
};

/** The package holding `path` (relative to `extension/`), or `undefined` outside `packages/`. */
export const layerOf = (path: string): Layer | undefined => {
  throw new Error("not implemented: layerOf");
};

/**
 * The package `specifier`, imported by `path`, reaches: a layer, or "external" for a module from
 * outside the workspace. A workspace name that is no package, or a relative path that leaves the
 * packages, cannot be judged and is refused by name.
 */
export const targetOf = (path: string, specifier: string): Layer | "external" => {
  throw new Error("not implemented: targetOf");
};

/** Every import in `file`, at `path` in a package, that reaches a layer its package may not. */
export const upstreamImports = (path: string, file: ts.SourceFile): string[] => {
  throw new Error("not implemented: upstreamImports");
};
```

**`extension/tests/lib/source.ts`** (changed: 1 edit)

<!-- edit: extension/tests/lib/source.ts -->
Replace:
```typescript
/**
 * The type checker over `paths` (relative to `extension/`, or absolute), compiled with the
```
with:
```typescript
/**
 * The modules the compiler's own import pre-scanner finds in `text`, without building a tree: an
 * independent count of a file's imports, to cross-check a reader that walks the tree.
 */
export const preScannedImports = (text: string): string[] => {
  throw new Error("not implemented: preScannedImports");
};

/**
 * The type checker over `paths` (relative to `extension/`, or absolute), compiled with the
```


- [ ] **Step 3: Watch them fail.** `npx vitest run tests/import-direction.test.ts`. Measured: 57 of 57 new tests fail: 28 on `Error: not implemented: importsOf` (the per-file pre-scanner cross-checks among them), 23 on `upstreamImports`, one each on `targetOf` and `layerOf`, three refusal cases on their own assertion (`expected a thrown error to be UnreadableSourceError: packages/co…`), and the walk case on its floor (`expected 'floor import-direction.files: none re…' to be undefined`).

<!-- check: red -->

- [ ] **Step 4: Implement.**

**`extension/tests/floors.json`** (changed: 1 edit)

<!-- edit: extension/tests/floors.json -->
Replace:
```json
{
  "compiler-home.uses": 23,
  "source.files": 24,
  "workspace.locked-packages": 198
```
with:
```json
{
  "compiler-home.imports": 73,
  "compiler-home.uses": 41,
  "import-direction.files": 9,
  "import-direction.imports": 12,
  "source.files": 26,
  "workspace.locked-packages": 198
```

**`extension/tests/lib/imports.ts`** (changed: 4 edits)

<!-- edit: extension/tests/lib/imports.ts -->
Replace:
```typescript
const literalOf = (file: ts.SourceFile, node: ts.Node, written: ts.Node | undefined): string => {
  throw new Error("not implemented: literalOf");
};

const isRequire = (node: ts.CallExpression): boolean => {
  throw new Error("not implemented: isRequire");
};

/** The module `node` names, if it is one of the import forms; `undefined` for any other node. */
const specifierOf = (file: ts.SourceFile, node: ts.Node): string | undefined => {
  throw new Error("not implemented: specifierOf");
};

/** Every import in `file`, in order. */
export const importsOf = (file: ts.SourceFile): Import[] => {
  throw new Error("not implemented: importsOf");
};

```
with:
```typescript
const literalOf = (file: ts.SourceFile, node: ts.Node, written: ts.Node | undefined): string => {
  // A type's `import("x")` holds its module as a literal type around the string.
  const expression =
    written !== undefined && ts.isLiteralTypeNode(written) ? written.literal : written;
  if (expression !== undefined && ts.isStringLiteralLike(expression)) {
    return expression.text;
  }
  throw new UnreadableSourceError(
    `${file.fileName} line ${String(lineOf(file, node))}: the module this import names is not ` +
      "written as a string, so its direction cannot be judged",
  );
};

const isRequire = (node: ts.CallExpression): boolean =>
  ts.isIdentifier(node.expression) && node.expression.text === "require";

/** The module `node` names, if it is one of the import forms; `undefined` for any other node. */
const specifierOf = (file: ts.SourceFile, node: ts.Node): string | undefined => {
  if (ts.isImportDeclaration(node)) {
    return literalOf(file, node, node.moduleSpecifier);
  }
  if (ts.isExportDeclaration(node) && node.moduleSpecifier !== undefined) {
    return literalOf(file, node, node.moduleSpecifier);
  }
  if (ts.isExternalModuleReference(node)) {
    return literalOf(file, node, node.expression);
  }
  if (
    ts.isCallExpression(node) &&
    (node.expression.kind === ts.SyntaxKind.ImportKeyword || isRequire(node))
  ) {
    return literalOf(file, node, node.arguments[0]);
  }
  if (ts.isImportTypeNode(node)) {
    return literalOf(file, node, node.argument);
  }
  return undefined;
};

/** Every import in `file`, in order. */
export const importsOf = (file: ts.SourceFile): Import[] =>
  nodes(file).flatMap((node) => {
    const specifier = specifierOf(file, node);
    return specifier === undefined ? [] : [{ specifier, line: lineOf(file, node) }];
  });

```

<!-- edit: extension/tests/lib/imports.ts -->
Replace:
```typescript

const isLayer = (name: string | undefined): name is Layer => {
  throw new Error("not implemented: isLayer");
};

/** The package holding `path` (relative to `extension/`), or `undefined` outside `packages/`. */
export const layerOf = (path: string): Layer | undefined => {
  throw new Error("not implemented: layerOf");
};
```
with:
```typescript

const isLayer = (name: string | undefined): name is Layer =>
  (LAYERS as readonly (string | undefined)[]).includes(name);

/** The package holding `path` (relative to `extension/`), or `undefined` outside `packages/`. */
export const layerOf = (path: string): Layer | undefined => {
  const [top, name] = path.split("/");
  return top === "packages" && isLayer(name) ? name : undefined;
};
```

<!-- edit: extension/tests/lib/imports.ts -->
Replace:
```typescript
export const targetOf = (path: string, specifier: string): Layer | "external" => {
  throw new Error("not implemented: targetOf");
};
```
with:
```typescript
export const targetOf = (path: string, specifier: string): Layer | "external" => {
  if (specifier.startsWith("@steadyhand/")) {
    const name = specifier.split("/")[1];
    if (isLayer(name)) {
      return name;
    }
    throw new UnreadableSourceError(`${path}: ${specifier} names no package of the workspace`);
  }
  if (specifier.startsWith(".")) {
    const layer = layerOf(posix.join(posix.dirname(path), specifier));
    if (layer !== undefined) {
      return layer;
    }
    throw new UnreadableSourceError(`${path}: ${specifier} reaches outside the packages`);
  }
  return "external";
};
```

<!-- edit: extension/tests/lib/imports.ts -->
Replace:
```typescript
export const upstreamImports = (path: string, file: ts.SourceFile): string[] => {
  throw new Error("not implemented: upstreamImports");
};
```
with:
```typescript
export const upstreamImports = (path: string, file: ts.SourceFile): string[] => {
  const from = layerOf(path);
  if (from === undefined) {
    throw new UnreadableSourceError(`${path}: not in a package, so it has no layer to judge`);
  }
  return importsOf(file).flatMap(({ specifier, line }) => {
    const to = targetOf(path, specifier);
    return to !== "external" && UPSTREAM[from].includes(to)
      ? [`${path} line ${String(line)}: ${from} imports ${to} (${specifier})`]
      : [];
  });
};
```

**`extension/tests/lib/source.ts`** (changed: 1 edit)

<!-- edit: extension/tests/lib/source.ts -->
Replace:
```typescript
 */
export const preScannedImports = (text: string): string[] => {
  throw new Error("not implemented: preScannedImports");
};

```
with:
```typescript
 */
export const preScannedImports = (text: string): string[] =>
  ts.preProcessFile(text, true, true).importedFiles.map((imported) => imported.fileName);

```


- [ ] **Step 5: Confirm the floors and run the gate.** `npm run floors:record` prints `no floor moved` (the file was recorded from Task 2's, printing the five Task 3 lines under **The floors each task records**); then the gate.

<!-- check: gate -->

- [ ] **Step 6: Commit** `feat(extension): #221 import direction between the layers, one home for the compiler import (Refs #221)`.

### Task 4: Core's rules: no browser global, no `number` by word or by type

**Acceptance criteria (story text):** AC3's second half (a browser global, `window`, `document`, `chrome` or `indexedDB`, in `core` is refused), AC4 (no `number` for money, widened by Shyden's decisions to all of `core`, by words and by types).

**Files:**
- Create: `extension/tests/lib/core-rules.ts`
- Test: `extension/tests/core-rules.test.ts`
- Modify: `extension/tests/floors.json`

**Interfaces:**
- Consumes: `source.ts` (`typeChecked` for the type pass), `walk.ts`.
- Produces: `BROWSER_GLOBALS`, `NUMBER_GLOBALS`, `browserGlobals(file) -> string[]`, `numberWords(file) -> string[]`, `typedDeclarations(file) -> ts.Node[]`, `numberTypes(checker, file) -> string[]`, each finding as `line <n>: <what>`.

- [ ] **Step 1: Write the failing tests.**

**`extension/tests/core-rules.test.ts`** (new)

<!-- file: extension/tests/core-rules.test.ts -->
```typescript
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, expect, test } from "vitest";
import { browserGlobals, numberTypes, numberWords, typedDeclarations } from "./lib/core-rules.ts";
import { floorBreach } from "./lib/floors.ts";
import { searched } from "./lib/population.ts";
import {
  nodes,
  parse,
  readSource,
  tokens,
  ts,
  typeChecked,
  UnreadableSourceError,
} from "./lib/source.ts";
import { filesUnder, gitListed } from "./lib/walk.ts";

const SUFFIXES = [".ts", ".js"] as const;
const CORE = filesUnder("packages/core/src", SUFFIXES);

const sample = (code: string): ts.SourceFile => parse(code, "sample.ts");

/** Each way core could reach a browser global (AC3), with what the guard reports. */
test.each([
  ["a bare global", "window.alert;", ["line 1: window"]],
  ["document", "document.title;", ["line 1: document"]],
  ["chrome", "chrome.runtime;", ["line 1: chrome"]],
  ["indexedDB", "indexedDB.open('x');", ["line 1: indexedDB"]],
  ["a typeof", "typeof window;", ["line 1: window"]],
  ["a shorthand property", "const a = { window };", ["line 1: window"]],
  ["a property of globalThis", "globalThis.chrome;", ["line 1: globalThis.chrome"]],
  ["a property of self", "self.indexedDB;", ["line 1: self.indexedDB"]],
  ["a key into globalThis", 'globalThis["document"];', ['line 1: globalThis["document"]']],
  ["window's own document", "window.document;", ["line 1: window.document", "line 1: window"]],
])("core reaching %s is refused", (_, code, found) => {
  expect(browserGlobals(sample(code))).toEqual(found);
});

/** Where the same names are keys or members, never the browser's globals. */
test.each([
  ["an object key", "const a = { window: 1n };"],
  ["a property of another object", "page.window;"],
  ["a class field", "class A { window = 1n; }"],
  ["an interface member", "interface A { window: string }"],
  ["a method", "class A { document(): void {} }"],
  ["a method signature", "interface A { chrome(): void }"],
  ["a getter", "class A { get window(): string { return ''; } }"],
  ["a setter", "class A { set window(v: string) {} }"],
  ["an enum member", "enum A { window }"],
  ["a qualified type name", "type A = B.window;"],
  ["a key into another object", 'page["window"];'],
  ["a key into globalThis naming no browser global", 'globalThis["structuredClone"];'],
  ["a string", '"window";'],
])("%s named like a browser global is allowed", (_, code) => {
  expect(browserGlobals(sample(code))).toEqual([]);
});

test("a computed key into a global object cannot be judged, and is refused by name", () => {
  expect(() => browserGlobals(sample("globalThis[key];"))).toThrow(
    new UnreadableSourceError(
      "sample.ts line 1: globalThis[…] with a computed key cannot be judged",
    ),
  );
});

/** Each way core could write a `number` (AC4), with what the guard reports. */
test.each([
  ["an annotation", "let a: number;", "line 1: number"],
  ["an assertion", "const a = b as number;", "line 1: number"],
  ["a satisfies", "const a = b satisfies number;", "line 1: number"],
  ["a type argument", "const a: Array<number> = [];", "line 1: number"],
  ["an array type", "let a: number[];", "line 1: number"],
  ["Number", "Number('1');", "line 1: Number"],
  ["Number's constant", "Number.MAX_SAFE_INTEGER;", "line 1: Number"],
  ["parseFloat", "parseFloat('1');", "line 1: parseFloat"],
  ["parseInt", "parseInt('1', 10);", "line 1: parseInt"],
  ["a decimal", "1.5;", "line 1: literal 1.5"],
  ["an exponent", "1e3;", "line 1: literal 1e3"],
  ["a leading point", ".5;", "line 1: literal .5"],
])("core writing %s is refused", (_, code, found) => {
  expect(numberWords(sample(code))).toEqual([found]);
});

test.each([
  ["a whole-number index", "rows[0];"],
  ["hex", "0xff;"],
  ["octal", "0o17;"],
  ["binary", "0b101;"],
  ["separators", "1_000;"],
  ["a bigint", "100n;"],
  ["a key named Number", "const a = { Number: 1n };"],
  ["a word in a comment", "// number 1.5 Number\n"],
])("%s is allowed by the written-word guard", (_, code) => {
  expect(numberWords(sample(code))).toEqual([]);
});

/** Each value a type can make a `number` without the word (Shyden, 2026-10-06), and the
 * finding. Each is its own file in one program, so the checker is built once. */
const TYPED: readonly (readonly [string, string, readonly string[]])[] = [
  ["an unlabelled whole number", "export const fee = 100;", ["line 1: fee: 100"]],
  ["a let", "export let fee = 100;", ["line 1: fee: number"]],
  ["a length kept in a name", "export const n = [1n].length;", ["line 1: n: number"]],
  [
    "an object literal holding one",
    "export const row = { fee: 100 };",
    ["line 1: row: { fee: number; }", "line 1: fee: number"],
  ],
  ["an array of them", "export const fees = [100];", ["line 1: fees: number[]"]],
  ["a function's result", "export function rate() {\n  return 100;\n}", ["line 1: returns number"]],
  ["an arrow's result", "export const rate = () => 100;", ["line 1: returns number"]],
  [
    "a parameter",
    "export const half = (n = 2) => n;",
    ["line 1: returns number", "line 1: n: number"],
  ],
  [
    "a destructured name",
    "const { length } = [1n];\nexport { length };",
    ["line 1: length: number"],
  ],
  ["a class field", "export class A {\n  fee = 100;\n}", ["line 2: fee: number"]],
  [
    "a literal type in an interface",
    "export interface A {\n  fee: bigint | 1;\n}",
    ["line 2: fee: bigint | 1"],
  ],
  [
    "a method's result",
    "export class A {\n  fee() {\n    return 1;\n  }\n}",
    ["line 2: returns number"],
  ],
  [
    "a getter's result",
    "export class A {\n  get fee() {\n    return 1;\n  }\n}",
    ["line 2: fee: number"],
  ],
  [
    "a callback's parameter",
    "export const xs = [1n].map((x, i) => x + BigInt(i));",
    ["line 1: i: number"],
  ],
  ["a bigint", "export const fee = 100n;", []],
  ["a comparator's result", "export const s = [2n, 1n].toSorted((a, b) => (a < b ? -1 : 1));", []],
  ["a string", 'export const s = "100";', []],
  ["an inline index", "export const first = [1n][0];", []],
  ["a repeated field type", "export const pair = { a: 1n, b: 1n };", []],
];

let fixtures = "";
let checked: ReturnType<typeof typeChecked> | undefined;

beforeAll(() => {
  fixtures = mkdtempSync(join(tmpdir(), "steadyhand-types-"));
  const paths = TYPED.map(([, code], index) => {
    const path = join(fixtures, `case-${String(index)}.ts`);
    writeFileSync(path, `${code}\n`);
    return path;
  });
  checked = typeChecked(paths);
});

afterAll(() => {
  rmSync(fixtures, { recursive: true, force: true });
});

test.each(TYPED.map((row, index) => [...row, index] as const))(
  "the type pass judges %s",
  (_, __, found, index) => {
    const file = checked?.files[index];
    expect(
      file === undefined || checked === undefined ? undefined : numberTypes(checked.checker, file),
    ).toEqual(found);
  },
);

test("core's files are the ones git lists, and as many as recorded", () => {
  expect(CORE).toEqual(gitListed("packages/core/src", SUFFIXES));
  expect(floorBreach("core.files", CORE.length)).toBeUndefined();
});

test("core reaches no browser global", () => {
  const read = CORE.map((path) => ({ path, file: readSource(path) }));
  const identifiers = read.flatMap(({ file }) => nodes(file).filter(ts.isIdentifier));
  const found = read.flatMap(({ path, file }) => browserGlobals(file).map((f) => `${path} ${f}`));
  expect(searched(found, { of: identifiers.length, what: "identifiers in core" })).toEqual([]);
  expect(floorBreach("browser-globals.identifiers", identifiers.length)).toBeUndefined();
});

test("core writes no number", () => {
  const read = CORE.map((path) => ({ path, file: readSource(path) }));
  const judged = read.flatMap(({ file }) => nodes(file));
  const found = read.flatMap(({ path, file }) => numberWords(file).map((f) => `${path} ${f}`));
  expect(searched(found, { of: judged.length, what: "nodes in core" })).toEqual([]);
  expect(floorBreach("number-words.nodes", judged.length)).toBeUndefined();
});

test("no value in core has a number type, written or inferred", () => {
  const { checker, files } = typeChecked(CORE);
  const judged = files.flatMap((file) => typedDeclarations(file));
  const found = files.flatMap((file) =>
    numberTypes(checker, file).map((f) => `${file.fileName} ${f}`),
  );
  expect(searched(found, { of: judged.length, what: "typed values in core" })).toEqual([]);
  expect(floorBreach("number-types.values", judged.length)).toBeUndefined();
});

/** The values the type pass should judge, counted by the token walk instead of the node walk. */
const typedByTokens = (file: ts.SourceFile): number =>
  tokens(file).filter((token) => {
    const { parent } = token;
    const passed =
      ts.isCallExpression(parent.parent) &&
      parent.parent.arguments.includes(parent as ts.Expression);
    if (ts.isIdentifier(token)) {
      return (parent as { name?: ts.Node }).name === token && NAMED_BY_TOKEN.has(parent.kind);
    }
    if (token.kind === ts.SyntaxKind.EqualsGreaterThanToken) {
      return ts.isArrowFunction(parent) && !passed;
    }
    return (
      token.kind === ts.SyntaxKind.FunctionKeyword &&
      (ts.isFunctionDeclaration(parent) || ts.isFunctionExpression(parent)) &&
      !passed
    );
  }).length;

const NAMED_BY_TOKEN = new Set([
  ts.SyntaxKind.VariableDeclaration,
  ts.SyntaxKind.Parameter,
  ts.SyntaxKind.BindingElement,
  ts.SyntaxKind.PropertyDeclaration,
  ts.SyntaxKind.PropertySignature,
  ts.SyntaxKind.PropertyAssignment,
  ts.SyntaxKind.ShorthandPropertyAssignment,
  ts.SyntaxKind.GetAccessor,
  ts.SyntaxKind.MethodDeclaration,
  ts.SyntaxKind.MethodSignature,
]);

test.each(TYPED.map(([name, code]) => [name, code] as const))(
  "the token walk counts the values the type pass judges in %s",
  (_, code) => {
    const file = sample(code);
    expect(typedDeclarations(file)).toHaveLength(typedByTokens(file));
  },
);

test.each(CORE)("%s: the token walk counts the values the type pass judges", (path) => {
  const file = readSource(path);
  expect(typedDeclarations(file)).toHaveLength(typedByTokens(file));
});
```


- [ ] **Step 2: Write the red form.**

**`extension/tests/lib/core-rules.ts`** (new)

<!-- file: extension/tests/lib/core-rules.ts -->
```typescript
/**
 * What core may not hold (spec §3, §4.1). Core is pure logic: no browser API, so it runs the same
 * in the side panel, a test and the parity harness. And `number` never holds money: money is a
 * `bigint` of minor units and ratios are `decimal.js`, as Python refuses `float`. Shyden chose
 * (2026-10-06, #221) to judge all of core, by the written word AND by the type checker, because a
 * plain `const fee = 100` is a `number` that never writes the word.
 */
import { lineOf, nodes, ts, UnreadableSourceError } from "./source.ts";

/** The browser's globals spec §3 names, and the objects they hang from. */
export const BROWSER_GLOBALS = new Set(["window", "document", "chrome", "indexedDB"]);
const GLOBAL_OBJECTS = new Set(["globalThis", "self", "window"]);

/** The globals that turn text into a `number`, or name its type. */
export const NUMBER_GLOBALS = new Set(["Number", "parseFloat", "parseInt"]);

/** The declarations whose `name` is a key, not a reference to a value. */
const KEYED = new Set([
  ts.SyntaxKind.PropertyAccessExpression,
  ts.SyntaxKind.PropertyAssignment,
  ts.SyntaxKind.PropertyDeclaration,
  ts.SyntaxKind.PropertySignature,
  ts.SyntaxKind.MethodDeclaration,
  ts.SyntaxKind.MethodSignature,
  ts.SyntaxKind.GetAccessor,
  ts.SyntaxKind.SetAccessor,
  ts.SyntaxKind.EnumMember,
]);

/** Whether `node` refers to a value by its name, rather than naming a key or a member. */
const isReference = (node: ts.Identifier): boolean => {
  throw new Error("not implemented: isReference");
};

const at = (file: ts.SourceFile, node: ts.Node, what: string): string => {
  throw new Error("not implemented: at");
};

/** Every use of a browser global in `file`: by name, or as a property of a global object. */
export const browserGlobals = (file: ts.SourceFile): string[] => {
  throw new Error("not implemented: browserGlobals");
};

/** A whole number written as one: decimal, hex, octal or binary digits, no point, no exponent. */
const WHOLE = /^(?:0[xX][\da-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+|\d[\d_]*)$/u;

/** Every place `file` writes `number`: the type keyword, a number global, a non-whole literal. */
export const numberWords = (file: ts.SourceFile): string[] => {
  throw new Error("not implemented: numberWords");
};

/** Whether `type` is, or holds, a `number`: a union member, an array or type argument, a field
 * of an anonymous object type. A named interface or class is judged where it is declared. */
const holdsNumber = (checker: ts.TypeChecker, type: ts.Type, seen: Set<ts.Type>): boolean => {
  throw new Error("not implemented: holdsNumber");
};

/** The declarations whose value the type pass judges by their name. */
const NAMED = new Set([
  ts.SyntaxKind.VariableDeclaration,
  ts.SyntaxKind.Parameter,
  ts.SyntaxKind.BindingElement,
  ts.SyntaxKind.PropertyDeclaration,
  ts.SyntaxKind.PropertySignature,
  ts.SyntaxKind.PropertyAssignment,
  ts.SyntaxKind.ShorthandPropertyAssignment,
  ts.SyntaxKind.GetAccessor,
]);

/** The functions whose result the type pass judges (a getter's is its property's type, above). */
const RETURNING = new Set([
  ts.SyntaxKind.FunctionDeclaration,
  ts.SyntaxKind.FunctionExpression,
  ts.SyntaxKind.ArrowFunction,
  ts.SyntaxKind.MethodDeclaration,
  ts.SyntaxKind.MethodSignature,
]);

/** A named declaration whose name is an identifier: a destructuring pattern's names are judged
 * as their own binding elements. */
const namedDeclaration = (node: ts.Node): ts.Identifier | undefined => {
  throw new Error("not implemented: namedDeclaration");
};

/**
 * A function passed straight to a call: its result is set by the callee (a comparator for `sort`
 * must return a `number`), so its parameters are judged and its result is not.
 */
const isCallback = (node: ts.Node): boolean => {
  throw new Error("not implemented: isCallback");
};

/** Every value in `file` the type pass judges: named declarations and the results of functions. */
export const typedDeclarations = (file: ts.SourceFile): ts.Node[] => {
  throw new Error("not implemented: typedDeclarations");
};

/** Every value in `file` whose type, written or inferred, is or holds a `number`. */
export const numberTypes = (checker: ts.TypeChecker, file: ts.SourceFile): string[] => {
  throw new Error("not implemented: numberTypes");
};
```


- [ ] **Step 3: Watch them fail.** `npx vitest run tests/core-rules.test.ts`. Measured: 87 of 87 new tests fail: 24 on `Error: not implemented: browserGlobals`, 21 on `typedDeclarations`, 21 on `numberWords`, 19 on `numberTypes`, one refusal on its own assertion, and the walk case on its floor (`expected 'floor core.files: none recorded, meas…' to be undefined`).

<!-- check: red -->

- [ ] **Step 4: Implement.**

**`extension/tests/floors.json`** (changed: 1 edit)

<!-- edit: extension/tests/floors.json -->
Replace:
```json
{
  "compiler-home.imports": 73,
  "compiler-home.uses": 41,
  "import-direction.files": 9,
  "import-direction.imports": 12,
  "source.files": 26,
  "workspace.locked-packages": 198
```
with:
```json
{
  "browser-globals.identifiers": 1,
  "compiler-home.imports": 83,
  "compiler-home.uses": 123,
  "core.files": 1,
  "import-direction.files": 9,
  "import-direction.imports": 12,
  "number-types.values": 1,
  "number-words.nodes": 7,
  "source.files": 28,
  "workspace.locked-packages": 198
```

**`extension/tests/lib/core-rules.ts`** (changed: 5 edits)

<!-- edit: extension/tests/lib/core-rules.ts -->
Replace:
```typescript
const isReference = (node: ts.Identifier): boolean => {
  throw new Error("not implemented: isReference");
};

const at = (file: ts.SourceFile, node: ts.Node, what: string): string => {
  throw new Error("not implemented: at");
};

/** Every use of a browser global in `file`: by name, or as a property of a global object. */
export const browserGlobals = (file: ts.SourceFile): string[] => {
  throw new Error("not implemented: browserGlobals");
};

```
with:
```typescript
const isReference = (node: ts.Identifier): boolean => {
  const { parent } = node;
  if (KEYED.has(parent.kind)) {
    return (parent as { name?: ts.Node }).name !== node;
  }
  return !(ts.isQualifiedName(parent) && parent.right === node);
};

const at = (file: ts.SourceFile, node: ts.Node, what: string): string =>
  `line ${String(lineOf(file, node))}: ${what}`;

/** Every use of a browser global in `file`: by name, or as a property of a global object. */
export const browserGlobals = (file: ts.SourceFile): string[] =>
  nodes(file).flatMap((node) => {
    if (ts.isIdentifier(node)) {
      return BROWSER_GLOBALS.has(node.text) && isReference(node) ? [at(file, node, node.text)] : [];
    }
    if (ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.expression)) {
      const owner = node.expression.text;
      const name = node.name.text;
      return GLOBAL_OBJECTS.has(owner) && BROWSER_GLOBALS.has(name)
        ? [at(file, node, `${owner}.${name}`)]
        : [];
    }
    if (ts.isElementAccessExpression(node) && ts.isIdentifier(node.expression)) {
      const owner = node.expression.text;
      if (!GLOBAL_OBJECTS.has(owner)) {
        return [];
      }
      const key = node.argumentExpression;
      if (!ts.isStringLiteralLike(key)) {
        throw new UnreadableSourceError(
          `${file.fileName} line ${String(lineOf(file, node))}: ${owner}[…] with a computed key ` +
            "cannot be judged",
        );
      }
      return BROWSER_GLOBALS.has(key.text) ? [at(file, node, `${owner}["${key.text}"]`)] : [];
    }
    return [];
  });

```

<!-- edit: extension/tests/lib/core-rules.ts -->
Replace:
```typescript
/** Every place `file` writes `number`: the type keyword, a number global, a non-whole literal. */
export const numberWords = (file: ts.SourceFile): string[] => {
  throw new Error("not implemented: numberWords");
};

```
with:
```typescript
/** Every place `file` writes `number`: the type keyword, a number global, a non-whole literal. */
export const numberWords = (file: ts.SourceFile): string[] =>
  nodes(file).flatMap((node) => {
    if (node.kind === ts.SyntaxKind.NumberKeyword) {
      return [at(file, node, "number")];
    }
    if (ts.isIdentifier(node) && NUMBER_GLOBALS.has(node.text) && isReference(node)) {
      return [at(file, node, node.text)];
    }
    // The literal as written: `text` is the normalised value, which reads `1e3` as `1000`.
    if (ts.isNumericLiteral(node) && !WHOLE.test(node.getText(file))) {
      return [at(file, node, `literal ${node.getText(file)}`)];
    }
    return [];
  });

```

<!-- edit: extension/tests/lib/core-rules.ts -->
Replace:
```typescript
const holdsNumber = (checker: ts.TypeChecker, type: ts.Type, seen: Set<ts.Type>): boolean => {
  throw new Error("not implemented: holdsNumber");
};
```
with:
```typescript
const holdsNumber = (checker: ts.TypeChecker, type: ts.Type, seen: Set<ts.Type>): boolean => {
  if (seen.has(type)) {
    return false;
  }
  seen.add(type);
  if ((type.flags & ts.TypeFlags.NumberLike) !== 0) {
    return true;
  }
  if (type.isUnionOrIntersection()) {
    return type.types.some((member) => holdsNumber(checker, member, seen));
  }
  const object = type as ts.ObjectType;
  if ((object.objectFlags & ts.ObjectFlags.Reference) !== 0) {
    return checker
      .getTypeArguments(object as ts.TypeReference)
      .some((argument) => holdsNumber(checker, argument, seen));
  }
  // An object literal's declared type is anonymous, not flagged ObjectLiteral (measured on
  // 2026-10-06). A function type is anonymous too and has no properties: its result is judged
  // where the function is declared.
  if ((object.objectFlags & ts.ObjectFlags.Anonymous) !== 0) {
    return checker
      .getPropertiesOfType(object)
      .some((property) => holdsNumber(checker, checker.getTypeOfSymbol(property), seen));
  }
  return false;
};
```

<!-- edit: extension/tests/lib/core-rules.ts -->
Replace:
```typescript
const namedDeclaration = (node: ts.Node): ts.Identifier | undefined => {
  throw new Error("not implemented: namedDeclaration");
};
```
with:
```typescript
const namedDeclaration = (node: ts.Node): ts.Identifier | undefined => {
  if (!NAMED.has(node.kind)) {
    return undefined;
  }
  const { name } = node as ts.Node & { name: ts.Node };
  return ts.isIdentifier(name) ? name : undefined;
};
```

<!-- edit: extension/tests/lib/core-rules.ts -->
Replace:
```typescript
 */
const isCallback = (node: ts.Node): boolean => {
  throw new Error("not implemented: isCallback");
};

/** Every value in `file` the type pass judges: named declarations and the results of functions. */
export const typedDeclarations = (file: ts.SourceFile): ts.Node[] => {
  throw new Error("not implemented: typedDeclarations");
};

/** Every value in `file` whose type, written or inferred, is or holds a `number`. */
export const numberTypes = (checker: ts.TypeChecker, file: ts.SourceFile): string[] => {
  throw new Error("not implemented: numberTypes");
};
```
with:
```typescript
 */
const isCallback = (node: ts.Node): boolean =>
  ts.isCallExpression(node.parent) && node.parent.arguments.some((argument) => argument === node);

/** Every value in `file` the type pass judges: named declarations and the results of functions. */
export const typedDeclarations = (file: ts.SourceFile): ts.Node[] =>
  nodes(file).filter(
    (node) =>
      namedDeclaration(node) !== undefined || (RETURNING.has(node.kind) && !isCallback(node)),
  );

/** Every value in `file` whose type, written or inferred, is or holds a `number`. */
export const numberTypes = (checker: ts.TypeChecker, file: ts.SourceFile): string[] =>
  typedDeclarations(file).flatMap((node) => {
    const name = namedDeclaration(node);
    if (name !== undefined) {
      const type = checker.getTypeAtLocation(name);
      return holdsNumber(checker, type, new Set())
        ? [at(file, node, `${name.text}: ${checker.typeToString(type)}`)]
        : [];
    }
    return checker
      .getSignaturesOfType(checker.getTypeAtLocation(node), ts.SignatureKind.Call)
      .map((signature) => checker.getReturnTypeOfSignature(signature))
      .filter((result) => holdsNumber(checker, result, new Set()))
      .map((result) => at(file, node, `returns ${checker.typeToString(result)}`));
  });
```


- [ ] **Step 5: Confirm the floors and run the gate.** `npm run floors:record` prints `no floor moved` (the file was recorded from Task 3's, printing the seven Task 4 lines under **The floors each task records**); then the gate.

<!-- check: gate -->

- [ ] **Step 6: Commit** `feat(extension): #221 core's rules: no browser global, no number by word or by type (Refs #221)`.

### Task 5: No literal floor in any TypeScript test

**Acceptance criteria (story text):** AC1's last sentence (a literal floor in any test is refused).

**Files:**
- Create: `extension/tests/lib/literal-floors.ts`
- Test: `extension/tests/literal-floors.test.ts`
- Modify: `extension/tests/floors.json`

**Interfaces:**
- Consumes: `source.ts`, `walk.ts`, `floors.ts`.
- Produces: `isAssertion(node)`, `assertionsOf(file)`, `literalFloors(file) -> string[]`, `variablesOf(file)`, `floorConstants(file) -> string[]`.

- [ ] **Step 1: Write the failing tests.**

**`extension/tests/literal-floors.test.ts`** (new)

<!-- file: extension/tests/literal-floors.test.ts -->
```typescript
import { expect, test } from "vitest";
import { floorBreach } from "./lib/floors.ts";
import { assertionsOf, floorConstants, literalFloors, variablesOf } from "./lib/literal-floors.ts";
import { searched } from "./lib/population.ts";
import { codeText, parse, readSource, tokens, ts, UnreadableSourceError } from "./lib/source.ts";
import { filesUnder, gitListed } from "./lib/walk.ts";

const SUFFIXES = [".ts", ".js"] as const;

/** The workspace's tests: every file under `tests/` and each package's `test/`. */
const isTest = (path: string): boolean =>
  path.startsWith("tests/") || path.split("/")[2] === "test";
const TESTS = filesUnder(".", SUFFIXES).filter(isTest);

const sample = (code: string): ts.SourceFile => parse(code, "sample.ts");

/** Each way a test can write a floor by hand (AC1), with what the guard reports. */
test.each([
  [
    "toBeGreaterThanOrEqual",
    "expect(n).toBeGreaterThanOrEqual(197);",
    "toBeGreaterThanOrEqual(197)",
  ],
  ["toBeGreaterThan", "expect(n).toBeGreaterThan(196);", "toBeGreaterThan(196)"],
  ["a negated toBeLessThan", "expect(n).not.toBeLessThan(197);", "not.toBeLessThan(197)"],
  [
    "a negated toBeLessThanOrEqual",
    "expect(n).not.toBeLessThanOrEqual(196);",
    "not.toBeLessThanOrEqual(196)",
  ],
  ["a resolved value", "await expect(p).resolves.toBeGreaterThan(5);", "toBeGreaterThan(5)"],
  ["a soft assertion", "expect.soft(n).toBeGreaterThan(5);", "toBeGreaterThan(5)"],
  ["a polled assertion", "await expect.poll(f).toBeGreaterThan(5);", "toBeGreaterThan(5)"],
  ["a separated literal", "expect(n).toBeGreaterThan(1_000);", "toBeGreaterThan(1_000)"],
  ["a bigint", "expect(n).toBeGreaterThan(5n);", "toBeGreaterThan(5n)"],
  ["a negative literal", "expect(n).toBeGreaterThan(-1);", "toBeGreaterThan(-1)"],
  ["a comparison", "expect(n >= 197).toBe(true);", "n >= 197"],
  ["a strict comparison", "expect(n > 196).toBe(true);", "n > 196"],
  ["a reversed comparison", "expect(197 <= n).toBe(true);", "197 <= n"],
  ["a reversed strict comparison", "expect(196 < n).toBe(true);", "196 < n"],
])("a floor written as %s is refused by line", (_, code, found) => {
  expect(literalFloors(sample(`\n${code}\n`))).toEqual([`line 2: ${found}`]);
});

test("a floor bound to a named literal is refused, naming both", () => {
  expect(
    literalFloors(sample("const MIN = 197;\nexpect(n).toBeGreaterThanOrEqual(MIN);\n")),
  ).toEqual(["line 2: toBeGreaterThanOrEqual(MIN = 197)"]);
});

test.each([
  ["FILES_FLOOR", "const FILES_FLOOR = 197;", "line 1: FILES_FLOOR = 197"],
  ["filesFloor", "let filesFloor = 196;", "line 1: filesFloor = 196"],
  ["a negative one", "const FLOOR = -1;", "line 1: FLOOR = -1"],
])("a constant named %s set to a literal is refused", (_, code, found) => {
  expect(floorConstants(sample(code))).toEqual([found]);
});

/** Bounds that are not floors, and floors that are recorded. */
test.each([
  ["a non-emptiness check", "expect(n).toBeGreaterThan(0);"],
  ["a ceiling", "expect(ms).toBeLessThan(30_000);"],
  ["a negated lower bound", "expect(n).not.toBeGreaterThan(5);"],
  ["a computed bound", "expect(n).toBeGreaterThan(rows.length);"],
  ["a negated computed bound", "expect(n).toBeGreaterThan(-rows.length);"],
  ["a bound kept in a computed name", "const min = rows.length;\nexpect(n).toBeGreaterThan(min);"],
  ["a recorded floor", 'expect(floorBreach("a.files", n)).toBeUndefined();'],
  ["a comparison outside an assertion", "if (n > 197) {\n  throw new Error();\n}"],
  ["a comparison against zero", "expect(n > 0).toBe(true);"],
  ["a matcher on something that is not an assertion", "helper(n).toBeGreaterThan(5);"],
  ["a matcher with no bound", "expect(n).toBeGreaterThan();"],
  ["a floor in a comment or a string", '// toBeGreaterThan(197)\nconst s = "FLOOR = 3";'],
  ["a floor constant that is computed", "const FILES_FLOOR = files.length;"],
  ["a floor constant of zero", "const FLOOR = 0;"],
  ["a floor constant with no value", "let floor;"],
])("%s is not a literal floor", (_, code) => {
  expect(literalFloors(sample(code))).toEqual([]);
  expect(floorConstants(sample(code))).toEqual([]);
});

test.each([
  ["an imported name", 'import { MIN } from "./m.ts";\nexpect(n).toBeGreaterThan(MIN);', "MIN"],
  ["a parameter", "(min: number) =>\n  expect(n).toBeGreaterThan(min);", "min"],
  ["a name declared with no value", "let min;\nexpect(n).toBeGreaterThan(min);", "min"],
])("a bound held in %s cannot be classified, and is refused by name", (_, code, name) => {
  expect(() => literalFloors(sample(code))).toThrow(
    new UnreadableSourceError(
      `sample.ts line 2: cannot tell whether ${name} is a literal floor; bound an assertion by ` +
        "a value computed in the test, or by a recorded floor",
    ),
  );
});

test("the test files read are the ones git lists, and as many as recorded", () => {
  expect(TESTS).toEqual(gitListed(".", SUFFIXES).filter(isTest));
  expect(floorBreach("literal-floors.files", TESTS.length)).toBeUndefined();
});

/** Assertions counted in the code text instead of the tree: `expect (`, `expect . soft (`. */
const ASSERTION_TEXT = /(?<!\. )\bexpect (?:\. (?:soft|poll) )?\(/gu;

test.each(TESTS)("%s: the tree reader finds the assertions the code text holds", (path) => {
  const file = readSource(path);
  expect(assertionsOf(file)).toHaveLength(codeText(file).match(ASSERTION_TEXT)?.length ?? 0);
});

test.each(TESTS)("%s: the tree reader finds the variables the token walk names", (path) => {
  const file = readSource(path);
  const named = tokens(file).filter(
    (token) =>
      ts.isIdentifier(token) &&
      ts.isVariableDeclaration(token.parent) &&
      token.parent.name === token,
  );
  expect(variablesOf(file)).toHaveLength(named.length);
});

test("no test bounds an assertion by a literal floor", () => {
  const read = TESTS.map((path) => ({ path, file: readSource(path) }));
  const assertions = read.flatMap(({ file }) => assertionsOf(file));
  const found = read.flatMap(({ path, file }) => literalFloors(file).map((f) => `${path} ${f}`));
  expect(searched(found, { of: assertions.length, what: "assertions in the tests" })).toEqual([]);
  expect(floorBreach("literal-floors.assertions", assertions.length)).toBeUndefined();
});

test("no test keeps a floor in a constant", () => {
  const read = TESTS.map((path) => ({ path, file: readSource(path) }));
  const variables = read.flatMap(({ file }) => variablesOf(file));
  const found = read.flatMap(({ path, file }) => floorConstants(file).map((f) => `${path} ${f}`));
  expect(searched(found, { of: variables.length, what: "variables in the tests" })).toEqual([]);
  expect(floorBreach("literal-floors.variables", variables.length)).toBeUndefined();
});
```


- [ ] **Step 2: Write the red form.**

**`extension/tests/lib/literal-floors.ts`** (new)

<!-- file: extension/tests/lib/literal-floors.ts -->
```typescript
/**
 * A floor typed into a test (spec §14.2, AC1): a literal lower bound on a population, which is
 * tight only on the day it is measured. Floors live in `tests/floors.json`; this reader refuses
 * every way a test can write one by hand. A bound of 0 is a non-emptiness check, not a floor, and
 * a ceiling (`toBeLessThan`) is a budget, not a floor; both are allowed.
 */
import { lineOf, nodes, ts, UnreadableSourceError } from "./source.ts";

const LOWER = new Set(["toBeGreaterThan", "toBeGreaterThanOrEqual"]);
const UPPER = new Set(["toBeLessThan", "toBeLessThanOrEqual"]);
const MODIFIERS = new Set(["not", "resolves", "rejects"]);
const KINDS = new Set(["soft", "poll"]);

/** Whether `node` is an assertion: `expect(…)`, `expect.soft(…)` or `expect.poll(…)`. */
export const isAssertion = (node: ts.Node): node is ts.CallExpression => {
  throw new Error("not implemented: isAssertion");
};

/** Every assertion in `file`. */
export const assertionsOf = (file: ts.SourceFile): ts.CallExpression[] => {
  throw new Error("not implemented: assertionsOf");
};

/** The number a literal writes, with its sign; `undefined` for anything else. */
const literalValue = (node: ts.Node): number | undefined => {
  throw new Error("not implemented: literalValue");
};

const isFloor = (node: ts.Node): boolean => {
  throw new Error("not implemented: isFloor");
};

/** The literal `name` is declared with in `file`, `undefined` if it is computed; a name not
 * declared there as a variable cannot be classified, so it is refused by name. */
const boundOf = (file: ts.SourceFile, name: ts.Identifier): ts.Node | undefined => {
  throw new Error("not implemented: boundOf");
};

/** The lower-bound matcher `node` calls on an assertion, with its argument, if it is one. */
const lowerBound = (node: ts.Node): { matcher: string; bound: ts.Expression } | undefined => {
  throw new Error("not implemented: lowerBound");
};

const COMPARISONS = new Map<ts.SyntaxKind, "left" | "right">([
  [ts.SyntaxKind.GreaterThanToken, "right"],
  [ts.SyntaxKind.GreaterThanEqualsToken, "right"],
  [ts.SyntaxKind.LessThanToken, "left"],
  [ts.SyntaxKind.LessThanEqualsToken, "left"],
]);

/** A comparison inside an assertion's subject that bounds a value from below by a literal. */
const isLiteralComparison = (node: ts.Node): node is ts.BinaryExpression => {
  throw new Error("not implemented: isLiteralComparison");
};

/** Every literal floor `file`'s assertions write, by line. */
export const literalFloors = (file: ts.SourceFile): string[] => {
  throw new Error("not implemented: literalFloors");
};

/** Every node under `node`, by the compiler's child walk. */
const descendants = (node: ts.Node): ts.Node[] => {
  throw new Error("not implemented: descendants");
};

const FLOOR_NAME = /floor/iu;

/** The variables `file` declares by name: the population the floor-constant check judges. */
export const variablesOf = (file: ts.SourceFile): ts.VariableDeclaration[] => {
  throw new Error("not implemented: variablesOf");
};

/** Every constant named like a floor that `file` sets to a literal, by line. */
export const floorConstants = (file: ts.SourceFile): string[] => {
  throw new Error("not implemented: floorConstants");
};
```


- [ ] **Step 3: Watch them fail.** `npx vitest run tests/literal-floors.test.ts`. Measured: 79 of 79 new tests fail: 30 on `Error: not implemented: literalFloors`, 21 on `variablesOf`, 21 on `assertionsOf`, 3 on `floorConstants`, three refusals on their own assertion, and the walk case on its floor (`expected 'floor literal-floors.files: none reco…' to be undefined`).

<!-- check: red -->

- [ ] **Step 4: Implement.**

**`extension/tests/floors.json`** (changed: 1 edit)

<!-- edit: extension/tests/floors.json -->
Replace:
```json
  "browser-globals.identifiers": 1,
  "compiler-home.imports": 83,
  "compiler-home.uses": 123,
  "core.files": 1,
  "import-direction.files": 9,
  "import-direction.imports": 12,
  "number-types.values": 1,
  "number-words.nodes": 7,
  "source.files": 28,
  "workspace.locked-packages": 198
```
with:
```json
  "browser-globals.identifiers": 1,
  "compiler-home.imports": 90,
  "compiler-home.uses": 175,
  "core.files": 1,
  "import-direction.files": 9,
  "import-direction.imports": 12,
  "literal-floors.assertions": 135,
  "literal-floors.files": 20,
  "literal-floors.variables": 247,
  "number-types.values": 1,
  "number-words.nodes": 7,
  "source.files": 30,
  "workspace.locked-packages": 198
```

**`extension/tests/lib/literal-floors.ts`** (changed: 5 edits)

<!-- edit: extension/tests/lib/literal-floors.ts -->
Replace:
```typescript
export const isAssertion = (node: ts.Node): node is ts.CallExpression => {
  throw new Error("not implemented: isAssertion");
};

/** Every assertion in `file`. */
export const assertionsOf = (file: ts.SourceFile): ts.CallExpression[] => {
  throw new Error("not implemented: assertionsOf");
};

/** The number a literal writes, with its sign; `undefined` for anything else. */
const literalValue = (node: ts.Node): number | undefined => {
  throw new Error("not implemented: literalValue");
};

const isFloor = (node: ts.Node): boolean => {
  throw new Error("not implemented: isFloor");
};
```
with:
```typescript
export const isAssertion = (node: ts.Node): node is ts.CallExpression => {
  if (!ts.isCallExpression(node)) {
    return false;
  }
  const callee = node.expression;
  if (ts.isIdentifier(callee)) {
    return callee.text === "expect";
  }
  return (
    ts.isPropertyAccessExpression(callee) &&
    ts.isIdentifier(callee.expression) &&
    callee.expression.text === "expect" &&
    KINDS.has(callee.name.text)
  );
};

/** Every assertion in `file`. */
export const assertionsOf = (file: ts.SourceFile): ts.CallExpression[] =>
  nodes(file).filter(isAssertion);

/** The number a literal writes, with its sign; `undefined` for anything else. */
const literalValue = (node: ts.Node): number | undefined => {
  if (ts.isNumericLiteral(node) || ts.isBigIntLiteral(node)) {
    return Number(node.text.replaceAll("_", "").replace(/n$/u, ""));
  }
  if (ts.isPrefixUnaryExpression(node) && node.operator === ts.SyntaxKind.MinusToken) {
    const value = literalValue(node.operand);
    return value === undefined ? undefined : -value;
  }
  return undefined;
};

const isFloor = (node: ts.Node): boolean => {
  const value = literalValue(node);
  return value !== undefined && value !== 0;
};
```

<!-- edit: extension/tests/lib/literal-floors.ts -->
Replace:
```typescript
const boundOf = (file: ts.SourceFile, name: ts.Identifier): ts.Node | undefined => {
  throw new Error("not implemented: boundOf");
};
```
with:
```typescript
const boundOf = (file: ts.SourceFile, name: ts.Identifier): ts.Node | undefined => {
  const declared = nodes(file).find(
    (node): node is ts.VariableDeclaration =>
      ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === name.text,
  );
  if (declared?.initializer === undefined) {
    throw new UnreadableSourceError(
      `${file.fileName} line ${String(lineOf(file, name))}: cannot tell whether ${name.text} is ` +
        "a literal floor; bound an assertion by a value computed in the test, or by a recorded floor",
    );
  }
  return isFloor(declared.initializer) ? declared.initializer : undefined;
};
```

<!-- edit: extension/tests/lib/literal-floors.ts -->
Replace:
```typescript
const lowerBound = (node: ts.Node): { matcher: string; bound: ts.Expression } | undefined => {
  throw new Error("not implemented: lowerBound");
};
```
with:
```typescript
const lowerBound = (node: ts.Node): { matcher: string; bound: ts.Expression } | undefined => {
  if (!ts.isCallExpression(node) || !ts.isPropertyAccessExpression(node.expression)) {
    return undefined;
  }
  const matcher = node.expression.name.text;
  let receiver = node.expression.expression;
  let negated = false;
  while (ts.isPropertyAccessExpression(receiver) && MODIFIERS.has(receiver.name.text)) {
    negated = negated !== (receiver.name.text === "not");
    receiver = receiver.expression;
  }
  const [bound] = node.arguments;
  const lower = negated ? UPPER.has(matcher) : LOWER.has(matcher);
  return lower && isAssertion(receiver) && bound !== undefined
    ? { matcher: `${negated ? "not." : ""}${matcher}`, bound }
    : undefined;
};
```

<!-- edit: extension/tests/lib/literal-floors.ts -->
Replace:
```typescript
const isLiteralComparison = (node: ts.Node): node is ts.BinaryExpression => {
  throw new Error("not implemented: isLiteralComparison");
};

/** Every literal floor `file`'s assertions write, by line. */
export const literalFloors = (file: ts.SourceFile): string[] => {
  throw new Error("not implemented: literalFloors");
};

/** Every node under `node`, by the compiler's child walk. */
const descendants = (node: ts.Node): ts.Node[] => {
  throw new Error("not implemented: descendants");
};
```
with:
```typescript
const isLiteralComparison = (node: ts.Node): node is ts.BinaryExpression => {
  if (!ts.isBinaryExpression(node)) {
    return false;
  }
  const side = COMPARISONS.get(node.operatorToken.kind);
  return side !== undefined && isFloor(node[side]);
};

/** Every literal floor `file`'s assertions write, by line. */
export const literalFloors = (file: ts.SourceFile): string[] =>
  nodes(file).flatMap((node) => {
    const at = `line ${String(lineOf(file, node))}`;
    if (isAssertion(node)) {
      return node.arguments
        .flatMap((argument) => [argument, ...descendants(argument)])
        .filter(isLiteralComparison)
        .map((comparison) => `${at}: ${comparison.getText(file)}`);
    }
    const found = lowerBound(node);
    if (found === undefined) {
      return [];
    }
    const { matcher, bound } = found;
    if (ts.isIdentifier(bound)) {
      const literal = boundOf(file, bound);
      return literal === undefined
        ? []
        : [`${at}: ${matcher}(${bound.text} = ${literal.getText(file)})`];
    }
    return isFloor(bound) ? [`${at}: ${matcher}(${bound.getText(file)})`] : [];
  });

/** Every node under `node`, by the compiler's child walk. */
const descendants = (node: ts.Node): ts.Node[] => {
  const found: ts.Node[] = [];
  const visit = (child: ts.Node): void => {
    found.push(child);
    ts.forEachChild(child, visit);
  };
  ts.forEachChild(node, visit);
  return found;
};
```

<!-- edit: extension/tests/lib/literal-floors.ts -->
Replace:
```typescript
/** The variables `file` declares by name: the population the floor-constant check judges. */
export const variablesOf = (file: ts.SourceFile): ts.VariableDeclaration[] => {
  throw new Error("not implemented: variablesOf");
};

/** Every constant named like a floor that `file` sets to a literal, by line. */
export const floorConstants = (file: ts.SourceFile): string[] => {
  throw new Error("not implemented: floorConstants");
};
```
with:
```typescript
/** The variables `file` declares by name: the population the floor-constant check judges. */
export const variablesOf = (file: ts.SourceFile): ts.VariableDeclaration[] =>
  nodes(file).filter(
    (node): node is ts.VariableDeclaration =>
      ts.isVariableDeclaration(node) && ts.isIdentifier(node.name),
  );

/** Every constant named like a floor that `file` sets to a literal, by line. */
export const floorConstants = (file: ts.SourceFile): string[] =>
  variablesOf(file).flatMap((variable) => {
    const { name, initializer } = variable;
    return FLOOR_NAME.test(name.getText(file)) && initializer !== undefined && isFloor(initializer)
      ? [
          `line ${String(lineOf(file, variable))}: ${name.getText(file)} = ${initializer.getText(file)}`,
        ]
      : [];
  });
```


- [ ] **Step 5: Confirm the floors and run the gate.** `npm run floors:record` prints `no floor moved` (the file was recorded from Task 4's, printing the six Task 5 lines under **The floors each task records**); then the gate.

<!-- check: gate -->

- [ ] **Step 6: The mutation checks** below, on this final tree.
- [ ] **Step 7: Commit** `feat(extension): #221 no literal floor in any TypeScript test (Refs #221)`.

## Mutation checks

Run once after Task 5, on the final tree, each predicted before it ran (AC6): for every guard, the reader blinded entirely, blinded to one form, and its walk narrowed. A mutation passes only when the set of failing tests equals its prediction exactly and the total test count equals the baseline plus the change the mutation predicts (a narrowed walk leaves per-file cases out: L6 −6, C8 −1; C9's planted module adds 3). The file is restored after each, and C9's planted module is removed. Where a prediction spans a population (S1, S2, S3, I1, L6), it is derived from a census the guard's own readers took of the final tree, never typed. I5, C8 and C9 also name the assertion each red test must fail through: `core` holds one module, so its walk narrowed is its loss (C8, red through the empty-population refusal, no floor named), and its growth is C9 (red through each floor over `core`).

| Id | File | Mutation | Change | Predicted red | Run |
|---|---|---|---|---|---|
| F1 | `extension/tests/lib/floors.ts` | growth blind | `if (measured > recorded + 1) {` | growth breaks the floor until it is recorded, naming the delta | 1 red of 29, as predicted |
| F2 | `extension/tests/lib/floors.ts` | the recorder lowers | `} else if (figure !== before) {` | a recording with a refusal prints it and writes nothing; the recorder never lowers a floor | 2 red of 29, as predicted |
| F3 | `extension/tests/lib/floors.ts` | record mode allowed in CI | `if (env.CI === "never") {` | recording refuses to run in CI, so CI can never pass a floor unjudged | 1 red of 29, as predicted |
| F4 | `extension/tests/lib/floors.ts` | two owners allowed | `if (tests.length > 2) {` | the recorder refuses an id asserted from two places | 1 red of 29, as predicted |
| F5 | `extension/tests/lib/floors.ts` | stale ids kept | `.filter(() => false)` | the recorder refuses a recorded id that no test asserts any more | 1 red of 29, as predicted |
| F6 | `extension/tests/lib/floors.ts` | the owner read from expect's stale state | `import { expect, type RunnerTestCase, TestRunner } from "vitest";` | after a test has run > a floor recorded from a suite's hook is refused, not credited to the test before; recording appends the measurement and the test that asserted it, and judges nothing | 2 red of 29, as predicted |
| F7 | `extension/tests/lib/population.ts` | BlindGuardError loses its name | `removed: override name = "BlindGuardError";` | the refusal is a BlindGuardError by name | 1 red of 3, as predicted |
| P1 | `tests/meta/test_extension_ci.py` | workflow values unread | `removed: elif isinstance(node, str):` | test_the_recorder_is_found_wherever_a_workflow_names_it[path]; test_the_recorder_is_found_wherever_a_workflow_names_it[run] | 2 red of 13, as predicted |
| P2 | `tests/meta/test_extension_ci.py` | workflow keys unread | `removed: yield str(key)` | test_the_recorder_is_found_wherever_a_workflow_names_it[env-name] | 1 red of 13, as predicted |
| P3 | `tests/meta/test_extension_ci.py` | the workflow walk narrowed to nothing | `files: list[Path] = []` | test_no_workflow_runs_the_floors_recorder | 1 red of 13, as predicted |
| P4 | `tests/meta/test_extension_ci.py` | npm scripts unread | `others: dict[str, str] = {}` | test_no_other_npm_script_reaches_the_floors_recorder | 1 red of 13, as predicted |
| S1 | `extension/tests/lib/source.ts` | node walk blind | `removed: ts.forEachChild(file, visit);` | a file with no error is compiled, and its checker reads its types; a name in code after a JSDoc comment is read as code; a name in code after a block comment is read as code; a name in code after a double-quoted string is read as code; a name in code after a line comment is read as code; a name in code after a regex holding a slash in a character class is read as code; a name in code after a regex literal after a return is read as code; a name in code after a regex literal is read as code; a name in code after a single-quoted string is read as code; a name in code after a template is read as code; a name in code after a template's text around a substitution is read as code; a name inside a template's substitution is code; a node's line is counted from 1; build.ts: the node walk and the token walk read the same names; eslint.config.js: the node walk and the token walk read the same names; only tests/lib/source.ts calls the compiler's readers, and ts is reached only as ts.X; packages/core/src/index.ts: the node walk and the token walk read the same names; packages/core/test/index.test.ts: the node walk and the token walk read the same names; packages/history/src/index.ts: the node walk and the token walk read the same names; packages/history/test/index.test.ts: the node walk and the token walk read the same names; packages/readers/src/index.ts: the node walk and the token walk read the same names; packages/readers/test/index.test.ts: the node walk and the token walk read the same names; packages/shell/src/side-panel.ts: the node walk and the token walk read the same names; playwright.config.ts: the node walk and the token walk read the same names; tests/build.test.ts: the node walk and the token walk read the same names; tests/core-rules.test.ts: the node walk and the token walk read the same names; tests/floors.test.ts: the node walk and the token walk read the same names; tests/import-direction.test.ts: the node walk and the token walk read the same names; tests/lib/core-rules.ts: the node walk and the token walk read the same names; tests/lib/floors.ts: the node walk and the token walk read the same names; tests/lib/imports.ts: the node walk and the token walk read the same names; tests/lib/literal-floors.ts: the node walk and the token walk read the same names; tests/lib/population.ts: the node walk and the token walk read the same names; tests/lib/source.ts: the node walk and the token walk read the same names; tests/lib/walk.ts: the node walk and the token walk read the same names; tests/literal-floors.test.ts: the node walk and the token walk read the same names; tests/population.test.ts: the node walk and the token walk read the same names; tests/record-floors.ts: the node walk and the token walk read the same names; tests/source.test.ts: the node walk and the token walk read the same names; tests/toolchain.test.ts: the node walk and the token walk read the same names; tests/workspace.test.ts: the node walk and the token walk read the same names; vitest.config.ts: the node walk and the token walk read the same names | 42 red of 64, as predicted |
| S2 | `extension/tests/lib/source.ts` | token walk blind to regex literals | `node.kind !== ts.SyntaxKind.EndOfFileToken && node.kind !== ts.SyntaxK` | code text empties every literal and keeps the code around it; tests/build.test.ts: the node walk and the token walk read the same names; tests/floors.test.ts: the node walk and the token walk read the same names; tests/import-direction.test.ts: the node walk and the token walk read the same names; tests/lib/core-rules.ts: the node walk and the token walk read the same names; tests/lib/literal-floors.ts: the node walk and the token walk read the same names; tests/literal-floors.test.ts: the node walk and the token walk read the same names; tests/source.test.ts: the node walk and the token walk read the same names; tests/workspace.test.ts: the node walk and the token walk read the same names | 9 red of 64, as predicted |
| S3 | `extension/tests/lib/walk.ts` | file walk narrowed (tests/lib left out) | `const SKIPPED = new Set(["node_modules", "dist", "coverage", "lib"]);` | no test keeps a floor in a constant; only tests/lib/source.ts calls the compiler's readers, and ts is reached only as ts.X; only tests/lib/source.ts imports the TypeScript compiler; the files read are the ones git lists, and as many as recorded; the test files read are the ones git lists, and as many as recorded | 5 red of 263, as predicted |
| S4 | `extension/tests/lib/source.ts` | a syntax error read anyway | `if (diagnostics.length > 99) {` | a file with a syntax error is refused by name, line and column | 1 red of 64, as predicted |
| S5 | `extension/tests/lib/source.ts` | a compiler error read anyway | `if (errors.length > 99) {` | a file with a compiler error is refused by name, not judged | 1 red of 64, as predicted |
| S6 | `extension/tests/lib/source.ts` | UnreadableSourceError loses its name | `removed: override name = "UnreadableSourceError";` | the refusal is an UnreadableSourceError by name | 1 red of 291, as predicted |
| I1 | `extension/tests/lib/imports.ts` | import reader blind | `return specifier === undefined ? [] : [];` | a dynamic import from core is refused by file and line; a relative path into another package from core is refused by file and line; a require call from core is refused by file and line; a side-effect import from core is refused by file and line; a type's import from core is refused by file and line; a type-only import from core is refused by file and line; an export from from core is refused by file and line; an export of everything from from core is refused by file and line; an import from core is refused by file and line; an import-equals require from core is refused by file and line; build.ts: the tree reader finds the imports the pre-scanner finds; core importing history is refused; core importing readers is refused; core importing shell is refused; eslint.config.js: the tree reader finds the imports the pre-scanner finds; history importing shell is refused; no package imports a package above it; only tests/lib/source.ts imports the TypeScript compiler; packages/core/test/index.test.ts: the tree reader finds the imports the pre-scanner finds; packages/history/src/index.ts: the tree reader finds the imports the pre-scanner finds; packages/history/test/index.test.ts: the tree reader finds the imports the pre-scanner finds; packages/readers/src/index.ts: the tree reader finds the imports the pre-scanner finds; packages/readers/test/index.test.ts: the tree reader finds the imports the pre-scanner finds; packages/shell/src/side-panel.ts: the tree reader finds the imports the pre-scanner finds; playwright.config.ts: the tree reader finds the imports the pre-scanner finds; readers importing shell is refused; tests/build.test.ts: the tree reader finds the imports the pre-scanner finds; tests/core-rules.test.ts: the tree reader finds the imports the pre-scanner finds; tests/floors.test.ts: the tree reader finds the imports the pre-scanner finds; tests/import-direction.test.ts: the tree reader finds the imports the pre-scanner finds; tests/lib/core-rules.ts: the tree reader finds the imports the pre-scanner finds; tests/lib/floors.ts: the tree reader finds the imports the pre-scanner finds; tests/lib/imports.ts: the tree reader finds the imports the pre-scanner finds; tests/lib/literal-floors.ts: the tree reader finds the imports the pre-scanner finds; tests/lib/source.ts: the tree reader finds the imports the pre-scanner finds; tests/lib/walk.ts: the tree reader finds the imports the pre-scanner finds; tests/literal-floors.test.ts: the tree reader finds the imports the pre-scanner finds; tests/population.test.ts: the tree reader finds the imports the pre-scanner finds; tests/record-floors.ts: the tree reader finds the imports the pre-scanner finds; tests/source.test.ts: the tree reader finds the imports the pre-scanner finds; tests/toolchain.test.ts: the tree reader finds the imports the pre-scanner finds; tests/workspace.test.ts: the tree reader finds the imports the pre-scanner finds; vitest.config.ts: the tree reader finds the imports the pre-scanner finds | 43 red of 61, as predicted |
| I2 | `extension/tests/lib/imports.ts` | blind to export … from | `if (false && ts.isExportDeclaration(node) && node.moduleSpecifier !== ` | an export from from core is refused by file and line; an export of everything from from core is refused by file and line | 2 red of 61, as predicted |
| I3 | `extension/tests/lib/imports.ts` | core may import history | `core: ["readers", "shell"],` | core importing history is refused | 1 red of 61, as predicted |
| I4 | `extension/tests/lib/imports.ts` | relative paths read as external | `if (specifier.startsWith("..../")) {` | a relative path into another package from core is refused by file and line; a relative path leaving the packages is refused by name | 2 red of 61, as predicted |
| I5 | `extension/tests/import-direction.test.ts` | the package walk narrowed (history left out) | `const PACKAGE_FILES = filesUnder("packages", SUFFIXES).filter((path) =` | no package imports a package above it; the package files read are the ones git lists, and as many as recorded | 2 red of 61, as predicted |
| C1 | `extension/tests/lib/core-rules.ts` | browser-global reader blind | `nodes(file).slice(0, 0).flatMap(` | a computed key into a global object cannot be judged, and is refused by name; core reaching a bare global is refused; core reaching a key into globalThis is refused; core reaching a property of globalThis is refused; core reaching a property of self is refused; core reaching a shorthand property is refused; core reaching a typeof is refused; core reaching chrome is refused; core reaching document is refused; core reaching indexedDB is refused; core reaching window's own document is refused | 11 red of 87, as predicted |
| C2 | `extension/tests/lib/core-rules.ts` | blind to a key into a global object | `if (false) {` | a computed key into a global object cannot be judged, and is refused by name; core reaching a key into globalThis is refused | 2 red of 87, as predicted |
| C3 | `extension/tests/lib/core-rules.ts` | blind to the number keyword | `if (false) {` | core writing a satisfies is refused; core writing a type argument is refused; core writing an annotation is refused; core writing an array type is refused; core writing an assertion is refused | 5 red of 87, as predicted |
| C4 | `extension/tests/lib/core-rules.ts` | the normalised literal judged | `!WHOLE.test(node.text)` | core writing an exponent is refused | 1 red of 87, as predicted |
| C5 | `extension/tests/lib/core-rules.ts` | type pass blind | `return false;` | the type pass judges a callback's parameter; the type pass judges a class field; the type pass judges a destructured name; the type pass judges a function's result; the type pass judges a getter's result; the type pass judges a length kept in a name; the type pass judges a let; the type pass judges a literal type in an interface; the type pass judges a method's result; the type pass judges a parameter; the type pass judges an array of them; the type pass judges an arrow's result; the type pass judges an object literal holding one; the type pass judges an unlabelled whole number | 14 red of 87, as predicted |
| C6 | `extension/tests/lib/core-rules.ts` | type pass blind to anonymous object types | `if (false) {` | the type pass judges an object literal holding one | 1 red of 87, as predicted |
| C7 | `extension/tests/lib/core-rules.ts` | type pass walk misses parameters | `removed: ts.SyntaxKind.Parameter,` | the token walk counts the values the type pass judges in a callback's parameter; the token walk counts the values the type pass judges in a comparator's result; the token walk counts the values the type pass judges in a parameter; the type pass judges a callback's parameter; the type pass judges a parameter | 5 red of 87, as predicted |
| C8 | `extension/tests/core-rules.test.ts` | core's walk loses its one file | `const CORE = filesUnder("packages/core/src", SUFFIXES).filter(() => fa` | core reaches no browser global; core writes no number; core's files are the ones git lists, and as many as recorded; no value in core has a number type, written or inferred | 4 red of 86, as predicted |
| C9 | `extension/packages/core/src/planted.ts` | core grows by a planted second module | `/** Planted by mutation C9: a second module in core. */` | core reaches no browser global; core writes no number; core's files are the ones git lists, and as many as recorded; no value in core has a number type, written or inferred; the files read are the ones git lists, and as many as recorded; the package files read are the ones git lists, and as many as recorded | 6 red of 215, as predicted |
| L1 | `extension/tests/lib/literal-floors.ts` | literal-floor reader blind | `nodes(file).slice(0, 0).flatMap(` | a bound held in a name declared with no value cannot be classified, and is refused by name; a bound held in a parameter cannot be classified, and is refused by name; a bound held in an imported name cannot be classified, and is refused by name; a floor bound to a named literal is refused, naming both; a floor written as a bigint is refused by line; a floor written as a comparison is refused by line; a floor written as a negated toBeLessThan is refused by line; a floor written as a negated toBeLessThanOrEqual is refused by line; a floor written as a negative literal is refused by line; a floor written as a polled assertion is refused by line; a floor written as a resolved value is refused by line; a floor written as a reversed comparison is refused by line; a floor written as a reversed strict comparison is refused by line; a floor written as a separated literal is refused by line; a floor written as a soft assertion is refused by line; a floor written as a strict comparison is refused by line; a floor written as toBeGreaterThan is refused by line; a floor written as toBeGreaterThanOrEqual is refused by line | 18 red of 79, as predicted |
| L2 | `extension/tests/lib/literal-floors.ts` | blind to negation | `const lower = LOWER.has(matcher);` | a floor written as a negated toBeLessThan is refused by line; a floor written as a negated toBeLessThanOrEqual is refused by line; a negated lower bound is not a literal floor | 3 red of 79, as predicted |
| L3 | `extension/tests/lib/literal-floors.ts` | blind to a reversed comparison | `removed: [ts.SyntaxKind.LessThanEqualsToken, "left"],` | a floor written as a reversed comparison is refused by line | 1 red of 79, as predicted |
| L4 | `extension/tests/lib/literal-floors.ts` | blind to expect.soft and expect.poll | `const KINDS = new Set<string>([]);` | a floor written as a polled assertion is refused by line; a floor written as a soft assertion is refused by line | 2 red of 79, as predicted |
| L5 | `extension/tests/lib/literal-floors.ts` | floor names matched by case | `const FLOOR_NAME = /floor/u;` | a constant named FILES_FLOOR set to a literal is refused; a constant named a negative one set to a literal is refused; a constant named filesFloor set to a literal is refused | 3 red of 79, as predicted |
| L6 | `extension/tests/literal-floors.test.ts` | walk narrowed to tests/ (package tests left out) | `path.startsWith("tests/");` | no test bounds an assertion by a literal floor; the test files read are the ones git lists, and as many as recorded | 2 red of 73, as predicted |

## After the merge

- `deploy-dev` runs on the develop push and verifies the attested zip; read every job by name.
- Close #221 with the evidence (gates, red phase, the mutation table, the develop run); move it to Done on the board.
- #272 (Python's literal floors) is unblocked.

## Review log

**Pass 1 (2026-10-07), mechanical and whole-document; 6 findings, all fixed:**
1. Splitting the green WIP commit by whole files did not make each commit green: Task 2 alone covered `tests/lib/source.ts` at 67% (`typeChecked` was tested only from `core-rules.test.ts`, `preScannedImports` only by Task 3's cross-check). Fixed in the code: the four `typeChecked` refusal tests moved to `source.test.ts`, which tests `source.ts`, with a success-path test and a scratch-directory helper that removes what it writes (the old `fixture()` left a temp directory per call); `preScannedImports` arrives in Task 3. The chain builder now runs coverage on every task's tree before committing it.
2. AC6 asks for each guard's walk narrowed; the import-direction package walk and core's walk had none. Added I5, C8 (core holds one module, so narrowing is its loss) and C9 (its growth), each naming the assertion it must fail through.
3. Two red-phase passes had no mutation proving them: the `BlindGuardError` and `UnreadableSourceError` "by name" tests (the classes are kept in the red form). Added F7 and S6.
4. The floors steps said the recorder prints `new, 198` on a tree where the figure is already pasted; it prints `no floor moved` (measured on the final tree). Reworded in every task.
5. The mutation section claimed the test total is always unchanged; L6 (−6), C8 (−1) and C9 (+3) change it by design. Reworded, and S1, S2, I1 named as census-derived alongside S3 and L6.
6. Review Focus named "another session's heavy run listed beside this one" as the load's source. The lock's holder notes outlive their runs (#274's closing comment); corrected.

Measured and recorded while running: one timeout of a 0.7 s test at load 20 (Review Focus 5); I5's and C9's red sets matched on the first run, but their message checks were longer than Vitest prints (it cuts a string at about 40 characters), so the texts were shortened to the printed part after the run; Vitest 5's `Isolate` summary line in the recorder's output is a timing report, not a warning (file isolation is kept). The test lock missed `uv run` and nested harnesses during this work: fixed separately as #274.

**Pass 2 (2026-10-07), the whole filled document; 1 finding, fixed:** Task 2 ships `typeChecked` since pass 1, but its title and commit message named only the reader and the walk.

**Pass 3 (2026-10-07), mechanical (10 of 10 replay trees identical, 37 mutation rows, every table row well-formed) and the mutation table read row by row; 1 finding, fixed:** Decision 7 said #222 "recognises" the helper, a claim about a story not yet built; it now says #222 builds on it.

**Pass 4 (2026-10-07), mechanical and the changed sentence read in place: no findings.** The plan is approved (Shyden's rule: reviewed to zero, then self-approved).
