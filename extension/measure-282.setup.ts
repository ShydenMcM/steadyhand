// Measurement-only vitest setup file (2026-10-12): per test and per file load, as JSON lines.
// Own CPU is the test THREAD's (process.threadCpuUsage), never the process's (global rule, #632).
// Every child_process entry point and net.Socket connect is recorded against the running test,
// or against the file's load when no test is running yet.
import { appendFileSync } from "node:fs";
import childProcess from "node:child_process";
import net from "node:net";
import { syncBuiltinESMExports } from "node:module";
import { afterEach, beforeAll, beforeEach } from "vitest";

const OUT = process.env.PROBE_OUT ?? "";
const thread = (): number => {
  const usage = process.threadCpuUsage();
  return (usage.user + usage.system) / 1e6;
};
const loadWall0 = performance.now();
const loadCpu0 = thread();
let current = "(load)";
const events = new Map<string, { kind: string; detail: string }[]>();
const note = (kind: string, detail: unknown): void => {
  const list = events.get(current) ?? [];
  list.push({ kind, detail: String(JSON.stringify(detail)).slice(0, 200) });
  events.set(current, list);
};

for (const name of ["spawn", "spawnSync", "exec", "execSync", "execFile", "execFileSync", "fork"] as const) {
  const original = childProcess[name] as (...args: unknown[]) => unknown;
  (childProcess as Record<string, unknown>)[name] = (...args: unknown[]) => {
    note("process", [name, args[0]]);
    return original.apply(childProcess, args);
  };
}
const connect = net.Socket.prototype.connect;
net.Socket.prototype.connect = function (this: net.Socket, ...args: unknown[]) {
  note("socket", args[0]);
  return (connect as (...a: unknown[]) => net.Socket).apply(this, args);
} as typeof connect;
syncBuiltinESMExports();

let fileName = "?";
// biome-ignore lint: vitest 5 reads the first argument only when destructured
beforeAll(({}, suite) => {
  fileName = (suite as { file?: { name?: string }; name?: string }).file?.name ?? (suite as { name?: string }).name ?? "?";
  appendFileSync(
    OUT,
    JSON.stringify({
      load: fileName,
      wall: (performance.now() - loadWall0) / 1000,
      cpu: thread() - loadCpu0,
      events: events.get("(load)") ?? [],
    }) + "\n",
  );
  events.delete("(load)");
});

let wall0 = 0;
let cpu0 = 0;
beforeEach((context) => {
  current = `${fileName} > ${context.task.name}`;
  wall0 = performance.now();
  cpu0 = thread();
});

afterEach((context) => {
  const id = `${fileName} > ${context.task.name}`;
  appendFileSync(
    OUT,
    JSON.stringify({ id, wall: (performance.now() - wall0) / 1000, cpu: thread() - cpu0, events: events.get(id) ?? [] }) + "\n",
  );
  events.delete(id);
  current = "(between)";
});
