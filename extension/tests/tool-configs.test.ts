/**
 * ESLint's and Playwright's configurations loaded in-process with the tools stood in (#374 AC6):
 * the real modules cost more to load than a unit file may spend (measured 2026-10-22: the ESLint
 * config 582-759 ms of CPU, the Playwright config 280-297 ms, against the 100 ms load limit), so
 * here each tool's helpers are mocks that hand back what they were given, and every line of both
 * files runs. The real tools load them in `tests/integration/tool-configs.test.ts`.
 */
import { join } from "node:path";
import { expect, test, vi } from "vitest";

const tools = vi.hoisted(() => ({
  recommended: { name: "stood-in js recommended" },
  strictTypeChecked: [{ name: "stood-in strict, type-checked" }],
}));
vi.mock("@eslint/js", () => ({ default: { configs: { recommended: tools.recommended } } }));
vi.mock("typescript-eslint", () => ({
  default: { configs: { strictTypeChecked: tools.strictTypeChecked } },
}));
vi.mock("eslint/config", () => ({
  defineConfig: (...configs: unknown[]) => configs,
  globalIgnores: (ignores: string[]) => ({ stoodInIgnores: ignores }),
}));
vi.mock("@playwright/test", () => ({ defineConfig: (config: unknown) => ({ stoodIn: config }) }));

const { default: eslint } = await import("../eslint.config.js");
const { default: playwright } = await import("../playwright.config.ts");

test("ESLint ignores the build and coverage output, then applies each rule set in order", () => {
  expect(eslint).toEqual([
    { stoodInIgnores: ["dist/", "coverage/"] },
    tools.recommended,
    tools.strictTypeChecked,
    {
      languageOptions: {
        parserOptions: { projectService: true, tsconfigRootDir: join(import.meta.dirname, "..") },
      },
    },
  ]);
});

test("Playwright runs the browser tests with no retry and refuses a focused test", () => {
  expect(playwright).toEqual({
    stoodIn: { testDir: "tests/browser", retries: 0, forbidOnly: true },
  });
});
