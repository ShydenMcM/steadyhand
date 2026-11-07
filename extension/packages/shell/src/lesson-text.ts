/** A lesson as written (spec §13, #244): TOML front matter between `+++` lines, then paragraphs,
 * lists and tables, with bold and code inline. The panel writes elements and text only, so the
 * text is read into blocks and spans here, and markup is never kept. */

export interface Span {
  readonly text: string;
  readonly style: "plain" | "strong" | "code";
}

/** A list item, or a table cell: its spans. */
export type Spans = readonly Span[];

export type Block =
  | { readonly kind: "paragraph"; readonly spans: Spans }
  | { readonly kind: "list"; readonly ordered: boolean; readonly items: readonly Spans[] }
  | {
      readonly kind: "table";
      readonly heading: readonly Spans[];
      readonly rows: readonly (readonly Spans[])[];
    };

export interface Lesson {
  /** The lesson's key, such as `idx.lots`. */
  readonly id: string;
  readonly title: string;
  readonly summary: string;
  /** The note codes the lesson explains. */
  readonly explains: readonly string[];
  /** The slug of the module the lesson is in, and its place there. */
  readonly module: string;
  readonly position: number;
  readonly seeAlso: readonly string[];
  readonly blocks: readonly Block[];
}

const FENCE = "+++";
const ITEM = /^(?:- |\d+\. )/u;
const INLINE = /(\*\*[^*]+\*\*|`[^`]+`)/u;

/** The front matter's fields: each line `key = value`, the value as TOML writes a string, a whole
 * number or a list of strings, which JSON reads the same. */
const frontOf = (lines: readonly string[]): Map<string, unknown> => {
  const fields = new Map<string, unknown>();
  // The lesson a refusal names: its id, read the plain way, before any line is judged.
  const named = /^id = "([^"]*)"$/mu.exec(lines.join("\n"))?.[1] ?? "a lesson";
  for (const line of lines.filter((each) => each.trim() !== "")) {
    const equals = line.indexOf(" = ");
    let value: unknown;
    try {
      value = JSON.parse(line.slice(equals + 3));
    } catch {
      value = undefined;
    }
    if (equals === -1 || value === undefined) {
      throw new SyntaxError(`${named}: the front matter line "${line}" is not key = value`);
    }
    fields.set(line.slice(0, equals), value);
  }
  return fields;
};

/** `text` as spans: `**bold**` and `` `code` `` each their own; an opener left unclosed is
 * refused. */
const spansOf = (text: string, id: string): Span[] =>
  text
    .split(INLINE)
    .filter((part) => part !== "")
    .map((part): Span => {
      if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
        return { text: part.slice(2, -2), style: "strong" };
      }
      if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
        return { text: part.slice(1, -1), style: "code" };
      }
      if (part.includes("**") || part.includes("`")) {
        throw new SyntaxError(`${id}: unclosed ** or \` in: ${text}`);
      }
      return { text: part, style: "plain" };
    });

const cellsOf = (line: string, id: string): Spans[] =>
  line
    .trim()
    .replace(/^\||\|$/gu, "")
    .split("|")
    .map((cell) => spansOf(cell.trim(), id));

/** One block from a run of lines with no blank line in it. */
const blockOf = (lines: readonly string[], id: string): Block => {
  // `^` without the `m` flag: the run's first line.
  const opening = lines.join("\n");
  if (lines.every((line) => line.trim().startsWith("|"))) {
    // The heading row, then the rule line under it, then the rows.
    return {
      kind: "table",
      heading: cellsOf(lines.slice(0, 1).join(""), id),
      rows: lines.slice(2).map((row) => cellsOf(row, id)),
    };
  }
  if (ITEM.test(opening)) {
    const items: string[][] = [];
    let item: string[] = [];
    for (const line of lines) {
      if (ITEM.test(line)) {
        item = [line.replace(ITEM, "")];
        items.push(item);
      } else {
        item.push(line.trim());
      }
    }
    return {
      kind: "list",
      ordered: /^\d/u.test(opening),
      items: items.map((words) => spansOf(words.join(" "), id)),
    };
  }
  return { kind: "paragraph", spans: spansOf(lines.map((line) => line.trim()).join(" "), id) };
};

const text = (fields: ReadonlyMap<string, unknown>, name: string, id: string): string => {
  const value = fields.get(name);
  if (typeof value !== "string") {
    throw new TypeError(`${id}: the front matter has no text ${name}`);
  }
  return value;
};

const list = (fields: ReadonlyMap<string, unknown>, name: string, id: string): string[] => {
  const value = fields.get(name);
  if (!Array.isArray(value) || !value.every((each) => typeof each === "string")) {
    throw new TypeError(`${id}: the front matter has no list ${name}`);
  }
  return value;
};

/** Read the lesson written as `written`; refuse, naming the lesson and what is wrong, anything
 * it cannot read. */
export const lessonFrom = (written: string): Lesson => {
  const lines = written.split("\n");
  const close = lines.indexOf(FENCE, 1);
  if (lines[0] !== FENCE || close === -1) {
    throw new SyntaxError("a lesson begins with +++ front matter");
  }
  const fields = frontOf(lines.slice(1, close));
  const id = text(fields, "id", "a lesson");
  const position = fields.get("position");
  if (!Number.isInteger(position)) {
    throw new TypeError(`${id}: the front matter has no whole-number position`);
  }
  let run: string[] = [];
  const runs = [run];
  for (const line of lines.slice(close + 1)) {
    if (line.trim() === "") {
      run = [];
      runs.push(run);
    } else {
      run.push(line);
    }
  }
  return {
    id,
    title: text(fields, "title", id),
    summary: text(fields, "summary", id),
    explains: list(fields, "explains", id),
    module: text(fields, "module", id),
    position: position as number,
    seeAlso: list(fields, "see_also", id),
    blocks: runs.filter((run) => run.length > 0).map((run) => blockOf(run, id)),
  };
};
