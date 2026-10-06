import { PACKAGE as CORE } from "@steadyhand/core";

/** The package's own name. */
export const PACKAGE = "@steadyhand/history";

/** The workspace packages this one is built on: history sits on core (spec §3). */
export const BUILT_ON: readonly string[] = [CORE];
