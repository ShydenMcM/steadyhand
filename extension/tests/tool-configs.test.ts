/**
 * ESLint's and Playwright's configurations loaded in-process with the tools stood in (#374 AC6):
 * the real modules cost more to load than a unit file may spend (measured 2026-10-22: the ESLint
 * config 582-759 ms of CPU, the Playwright config 280-297 ms, against the 100 ms load limit), so
 * here each tool is a stand-in module that hands back what it was given, and every line of both
 * files runs. No module mock (#394: Vitest rewrites a file that mocks one, and Node's own coverage
 * can only measure a file that runs as written): Node's own module hooks resolve each tool to its
 * stand-in while the two configurations load. A hook is matched on where the tool resolves to, not
 * the specifier it is asked for: Vitest's module runner resolves a package itself and asks Node for
 * its file path, a native load asks with the package's name (measured 2026-10-23). The real tools
 * load them in `tests/integration/tool-configs.test.ts`.
 */
import { registerHooks } from "node:module";
import { join } from "node:path";
import { expect, test } from "vitest";

/** Each tool the configurations import, by the URL it resolves to, and its stand-in's source. */
const STAND_INS = new Map(
  Object.entries({
    "@eslint/js":
      'export default { configs: { recommended: { name: "stood-in js recommended" } } };',
    "typescript-eslint":
      'export default { configs: { strictTypeChecked: [{ name: "stood-in strict, type-checked" }] } };',
    "eslint/config":
      "export const defineConfig = (...configs) => configs;\n" +
      "export const globalIgnores = (ignores) => ({ stoodInIgnores: ignores });",
    "@playwright/test": "export const defineConfig = (config) => ({ stoodIn: config });",
  }).map(([tool, source]) => [import.meta.resolve(tool), source]),
);

const hooks = registerHooks({
  resolve(specifier, context, nextResolve) {
    const resolved = nextResolve(specifier, context);
    const source = STAND_INS.get(resolved.url);
    return source === undefined
      ? resolved
      : { url: `data:text/javascript,${encodeURIComponent(source)}`, shortCircuit: true };
  },
});
const { default: eslint } = await import("../eslint.config.js");
const { default: playwright } = await import("../playwright.config.ts");
hooks.deregister();

test("ESLint ignores the build and coverage output, then applies each rule set in order", () => {
  expect(eslint).toEqual([
    { stoodInIgnores: ["dist/", "coverage/"] },
    { name: "stood-in js recommended" },
    [{ name: "stood-in strict, type-checked" }],
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
