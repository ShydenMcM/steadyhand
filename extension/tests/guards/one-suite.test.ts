import { readdirSync, readFileSync } from "node:fs";
import { expect, test } from "vitest";

// One suite, run unchanged on every browser, nothing skipped (Shyden's global rule, 2026-11-05;
// #501): no browser test is expected to fail, slowed, or filtered out of the suite. Skips are
// caught by the shared one-suite checks on CI (#595).
const SKIPS = [
  /\.skip\b/,
  /\.fixme\b/,
  /\.fail\b/,
  /\.slow\b/,
  /\bgrep(?:Invert)?\s*:/,
  /\btestIgnore\b/,
  /\btestMatch\b/,
  /--grep\b/,
  /--project\b/,
] as const;

/** Each line of `text` that skips or filters a browser test, as `line N: text`. */
const skipsIn = (text: string): string[] =>
  text
    .split("\n")
    .map((line, at) => ({ line, at }))
    .filter(({ line }) => SKIPS.some((pattern) => pattern.test(line)))
    .map(({ line, at }) => `line ${String(at + 1)}: ${line.trim()}`);

test.each([
  ["a test expected to fail", "test.fail();"],
  ["a slowed test", "test.slow();"],
  ["a project grep", "grep: /@chrome/,"],
  ["a project grepInvert", "grepInvert: /@mobile/,"],
  ["an ignored file", 'testIgnore: "*.edge.spec.ts",'],
  ["a matched file", 'testMatch: "*.chrome.spec.ts",'],
  ["a command filter", "playwright test --grep @smoke"],
  ["one project's run", "playwright test --project=chrome"],
])("%s is refused", (_name, code) => {
  expect(skipsIn(code)).toEqual([`line 1: ${code}`]);
});

// The shared one-suite checks (playwright-devices, CI step "The same tests on every browser")
// fail a run whose report holds a skipped test, so skips are theirs; this guard keeps what a
// report cannot show (#595, Shyden 2026-11-24).
test.each([
  ["a skipped test", 'test.skip("a", async () => {});'],
  ["a conditional skip", 'test.skip(browserName === "webkit");'],
  ["a test to fix later", 'test.fixme("a", async () => {});'],
  ["a described skip", 'test.describe.skip("a", () => {});'],
])("%s is left to the shared checks", (_name, code) => {
  expect(skipsIn(code)).toEqual([]);
});

test("a plain test is not refused", () => {
  expect(skipsIn('test("a", async ({ page }) => {});')).toEqual([]);
});

const BROWSER = new URL("../browser/", import.meta.url);
const FILES = [
  new URL("../../playwright.config.ts", import.meta.url),
  ...readdirSync(BROWSER, { recursive: true, encoding: "utf8" })
    .filter((name) => name.endsWith(".ts"))
    .map((name) => new URL(name, BROWSER)),
];

test.each(FILES.map((file) => [file.pathname.split("/extension/")[1], file]))(
  "%s skips and filters no browser test",
  (_name, file) => {
    expect(skipsIn(readFileSync(file, "utf8"))).toEqual([]);
  },
);
