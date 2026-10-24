import { defineConfig } from "@playwright/test";

// A retry turns a real failure into a pass (Shyden's global rule), so there are none, anywhere.
// Named before it is exported, so coverage counts it (see eslint.config.js, #374 AC6).
const config = defineConfig({
  testDir: "tests/browser",
  retries: 0,
  forbidOnly: true,
});

export default config;
