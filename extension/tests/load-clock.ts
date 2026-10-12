/**
 * The unit project's LAST setup file (#285): it runs just before each test file is imported, so
 * the time from here to the file's first hook is that file's load. It records the load on the
 * file's meta for `tests/load-report.ts`, and fails the file when the load is over the limit.
 * Own CPU is the test THREAD's (`process.threadCpuUsage`), never the process's.
 */
import { relative } from "node:path";
import { beforeAll } from "vitest";
import { loadRefusal } from "./lib/load-clock.ts";

const ROOT = new URL("..", import.meta.url).pathname;
const thread = (): number => {
  const { user, system } = process.threadCpuUsage();
  return user + system;
};
const cpu = thread();
const wall = performance.now();

// Vitest reads a hook's first argument only when it is destructured; the suite is the second.
// eslint-disable-next-line no-empty-pattern
beforeAll(({}, suite) => {
  const load = {
    path: relative(ROOT, suite.file.filepath),
    cpuMicroseconds: thread() - cpu,
    wallMicroseconds: Math.round((performance.now() - wall) * 1000),
  };
  suite.meta.load = load;
  const refusal = loadRefusal(load);
  if (refusal !== undefined) throw new Error(refusal);
});
