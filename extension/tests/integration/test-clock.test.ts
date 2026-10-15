/**
 * The unit limits against real slow tests (#323): planted tests run by vitest in its own process,
 * with the real setup file and `limitsFor`. In a limits run a test that spins past 0.1 s of its
 * own CPU is refused by name, and one that only waits fails on the 1 s wall limit; any other run
 * holds neither. The clock's logic, with planted records, is unit-tested in
 * `tests/test-clock.test.ts`.
 */
import { execFile } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { afterAll, beforeAll, expect, test } from "vitest";

const EXTENSION = new URL("../..", import.meta.url).pathname;
const VITEST = join(EXTENSION, "node_modules/vitest/vitest.mjs");

const PLANTED = `
const spin = (ms) => {
  const end = performance.now() + ms;
  while (performance.now() < end) {}
};
test("spins", () => spin(250));
test("waits", () => new Promise((resolve) => setTimeout(resolve, 1500)));
test("quick", () => {});
`;

const CONFIG = `
import { limitsFor } from ${JSON.stringify(join(EXTENSION, "tests/lib/test-clock.ts"))};
export default ({ mode }) => ({
  test: {
    ...limitsFor(mode),
    globals: true,
    include: ["planted.test.ts"],
    setupFiles: [${JSON.stringify(join(EXTENSION, "tests/test-clock.ts"))}],
    env: { STEADYHAND_JUDGE_LOADS: mode === "limits" ? "1" : "" },
  },
});
`;

let folder = "";

beforeAll(async () => {
  folder = await mkdtemp(join(tmpdir(), "steadyhand-limits-"));
  await writeFile(join(folder, "planted.test.ts"), PLANTED);
  await writeFile(join(folder, "vitest.config.mjs"), CONFIG);
});

afterAll(async () => {
  await rm(folder, { recursive: true, force: true });
});

/** vitest on the planted folder in `mode`: its exit code and everything it printed. */
const run = async (mode: string): Promise<{ code: number; output: string }> => {
  const args = [VITEST, "run", "--root", folder, "--mode", mode, "--reporter", "verbose"];
  const env = { ...process.env, NO_COLOR: "1", FORCE_COLOR: "0" };
  try {
    const { stdout, stderr } = await promisify(execFile)(process.execPath, args, { env });
    return { code: 0, output: stdout + stderr };
  } catch (error) {
    const failed = error as { code: number; stdout: string; stderr: string };
    return { code: failed.code, output: failed.stdout + failed.stderr };
  }
};

test("a limits run refuses the spinning test by name and times out the waiting one", async () => {
  const { code, output } = await run("limits");
  expect(code, output).toBe(1);
  const refused = output.split("\n").filter((line) => line.includes("CPU LIMIT: "));
  expect(refused.length, output).toBeGreaterThan(0);
  expect(
    refused.every((line) => line.includes("planted.test.ts > spins took ")),
    output,
  ).toBe(true);
  expect(output).toContain("Test timed out in 1000ms");
  expect(output).toMatch(/Tests {2}2 failed \| 1 passed \(3\)/);
});

test("any other run holds neither limit", async () => {
  const { code, output } = await run("test");
  expect(code, output).toBe(0);
  expect(output).not.toContain("CPU LIMIT: ");
  expect(output).toMatch(/Tests {2}3 passed \(3\)/);
});
