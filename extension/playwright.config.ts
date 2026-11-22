import { defineConfig } from "@playwright/test";
import { desktopProjects } from "@shyden-labs/playwright-devices/desktop";

// A retry turns a real failure into a pass (Shyden's global rule), so there are none, anywhere.
// Named before it is exported, so coverage counts it (see eslint.config.js, #374 AC6).
const config = defineConfig({
  testDir: "tests/browser",
  retries: 0,
  forbidOnly: true,
  // One suite, run unchanged on every browser the extension supports (Shyden's global rule
  // 2026-11-05, #501), on the browsers every project shares (#579): the extension is a Chrome one,
  // so it runs on the Chromium family. No project filters or skips a test. Each keeps only its
  // browser: the journeys open a real window (viewport null), which no device descriptor may set.
  projects: desktopProjects(["chromium", "chrome", "msedge"]).map((project) => ({
    ...project,
    use: project.use?.channel === undefined ? {} : { channel: project.use.channel },
  })),
});

export default config;
