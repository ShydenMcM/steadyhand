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
      thresholds: { branches: 100, functions: 100, lines: 100, statements: 100 },
    },
  },
});
