import { defineConfig } from "@playwright/test";

// A retry turns a real failure into a pass (Shyden's global rule), so there are none, anywhere.
export default defineConfig({
  testDir: "tests/browser",
  retries: 0,
  forbidOnly: true,
});
