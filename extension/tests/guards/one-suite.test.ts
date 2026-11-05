import { readdirSync, readFileSync } from "node:fs";
import { expect, test } from "vitest";

// One suite, run unchanged on every browser, nothing skipped (Shyden's global rule, 2026-11-05;
// #501): no browser test is skipped, marked to fix later, or filtered to some browsers only.
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
  ["a skipped test", 'test.skip("a", async () => {});'],
  ["a conditional skip", 'test.skip(browserName === "webkit");'],
  ["a test to fix later", 'test.fixme("a", async () => {});'],
  ["a test expected to fail", "test.fail();"],
  ["a described skip", 'test.describe.skip("a", () => {});'],
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
