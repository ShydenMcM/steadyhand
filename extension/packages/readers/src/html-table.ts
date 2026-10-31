/**
 * Tables read out of a saved page's HTML text, without a browser (spec §5.2: a reader is a pure
 * function of its snapshot). Fail closed: a table that is missing, doubled, or whose labels differ
 * from the ones the reader knows is refused by name, never read in part.
 */
import { PAGE_KINDS, type PageKind } from "@steadyhand/core";

/** A reader's refusal, naming what it did not recognise. */
export interface Refused {
  readonly refused: string;
}

/** Each entity decoded, `&amp;` last so `&amp;lt;` reads as `&lt;`, not `<`. */
const ENTITIES: readonly (readonly [string, string])[] = [
  ["&lt;", "<"],
  ["&gt;", ">"],
  ["&quot;", '"'],
  ["&#39;", "'"],
  ["&nbsp;", " "],
  ["&amp;", "&"],
];

/** A cell's text: tags dropped, the common entities decoded, white space collapsed and trimmed.
 * Any other entity is left as written, so a number holding one is refused when it is parsed. */
export const cellText = (html: string): string =>
  ENTITIES.reduce(
    (text, [entity, character]) => text.replaceAll(entity, character),
    html.replace(/<[^>]*>/gu, " "),
  )
    .replace(/\s+/gu, " ")
    .trim();

/** The page kind the page declares on its `main` element. */
export const pageKindOf = (html: string): { readonly kind: PageKind } | Refused => {
  const declared = [...html.matchAll(/<main\b[^>]*\bdata-page-kind="([^"]*)"/gu)];
  const [first, ...more] = declared;
  if (first === undefined) {
    return { refused: "the page names no page kind" };
  }
  if (more.length > 0) {
    return { refused: "the page names more than one page kind" };
  }
  const kind = PAGE_KINDS.find((known) => known === first[1]);
  return kind === undefined
    ? { refused: `unknown page kind ${JSON.stringify(first[1])}` }
    : { kind };
};

/** The rows of table `id`, each its cells' text. */
const tableRows = (
  html: string,
  id: string,
): { readonly rows: readonly (readonly string[])[] } | Refused => {
  const pattern = new RegExp(`<table\\b[^>]*\\bid="${id}"[^>]*>([\\s\\S]*?)</table>`, "gu");
  const tables = [...html.matchAll(pattern)];
  const [table, ...more] = tables;
  if (table === undefined) {
    return { refused: `no table ${JSON.stringify(id)}` };
  }
  if (more.length > 0) {
    return { refused: `two tables ${JSON.stringify(id)}` };
  }
  const [, inner = ""] = table;
  const rows = [...inner.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gu)].map(([, cells = ""]) =>
    [...cells.matchAll(/<t([hd])\b[^>]*>([\s\S]*?)<\/t\1>/gu)].map(([, , cell = ""]) =>
      cellText(cell),
    ),
  );
  return { rows };
};

const quoted = (labels: readonly string[]): string =>
  labels.map((label) => JSON.stringify(label)).join(", ");

/** The labels found against the ones expected: the first unknown or missing one, or none. */
const labelProblem = (
  name: string,
  found: readonly string[],
  expected: readonly string[],
  what: "column" | "field",
): Refused | undefined => {
  const unknown = found.find((label) => !expected.includes(label));
  if (unknown !== undefined) {
    return { refused: `${name}: unknown label ${JSON.stringify(unknown)}` };
  }
  const missing = expected.find((label) => !found.includes(label));
  if (missing !== undefined) {
    return { refused: `${name}: missing ${what} ${JSON.stringify(missing)}` };
  }
  return undefined;
};

/** A table whose first row labels its columns, exactly `labels` in that order, and whose other
 * rows are one record each. */
export const columnsTable = <L extends string>(
  html: string,
  id: string,
  labels: readonly L[],
): { readonly rows: readonly Readonly<Record<L, string>>[] } | Refused => {
  const table = tableRows(html, id);
  if ("refused" in table) {
    return table;
  }
  const name = `table ${JSON.stringify(id)}`;
  const [header, ...body] = table.rows;
  if (header === undefined) {
    return { refused: `${name} has no label row` };
  }
  const problem = labelProblem(name, header, labels, "column");
  if (problem !== undefined) {
    return problem;
  }
  if (header.some((label, index) => label !== labels[index])) {
    return { refused: `${name}: columns out of order, expected ${quoted(labels)}` };
  }
  const short = body.find((row) => row.length !== labels.length);
  if (short !== undefined) {
    const row = String(body.indexOf(short) + 1);
    return {
      refused: `${name} row ${row} has ${String(short.length)} cells, expected ${String(labels.length)}`,
    };
  }
  // Every row has one cell per label, checked above.
  const rows = body.map(
    (row) =>
      Object.fromEntries(labels.map((label, index) => [label, row[index]])) as Record<L, string>,
  );
  return { rows };
};

/** A table of label and value rows, holding exactly `labels`. */
export const fieldsTable = <L extends string>(
  html: string,
  id: string,
  labels: readonly L[],
): { readonly fields: Readonly<Record<L, string>> } | Refused => {
  const table = tableRows(html, id);
  if ("refused" in table) {
    return table;
  }
  const name = `table ${JSON.stringify(id)}`;
  const odd = table.rows.findIndex((row) => row.length !== 2);
  if (odd !== -1) {
    return { refused: `${name} row ${String(odd + 1)} is not one label and one value` };
  }
  const found = table.rows.map(([label = ""]) => label);
  const twice = found.find((label, index) => found.indexOf(label) !== index);
  if (twice !== undefined) {
    return { refused: `${name}: two fields ${JSON.stringify(twice)}` };
  }
  const problem = labelProblem(name, found, labels, "field");
  if (problem !== undefined) {
    return problem;
  }
  const fields = Object.fromEntries(
    table.rows.map(([label = "", value = ""]) => [label, value]),
  ) as Record<L, string>;
  return { fields };
};
