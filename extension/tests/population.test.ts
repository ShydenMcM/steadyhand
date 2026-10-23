import { expect, test } from "vitest";
import { BlindGuardError, foundIn, searched } from "./lib/population.ts";

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

test("each item's findings are kept beside where it is, only for the items with any", () => {
  const items = [
    { path: "a.ts", found: ["line 1: window"] },
    { path: "b.ts", found: [] },
    { path: "c.ts", found: ["line 2: chrome", "line 3: document"] },
  ];
  expect(
    foundIn(
      items,
      (item) => item.path,
      (item) => item.found,
    ),
  ).toEqual([
    { where: "a.ts", found: ["line 1: window"] },
    { where: "c.ts", found: ["line 2: chrome", "line 3: document"] },
  ]);
});

test("items with no findings leave nothing", () => {
  expect(
    foundIn(
      ["a.ts", "b.ts"],
      (path) => path,
      () => [],
    ),
  ).toEqual([]);
});
