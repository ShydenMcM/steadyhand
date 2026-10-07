import { expect, test } from "vitest";
import { BlindGuardError, searched } from "./lib/population.ts";

test("a verdict over a population of none is refused, naming what was not judged", () => {
  expect(() => searched([], { of: 0, what: "core modules" })).toThrow(
    new BlindGuardError("judged no core modules: an empty finding over nothing proves nothing"),
  );
});

test("a verdict over a population of one or more is the findings themselves", () => {
  const findings = ["line 3: window"];
  expect(searched(findings, { of: 1, what: "core modules" })).toBe(findings);
});

test("the refusal is a BlindGuardError by name", () => {
  expect(new BlindGuardError("x").name).toBe("BlindGuardError");
});
