import { PACKAGE as CORE } from "@steadyhand/core";
import { expect, test } from "vitest";
import { BUILT_ON, PACKAGE } from "../src/index.ts";

test("readers names itself", () => {
  expect(PACKAGE).toBe("@steadyhand/readers");
});

test("readers is built on core alone, reached through the workspace", () => {
  expect(BUILT_ON).toEqual([CORE]);
  expect(CORE).toBe("@steadyhand/core");
});
