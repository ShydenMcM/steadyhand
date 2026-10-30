import { configDefaults, defineConfig } from "vitest/config";

/** The packages held to 100% coverage (spec §14.1). The shell's side panel is measured in unit with
 * its document stood in (#374 AC5); its content script and service worker are `export {};`
 * placeholders with nothing to count, unmeasured until EXT S14a writes them (Shyden, 2026-10-23:
 * "Leave until S14a"), so the coverage gate fails any change to them until then. */
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
 * `--mode guards`; any other mode is a unit run. The build and the tool configurations are loaded
 * in-process with their tools stood in (#374 AC6: `tests/build.test.ts`, `tests/tool-configs.test.ts`). */
export const UNIT_COVERED = [
  ...COVERED.map((name) => `packages/${name}/src/**/*.ts`),
  "packages/shell/src/side-panel.ts",
  "build.ts",
  "eslint.config.js",
  "playwright.config.ts",
  "tests/lib/node-coverage.ts",
  "tests/lib/found.ts",
  "tests/lib/no-process.ts",
  "tests/lib/program.ts",
];
export const GUARDS_COVERED = [
  "tests/lib/core-rules.ts",
  "tests/lib/imports.ts",
  "tests/lib/module-mocks.ts",
  "tests/lib/raised-limits.ts",
  "tests/lib/source.ts",
  "tests/lib/walk.ts",
  "tests/node-coverage-report.ts",
];

export default defineConfig(({ mode }) => ({
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: "unit",
          include: ["packages/*/test/**/*.test.ts", "tests/**/*.test.ts"],
          exclude: [...configDefaults.exclude, GUARDS, INTEGRATION],
          // Node's coverage writer first, so its hook runs after every other setup file's (#394);
          // then the refusal, so nothing a test file imports can start a process unseen.
          setupFiles: [FLUSH_NODE_COVERAGE, "tests/no-process.ts"],
          // The one place a limit is set: every unit test and hook runs in under 1 s.
          testTimeout: 1_000,
          hookTimeout: 1_000,
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
