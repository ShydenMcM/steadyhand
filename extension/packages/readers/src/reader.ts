/**
 * What every reader is (spec §5.2): a pure function from one snapshot to one part of the broker
 * view, or a refusal naming what it did not recognise.
 */
import type { Part, PartValues, PageKind } from "@steadyhand/core";
import type { Refused } from "./html-table.ts";

export type { Refused } from "./html-table.ts";

/** What the shell hands a reader: a page's HTML, text the user pasted, or an export file's bytes. */
export type Snapshot =
  | { readonly route: "page"; readonly text: string }
  | { readonly route: "paste"; readonly text: string }
  | { readonly route: "export"; readonly bytes: Uint8Array };

/** A reader's result: the part it read, or why it refused. */
export type Read<T> = { readonly part: Part<T> } | Refused;

/** A reader of one page kind. `readAt` is the instant the snapshot was taken. */
export type Reader<K extends PageKind> = (snapshot: Snapshot, readAt: Date) => Read<PartValues[K]>;
