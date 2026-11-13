// #570 probe: the integration project alone, with a setup file recording each test's assertions.
import { defineConfig } from "vitest/config";
import { INTEGRATION } from "./vitest.config.ts";

export default defineConfig({
  test: { include: [INTEGRATION], setupFiles: ["./count-setup.ts"] },
});
