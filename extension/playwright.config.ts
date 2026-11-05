import { defineConfig } from "@playwright/test";

// A retry turns a real failure into a pass (Shyden's global rule), so there are none, anywhere.
// Named before it is exported, so coverage counts it (see eslint.config.js, #374 AC6).
const config = defineConfig({
  testDir: "tests/browser",
  retries: 0,
  forbidOnly: true,
  // One suite, run unchanged on every browser the extension supports (Shyden's global rule
  // 2026-11-05, #501): no project filters or skips a test.
  projects: [
    { name: "chromium", use: { channel: "chromium" } },
    { name: "chrome", use: { channel: "chrome" } },
    { name: "msedge", use: { channel: "msedge" } },
  ],
});

export default config;
