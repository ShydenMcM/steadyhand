import { defineConfig } from "@playwright/test";
import { desktopProjects } from "@shyden-labs/playwright-devices/desktop";

// A retry turns a real failure into a pass (Shyden's global rule), so there are none, anywhere.
// Named before it is exported, so coverage counts it (see eslint.config.js, #374 AC6).
const config = defineConfig({
  testDir: "tests/browser",
  retries: 0,
  forbidOnly: true,
  // One suite, run unchanged on every browser the extension supports (Shyden's global rule
  // 2026-11-05, #501), from the shared desktop browsers (#579): a Chrome extension runs on the
  // Chromium family only. No project filters or skips a test.
  projects: desktopProjects(["chromium", "chrome", "msedge"]),
});

export default config;
