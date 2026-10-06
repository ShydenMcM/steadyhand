import { PACKAGE as CORE } from "@steadyhand/core";
import { expect, test } from "vitest";
import { BUILT_ON, PACKAGE } from "../src/index.ts";

test("history names itself", () => {
  expect(PACKAGE).toBe("@steadyhand/history");
});

test("history is built on core alone, reached through the workspace", () => {
  expect(BUILT_ON).toEqual([CORE]);
  expect(CORE).toBe("@steadyhand/core");
});
