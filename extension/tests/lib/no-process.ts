/**
 * A unit test starts no process and opens no outside connection (#286). Shyden's rules (every
 * project): "A unit test never reaches a real service" and "Nor does a unit test start a process"
 * (2026-10-08, ruled in shyden.co.uk #629). The setup file `tests/no-process.ts` installs this for
 * the unit project only; the guards and integration projects need real processes.
 *
 * Each entry point is wrapped on the module object every import shares, and
 * `syncBuiltinESMExports()` carries the wrapper to ESM named imports too. Every route to a socket
 * (`net.connect`, `http`, `tls`, `fetch`) ends in `net.Socket.prototype.connect`. A wrapped call is
 * refused by name before anything starts, and a refusal the test swallowed still fails it.
 */
import childProcess from "node:child_process";
import dns from "node:dns";
import { syncBuiltinESMExports } from "node:module";
import net from "node:net";

export const RULE = "a unit test starts no process and opens no outside connection";

/** The label a wrapper carries, so a test can see which entry point it refuses. */
export const REFUSES = Symbol.for("steadyhand.refuses");

/** A unit test called a process or network entry point. */
export class UnitRuleError extends Error {
  override name = "UnitRuleError";
}

/** Every way a test could start a process or reach out: [label, owner, property]. */
export const ENTRY_POINTS: readonly (readonly [string, object, string])[] = [
  ...(["spawn", "spawnSync", "exec", "execSync", "execFile", "execFileSync", "fork"] as const).map(
    (name) => [`child_process.${name}`, childProcess, name] as const,
  ),
  ["net.Socket.connect", net.Socket.prototype, "connect"],
  ...(
    ["lookup", "lookupService", "resolve", "resolve4", "resolve6", "resolveAny"] as const
  ).flatMap((name) => [
    [`dns.${name}`, dns, name] as const,
    [`dns.promises.${name}`, dns.promises, name] as const,
  ]),
];

/** Whether calls are refused, and the refusals not yet taken. */
export interface Gate {
  armed: boolean;
  refused: string[];
}

const state: Gate = { armed: false, refused: [] };

type Callable = (this: unknown, ...args: unknown[]) => unknown;

/** `original` refused by name while `gate` is armed, and called as it was otherwise. */
export const refusing = (label: string, original: Callable, gate: Gate = state): Callable => {
  const wrapper = function (this: unknown, ...args: unknown[]): unknown {
    if (gate.armed) {
      gate.refused.push(label);
      throw new UnitRuleError(
        `${label} was called: ${RULE} (#286). Call the code in-process with the process stood ` +
          "in, or move the real case to tests/integration and keep a stand-in of its logic here.",
      );
    }
    return original.apply(this, args);
  };
  Object.defineProperty(wrapper, REFUSES, { value: label });
  return wrapper;
};

/** Wrap every entry point, once per process (each test file's setup runs this again), and arm. */
export const install = (): void => {
  for (const [label, owner, name] of ENTRY_POINTS) {
    const current = Reflect.get(owner, name) as Callable & Record<symbol, unknown>;
    if (current[REFUSES] !== label) Reflect.set(owner, name, refusing(label, current));
  }
  syncBuiltinESMExports();
  state.armed = true;
};

/** Whether the refusal is armed. */
export const armed = (): boolean => state.armed;

/** The refusals since the last call, which are then forgotten. */
export const takeRefused = (): string[] => state.refused.splice(0);

/** Why a test that was refused and carried on fails, or undefined when nothing was refused. */
export const swallowedMessage = (refused: readonly string[]): string | undefined =>
  refused.length === 0
    ? undefined
    : `refused, and the test carried on as if nothing happened: ${refused.join(", ")} (${RULE}, #286)`;
