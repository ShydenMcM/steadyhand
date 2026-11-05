import { readdirSync, readFileSync } from "node:fs";
import { expect, test } from "vitest";
import { FIXTURE_READERS as FIXTURE_SOURCE } from "../src/fixture-broker.ts";
import { pageKindOf as kindSource } from "../src/html-table.ts";
import { FIXTURE_READERS, pageKindOf } from "../src/index.ts";

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
