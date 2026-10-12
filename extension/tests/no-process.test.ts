/**
 * A unit test starts no process and opens no outside connection (#286).
 *
 * The entry points and the plants are written out here by hand, never read from the refusal's own
 * list: a plant generated from that list could not see it drop one (the guard-forms catalogue,
 * #446). A plant only runs once every entry point is seen wrapped, so a run with a wrapper taken
 * out fails before anything could really start a process or reach the network.
 */
import childProcess from "node:child_process";
import { execFileSync as namedExecFileSync, spawn as namedSpawn } from "node:child_process";
import dns from "node:dns";
import dnsPromises from "node:dns/promises";
import { lookup as namedLookup } from "node:dns/promises";
import { connect as namedConnect } from "node:net";
import http from "node:http";
import net from "node:net";
import { expect, test } from "vitest";
import {
  armed,
  install,
  REFUSES,
  refusing,
  swallowedMessage,
  takeRefused,
  UnitRuleError,
} from "./lib/no-process.ts";

const ENTRY_POINTS: readonly (readonly [string, object, string])[] = [
  ["child_process.spawn", childProcess, "spawn"],
  ["child_process.spawnSync", childProcess, "spawnSync"],
  ["child_process.exec", childProcess, "exec"],
  ["child_process.execSync", childProcess, "execSync"],
  ["child_process.execFile", childProcess, "execFile"],
  ["child_process.execFileSync", childProcess, "execFileSync"],
  ["child_process.fork", childProcess, "fork"],
  ["net.Socket.connect", net.Socket.prototype, "connect"],
  ["dns.lookup", dns, "lookup"],
  ["dns.lookupService", dns, "lookupService"],
  ["dns.resolve", dns, "resolve"],
  ["dns.resolve4", dns, "resolve4"],
  ["dns.resolve6", dns, "resolve6"],
  ["dns.resolveAny", dns, "resolveAny"],
  ["dns.promises.lookup", dnsPromises, "lookup"],
  ["dns.promises.lookupService", dnsPromises, "lookupService"],
  ["dns.promises.resolve", dnsPromises, "resolve"],
  ["dns.promises.resolve4", dnsPromises, "resolve4"],
  ["dns.promises.resolve6", dnsPromises, "resolve6"],
  ["dns.promises.resolveAny", dnsPromises, "resolveAny"],
];

const refuses = (owner: object, name: string): unknown =>
  (Reflect.get(owner, name) as Record<symbol, unknown> | undefined)?.[REFUSES];

test.each(ENTRY_POINTS)("this unit run refuses %s", (label, owner, name) => {
  expect(refuses(owner, name)).toBe(label);
});

test("node:dns/promises is the same object as dns.promises, so one wrapper covers both", () => {
  expect(dnsPromises).toBe(dns.promises);
});

/** Fail before a plant runs unless every entry point is wrapped, so that taking a wrapper out
 * (a mutation) can never let a plant start a real process or reach the network. */
const everyEntryPointWrapped = (): void => {
  if (!armed()) throw new Error("the refusal is not armed, so no plant runs");
  // net.connect is not wrapped itself: it reaches the wrapped Socket.prototype.connect inside.
  const named: readonly (readonly [string, unknown])[] = [
    ["child_process.spawn", namedSpawn],
    ["child_process.execFileSync", namedExecFileSync],
    ["dns.promises.lookup", namedLookup],
  ];
  const stale = named.filter(
    ([label, binding]) => (binding as Record<symbol, unknown>)[REFUSES] !== label,
  );
  if (stale.length > 0) {
    throw new Error(
      `named imports not wrapped, so no plant runs: ${stale.map(([l]) => l).join(", ")}`,
    );
  }
  const unwrapped = ENTRY_POINTS.filter(([label, owner, name]) => refuses(owner, name) !== label);
  if (unwrapped.length > 0) {
    throw new Error(`not wrapped, so no plant runs: ${unwrapped.map(([l]) => l).join(", ")}`);
  }
};

const ignore = (): void => undefined;

const PLANTS: readonly (readonly [string, string, () => unknown])[] = [
  ["spawn", "child_process.spawn", () => childProcess.spawn("true")],
  ["spawnSync", "child_process.spawnSync", () => childProcess.spawnSync("true")],
  ["exec", "child_process.exec", () => childProcess.exec("true")],
  ["execSync", "child_process.execSync", () => childProcess.execSync("true")],
  ["execFile", "child_process.execFile", () => childProcess.execFile("true")],
  ["execFileSync", "child_process.execFileSync", () => childProcess.execFileSync("true")],
  ["fork", "child_process.fork", () => childProcess.fork("plant.js")],
  ["socket-connect", "net.Socket.connect", () => new net.Socket().connect(9, "127.0.0.1")],
  ["net-connect", "net.Socket.connect", () => net.connect(9, "127.0.0.1")],
  ["create-connection", "net.Socket.connect", () => net.createConnection({ port: 9 })],
  ["http-get", "net.Socket.connect", () => http.get("http://x.test/")],
  [
    "lookup",
    "dns.lookup",
    () => {
      dns.lookup("x.test", ignore);
    },
  ],
  [
    "lookupService",
    "dns.lookupService",
    () => {
      dns.lookupService("127.0.0.1", 80, ignore);
    },
  ],
  [
    "resolve",
    "dns.resolve",
    () => {
      dns.resolve("x.test", ignore);
    },
  ],
  [
    "resolve4",
    "dns.resolve4",
    () => {
      dns.resolve4("x.test", ignore);
    },
  ],
  [
    "resolve6",
    "dns.resolve6",
    () => {
      dns.resolve6("x.test", ignore);
    },
  ],
  [
    "resolveAny",
    "dns.resolveAny",
    () => {
      dns.resolveAny("x.test", ignore);
    },
  ],
  ["promises-lookup", "dns.promises.lookup", () => dnsPromises.lookup("x.test")],
  [
    "promises-lookupService",
    "dns.promises.lookupService",
    () => dnsPromises.lookupService("127.0.0.1", 80),
  ],
  ["promises-resolve", "dns.promises.resolve", () => dnsPromises.resolve("x.test")],
  ["promises-resolve4", "dns.promises.resolve4", () => dnsPromises.resolve4("x.test")],
  ["promises-resolve6", "dns.promises.resolve6", () => dnsPromises.resolve6("x.test")],
  ["promises-resolveAny", "dns.promises.resolveAny", () => dnsPromises.resolveAny("x.test")],
];

/** The same entry points reached through ESM named imports, bound when this file was linked:
 * they see the wrappers only because the refusal re-syncs the built-in modules' named exports. */
const NAMED_PLANTS: readonly (readonly [string, string, () => unknown])[] = [
  ["named-spawn", "child_process.spawn", () => namedSpawn("true")],
  ["named-execFileSync", "child_process.execFileSync", () => namedExecFileSync("true")],
  ["named-promises-lookup", "dns.promises.lookup", () => namedLookup("x.test")],
  ["named-net-connect", "net.Socket.connect", () => namedConnect(9, "127.0.0.1")],
];

const escape = (text: string): string => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

test.each([...PLANTS, ...NAMED_PLANTS])(
  "a planted %s call is refused by name",
  (_id, label, plant) => {
    everyEntryPointWrapped();
    expect(plant).toThrow(new RegExp(`^${escape(label)} was called: `));
    expect(takeRefused()).toEqual([label]);
  },
);

test("a planted fetch is refused at its socket, and the refusal is kept though fetch hides it", async () => {
  everyEntryPointWrapped();
  await expect(fetch("http://x.test/")).rejects.toThrow("fetch failed");
  expect(takeRefused()).toEqual(["net.Socket.connect"]);
});

test("the refusal says what to do instead", () => {
  everyEntryPointWrapped();
  let refused: unknown;
  try {
    childProcess.execSync("true");
  } catch (error) {
    refused = error;
  }
  takeRefused();
  expect(refused).toBeInstanceOf(UnitRuleError);
  expect((refused as Error).message).toBe(
    "child_process.execSync was called: a unit test starts no process and opens no outside " +
      "connection (#286). Call the code in-process with the process stood in, or move the real " +
      "case to tests/integration and keep a stand-in of its logic here.",
  );
});

test("a refusal the test swallowed still fails it by name", () => {
  expect(swallowedMessage(["child_process.spawn", "dns.lookup"])).toBe(
    "refused, and the test carried on as if nothing happened: child_process.spawn, dns.lookup " +
      "(a unit test starts no process and opens no outside connection, #286)",
  );
});

test("nothing refused, nothing to report", () => {
  expect(swallowedMessage([])).toBeUndefined();
});

test("unarmed, a wrapper calls through with its receiver and arguments", () => {
  const gate = { armed: false, refused: [] };
  const original = function (this: unknown, ...args: unknown[]): unknown {
    return [this, ...args];
  };
  const receiver = { name: "receiver" };
  expect(refusing("plant", original, gate).call(receiver, 1, "two")).toEqual([receiver, 1, "two"]);
  expect(gate.refused).toHaveLength(0);
});

test("armed, a wrapper records its label in its own gate and never calls through", () => {
  const gate = { armed: true, refused: [] };
  let called = false;
  const original = (): void => {
    called = true;
  };
  expect(() => refusing("plant", original, gate).call(undefined)).toThrow(UnitRuleError);
  expect([gate.refused, called]).toEqual([["plant"], false]);
});

test.each(ENTRY_POINTS)(
  "installing again leaves the %s wrapper as it was",
  (_label, owner, name) => {
    const before: unknown = Reflect.get(owner, name);
    install();
    expect(Reflect.get(owner, name)).toBe(before);
  },
);
