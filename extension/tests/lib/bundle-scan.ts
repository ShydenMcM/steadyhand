/**
 * The scan of each built bundle (#240, spec §11, §12.3). A bundle is read as acorn's parse tree,
 * never as text, so a forbidden name inside a string, a template's text, a comment or an object
 * key is not code. No bundle may reach the network or run code made from text; the content
 * script may also neither drive the broker's page nor write to it.
 */
import { parse } from "acorn";

export interface Finding {
  readonly line: number;
  readonly column: number;
  readonly what: string;
}

export interface Scan {
  /** The calls, constructions and assignments judged: a scan that judged none proves nothing. */
  readonly judged: number;
  readonly found: readonly Finding[];
}

/** A node of acorn's parse tree, with its fields read by name. */
interface Tree {
  readonly type: string;
  readonly loc: { readonly start: { readonly line: number; readonly column: number } };
  readonly [field: string]: unknown;
}

/** Names that reach the network or run code made from text, however they are reached. */
const REACH_OUT = new Set([
  "fetch",
  "XMLHttpRequest",
  "WebSocket",
  "EventSource",
  "sendBeacon",
  "RTCPeerConnection",
  "importScripts",
  "eval",
]);
/** What the content script may not do to the broker's page, nor write to it. */
const PAGE_ACTIONS = new Set([
  "click",
  "submit",
  "requestSubmit",
  "dispatchEvent",
  "focus",
  "blur",
]);
const PAGE_WRITES = new Set(["value", "innerHTML", "outerHTML", "textContent", "checked"]);
/** The events a person's input raises. */
const INPUT_EVENTS = new Set([
  "input",
  "beforeinput",
  "change",
  "keydown",
  "keypress",
  "keyup",
  "click",
  "dblclick",
  "mousedown",
  "mouseup",
  "pointerdown",
  "pointerup",
  "submit",
  "paste",
  "cut",
  "copy",
  "focus",
  "blur",
  "focusin",
  "focusout",
]);
const FROM_THE_WEB = /^https?:/iu;
const JUDGED = new Set([
  "CallExpression",
  "NewExpression",
  "AssignmentExpression",
  "ImportExpression",
]);
/** Nodes whose `key` is a name, not code, unless computed. */
const KEYED = new Set(["Property", "PropertyDefinition", "MethodDefinition"]);

const isTree = (value: unknown): value is Tree =>
  typeof value === "object" &&
  value !== null &&
  typeof (value as { type?: unknown }).type === "string";

/** The node in `field` of `tree`: the scan reads only fields that always hold one. */
const part = (tree: Tree, field: string): Tree => tree[field] as Tree;

const argumentAt = (call: Tree, place: number): Tree | undefined => {
  const value = (call.arguments as readonly unknown[])[place];
  return isTree(value) ? value : undefined;
};

/** The text of a string literal, or of a template with no substitution. */
const textOf = (tree: Tree | undefined): string | undefined => {
  if (tree?.type === "Literal") {
    return typeof tree.value === "string" ? tree.value : undefined;
  }
  if (tree?.type === "TemplateLiteral" && (tree.expressions as readonly unknown[]).length === 0) {
    const [text] = tree.quasis as readonly { readonly value: { readonly cooked: string } }[];
    return text?.value.cooked;
  }
  return undefined;
};

/** The name `x`, `a.x` and `a["x"]` each reach. */
const reached = (tree: Tree | undefined): string | undefined => {
  if (tree?.type === "Identifier") {
    return tree.name as string;
  }
  if (tree?.type === "MemberExpression") {
    const property = part(tree, "property");
    return tree.computed === true ? textOf(property) : reached(property);
  }
  return undefined;
};

/** Whether `tree` is an address on the web: a string, or a template whose text starts with one. */
const isWebUrl = (tree: Tree | undefined): boolean => {
  const [start] = tree?.type === "TemplateLiteral" ? (tree.quasis as readonly Tree[]) : [];
  const text = start === undefined ? textOf(tree) : (start.value as { cooked: string }).cooked;
  return text !== undefined && FROM_THE_WEB.test(text);
};

const callFindings = (call: Tree, contentScript: boolean): string[] => {
  const callee = part(call, "callee");
  const name = reached(callee) ?? "";
  const first = argumentAt(call, 0);
  const found: string[] = [];
  if (
    (name === "setTimeout" || name === "setInterval") &&
    (first?.type === "TemplateLiteral" || textOf(first) !== undefined)
  ) {
    found.push(`${name} with a string`);
  }
  if (name === "setAttribute" && textOf(first) === "src" && isWebUrl(argumentAt(call, 1))) {
    found.push("src from the web");
  }
  if (contentScript && callee.type === "MemberExpression" && PAGE_ACTIONS.has(name)) {
    found.push(`${name}()`);
  }
  if (contentScript && name === "addEventListener") {
    const event = textOf(first);
    if (event === undefined) {
      found.push("listens for an event it does not name");
    } else if (INPUT_EVENTS.has(event)) {
      found.push(`listens for ${event}`);
    }
  }
  return found;
};

const assignmentFindings = (assignment: Tree, contentScript: boolean): string[] => {
  const target = part(assignment, "left");
  const name = reached(target) ?? "";
  const found: string[] = [];
  if (name === "src" && isWebUrl(part(assignment, "right"))) {
    found.push("src from the web");
  }
  if (contentScript && target.type === "MemberExpression" && PAGE_WRITES.has(name)) {
    found.push(`${name} written`);
  }
  return found;
};

/** What `tree` itself holds that is forbidden, its children aside. */
const findingsAt = (tree: Tree, contentScript: boolean): string[] => {
  switch (tree.type) {
    case "Identifier":
    case "MemberExpression": {
      const name = reached(tree);
      return name !== undefined && REACH_OUT.has(name) ? [name] : [];
    }
    case "ImportExpression":
      return ["import()"];
    case "NewExpression": {
      const made = reached(part(tree, "callee"));
      return made === "Worker" || made === "Function" ? [`new ${made}`] : [];
    }
    case "CallExpression":
      return callFindings(tree, contentScript);
    case "AssignmentExpression":
      return assignmentFindings(tree, contentScript);
    default:
      return [];
  }
};

/** The children of `tree` that are code: a member's property or a key only when computed. */
const codeUnder = (tree: Tree): Tree[] =>
  Object.entries(tree).flatMap(([field, value]) => {
    const isName =
      (tree.type === "MemberExpression" && field === "property") ||
      (KEYED.has(tree.type) && field === "key");
    if (isName && tree.computed !== true) {
      return [];
    }
    return (Array.isArray(value) ? (value as unknown[]) : [value]).filter(isTree);
  });

/** Scan `code`, under the content script's rules too when `contentScript`. */
export const scan = (code: string, contentScript: boolean): Scan => {
  const root = parse(code, { ecmaVersion: "latest", sourceType: "script", locations: true });
  const found: Finding[] = [];
  let judged = 0;
  const visit = (tree: Tree): void => {
    judged += JUDGED.has(tree.type) ? 1 : 0;
    const { line, column } = tree.loc.start;
    found.push(...findingsAt(tree, contentScript).map((what) => ({ line, column, what })));
    codeUnder(tree).forEach(visit);
  };
  visit(root as unknown as Tree);
  if (judged === 0) {
    throw new Error("the scan judged no call, construction or assignment");
  }
  return { judged, found };
};

/** The http and https sources of the script tags in the page `html`. */
export const webScripts = (html: string): string[] =>
  [...html.matchAll(/<script\b[^>]*>/giu)].flatMap((tag) => {
    const source = /\bsrc\s*=\s*(["'])(.*?)\1/iu.exec(tag[0])?.[2];
    return source !== undefined && FROM_THE_WEB.test(source) ? [source] : [];
  });

/** The advice words in `text` (spec §12.3): steadyhand says what a strategy implies, never what
 * to do. */
export const adviceWords = (text: string): string[] =>
  [...text.matchAll(/recommend|we\s+suggest/giu)].map((match) => match[0]);
