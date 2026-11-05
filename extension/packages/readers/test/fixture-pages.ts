import type { PageKind } from "@steadyhand/core";

/** The folder of the fixture broker's pages, one `<page kind>.html` each. Tests alone read it: the
 * bundled panel has no module address to find it from (#238). */
export const FIXTURE_PAGES = new URL("../fixtures/fixture-broker/", import.meta.url);

/** The file name of the fixture page of `kind`, under `FIXTURE_PAGES`. */
export const fixturePagePath = (kind: PageKind): string => `${kind}.html`;
