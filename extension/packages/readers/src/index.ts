import { PACKAGE as CORE } from "@steadyhand/core";

/** The package's own name. */
export const PACKAGE = "@steadyhand/readers";

/** The workspace packages this one is built on: readers sits on core (spec §3). */
export const BUILT_ON: readonly string[] = [CORE];

export { FIXTURE_BROKER, FIXTURE_READERS } from "./fixture-broker.ts";
export { pageKindOf } from "./html-table.ts";
export type { Read, Reader, Refused, Snapshot } from "./reader.ts";
