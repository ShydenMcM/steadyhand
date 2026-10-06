import { expect, test } from "vitest";
import playwright from "../playwright.config.ts";

test("Playwright never retries a failed test", () => {
  expect(playwright.retries).toBe(0);
});
