import { readdirSync, readFileSync } from "node:fs";
import { PACKAGE as CORE } from "@steadyhand/core";
import { expect, test } from "vitest";
import { FIXTURE_READERS as FIXTURE_SOURCE } from "../src/fixture-broker.ts";
import { pageKindOf as kindSource } from "../src/html-table.ts";
import { BUILT_ON, FIXTURE_READERS, PACKAGE, pageKindOf } from "../src/index.ts";

test("readers names itself", () => {
  expect(PACKAGE).toBe("@steadyhand/readers");
});

test("readers is built on core alone, reached through the workspace", () => {
  expect(BUILT_ON).toEqual([CORE]);
  expect(CORE).toBe("@steadyhand/core");
});

test("readers gives the panel the page-kind check and the fixture broker's readers", () => {
  expect(pageKindOf).toBe(kindSource);
  expect(FIXTURE_READERS).toBe(FIXTURE_SOURCE);
});

// The panel bundles the readers as one script, where a module has no address of its own: a
// source asking for `import.meta.url` throws as the panel loads (#238).
const SOURCES = new URL("../src/", import.meta.url);

test.each(readdirSync(SOURCES).filter((name) => name.endsWith(".ts")))(
  "%s never asks for its own address",
  (name) => {
    expect(readFileSync(new URL(name, SOURCES), "utf8")).not.toContain("import.meta");
  },
);
