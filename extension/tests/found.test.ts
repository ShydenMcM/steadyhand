import { expect, test } from "vitest";
import { foundIn } from "./lib/found.ts";

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
