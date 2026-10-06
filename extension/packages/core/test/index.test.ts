import { expect, test } from "vitest";
import { PACKAGE } from "../src/index.ts";

test("core names itself", () => {
  expect(PACKAGE).toBe("@steadyhand/core");
});
