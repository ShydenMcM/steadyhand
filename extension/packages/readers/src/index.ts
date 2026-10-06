import { PACKAGE as CORE } from "@steadyhand/core";

/** The package's own name. */
export const PACKAGE = "@steadyhand/readers";

/** The workspace packages this one is built on: readers sits on core (spec §3). */
export const BUILT_ON: readonly string[] = [CORE];
