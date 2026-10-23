import { configDefaults, defineConfig } from "vitest/config";
import { limitsFor } from "./tests/lib/test-clock.ts";

/** The packages held to 100% coverage (spec §14.1); the shell is proved by browser tests. */
export const COVERED = ["core", "readers", "history"] as const;

/** The whole-repo guards (#285): they read the tracked tree to check a rule across the code, so
 * they run as their own project in their own CI job (`npm run test:guards`), never in unit. */
export const GUARDS = "tests/guards/**/*.test.ts";

/** The tests whose real case needs a process or a tool too heavy for a unit file's load (#286):
 * the bundler, and each tool's own configuration loaded by the tool. Their own project and CI job
 * (`npm run test:integration`); the unit project keeps a stand-in of the build's logic. */
export const INTEGRATION = "tests/integration/**/*.test.ts";

/** The setup file every project names first (#394): it writes Node's own coverage of each test
 * file's worker, for the files Vitest's coverage cannot measure (`npm run test:native`). */
export const FLUSH_NODE_COVERAGE = "tests/flush-node-coverage.ts";

/** What each suite holds to 100% coverage: every helper in `tests/lib` is in exactly one list,
 * the list of the suite whose tests cover it (measured 2026-10-12, #285). A guards run is
 * `--mode guards`; any other mode is a unit run. */
export const UNIT_COVERED = [
  ...COVERED.map((name) => `packages/${name}/src/**/*.ts`),
  "build.ts",
  "tests/lib/floors.ts",
  "tests/lib/load-clock.ts",
  "tests/lib/node-coverage.ts",
  "tests/lib/no-process.ts",
  "tests/lib/population.ts",
  "tests/lib/test-clock.ts",
];
export const GUARDS_COVERED = [
  "tests/lib/core-rules.ts",
  "tests/lib/imports.ts",
  "tests/lib/literal-floors.ts",
  "tests/lib/module-mocks.ts",
  "tests/lib/raised-limits.ts",
  "tests/lib/source.ts",
  "tests/lib/walk.ts",
  "tests/node-coverage-report.ts",
];

export default defineConfig(({ mode }) => ({
  test: {
    // The one place a per-test limit is set (#323): 1 s per test and hook in a limits run
    // (`npm run test:limits`, no coverage), none in any other, whose CI step bounds it.
    ...limitsFor(mode),
    reporters: ["default", "./tests/load-report.ts"],
    projects: [
      {
        extends: true,
        test: {
          name: "unit",
          include: ["packages/*/test/**/*.test.ts", "tests/**/*.test.ts"],
          exclude: [...configDefaults.exclude, GUARDS, INTEGRATION],
          // Node's coverage writer first, so its hook runs after every other setup file's (#394);
          // then the refusal, so nothing a test file imports can start a process unseen; then the
          // per-test clock (#323); the load clock last, so the time it measures to each file's
          // first hook is that file's load alone.
          setupFiles: [
            FLUSH_NODE_COVERAGE,
            "tests/no-process.ts",
            "tests/test-clock.ts",
            "tests/load-clock.ts",
          ],
          // A limits run (`--mode limits`, no coverage) judges each load and test; others report.
          env: { STEADYHAND_JUDGE_LOADS: mode === "limits" ? "1" : "" },
        },
      },
      {
        extends: true,
        test: { name: "guards", include: [GUARDS], setupFiles: [FLUSH_NODE_COVERAGE] },
      },
      {
        extends: true,
        test: { name: "integration", include: [INTEGRATION], setupFiles: [FLUSH_NODE_COVERAGE] },
      },
    ],
    coverage: {
      provider: "v8",
      include: mode === "guards" ? GUARDS_COVERED : UNIT_COVERED,
      reporter: ["text"],
      thresholds: { branches: 100, functions: 100, lines: 100, statements: 100 },
    },
  },
}));
