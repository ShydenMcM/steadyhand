/**
 * The unit project's per-test clock (#323). Its `beforeEach` runs first and its `afterEach` last
 * (vitest's default stack order puts a setup file's hooks outside a test file's), so the time
 * between them is the test's own, its hooks included. It records the time on the test's meta for
 * `tests/load-report.ts`, and in a limits run (`npm run test:limits`, no coverage) fails the test
 * when its own CPU is over the limit. Own CPU is the test THREAD's (`process.threadCpuUsage`).
 */
import { relative } from "node:path";
import { afterEach, beforeEach } from "vitest";
import { JUDGE_ENV, judge } from "./lib/load-clock.ts";
import { type Spent, testRefusal } from "./lib/test-clock.ts";

const ROOT = new URL("..", import.meta.url).pathname;
const thread = (): number => {
  const { user, system } = process.threadCpuUsage();
  return user + system;
};
let cpu = 0;
let wall = 0;

beforeEach(() => {
  cpu = thread();
  wall = performance.now();
});

afterEach(({ task }) => {
  const spent: Spent = {
    name: `${relative(ROOT, task.file.filepath)} > ${task.name}`,
    cpuMicroseconds: thread() - cpu,
    wallMicroseconds: Math.round((performance.now() - wall) * 1000),
  };
  (task.meta as { spent?: Spent }).spent = spent;
  const refusal = testRefusal(spent);
  judge(refusal, process.env[JUDGE_ENV]);
});
