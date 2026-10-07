/**
 * Every import a file makes, read from the parse tree (spec §3: the dependency rule is a test).
 * Each way the workspace can name another module is read: `import … from`, a side-effect import,
 * `export … from`, `import x = require(…)`, a dynamic `import(…)`, `require(…)` and a type's
 * `import(…)`. One whose module is not a string written in the code cannot be judged, so it is
 * refused by name.
 */
import { posix } from "node:path";
import { lineOf, nodes, ts, UnreadableSourceError } from "./source.ts";

/** One module named by a file, and the line naming it. */
export interface Import {
  specifier: string;
  line: number;
}

const literalOf = (file: ts.SourceFile, node: ts.Node, written: ts.Node | undefined): string => {
  // A type's `import("x")` holds its module as a literal type around the string.
  const expression =
    written !== undefined && ts.isLiteralTypeNode(written) ? written.literal : written;
  if (expression !== undefined && ts.isStringLiteralLike(expression)) {
    return expression.text;
  }
  throw new UnreadableSourceError(
    `${file.fileName} line ${String(lineOf(file, node))}: the module this import names is not ` +
      "written as a string, so its direction cannot be judged",
  );
};

const isRequire = (node: ts.CallExpression): boolean =>
  ts.isIdentifier(node.expression) && node.expression.text === "require";

/** The module `node` names, if it is one of the import forms; `undefined` for any other node. */
const specifierOf = (file: ts.SourceFile, node: ts.Node): string | undefined => {
  if (ts.isImportDeclaration(node)) {
    return literalOf(file, node, node.moduleSpecifier);
  }
  if (ts.isExportDeclaration(node) && node.moduleSpecifier !== undefined) {
    return literalOf(file, node, node.moduleSpecifier);
  }
  if (ts.isExternalModuleReference(node)) {
    return literalOf(file, node, node.expression);
  }
  if (
    ts.isCallExpression(node) &&
    (node.expression.kind === ts.SyntaxKind.ImportKeyword || isRequire(node))
  ) {
    return literalOf(file, node, node.arguments[0]);
  }
  if (ts.isImportTypeNode(node)) {
    return literalOf(file, node, node.argument);
  }
  return undefined;
};

/** Every import in `file`, in order. */
export const importsOf = (file: ts.SourceFile): Import[] =>
  nodes(file).flatMap((node) => {
    const specifier = specifierOf(file, node);
    return specifier === undefined ? [] : [{ specifier, line: lineOf(file, node) }];
  });

/** The workspace's packages, from the bottom layer up (spec §3). */
export const LAYERS = ["core", "readers", "history", "shell"] as const;
export type Layer = (typeof LAYERS)[number];

/** The layers each package may NOT import: core imports no other package, nothing imports shell. */
export const UPSTREAM: Readonly<Record<Layer, readonly Layer[]>> = {
  core: ["readers", "history", "shell"],
  readers: ["shell"],
  history: ["shell"],
  shell: [],
};

const isLayer = (name: string | undefined): name is Layer =>
  (LAYERS as readonly (string | undefined)[]).includes(name);

/** The package holding `path` (relative to `extension/`), or `undefined` outside `packages/`. */
export const layerOf = (path: string): Layer | undefined => {
  const [top, name] = path.split("/");
  return top === "packages" && isLayer(name) ? name : undefined;
};

/**
 * The package `specifier`, imported by `path`, reaches: a layer, or "external" for a module from
 * outside the workspace. A workspace name that is no package, or a relative path that leaves the
 * packages, cannot be judged and is refused by name.
 */
export const targetOf = (path: string, specifier: string): Layer | "external" => {
  if (specifier.startsWith("@steadyhand/")) {
    const name = specifier.split("/")[1];
    if (isLayer(name)) {
      return name;
    }
    throw new UnreadableSourceError(`${path}: ${specifier} names no package of the workspace`);
  }
  if (specifier.startsWith(".")) {
    const layer = layerOf(posix.join(posix.dirname(path), specifier));
    if (layer !== undefined) {
      return layer;
    }
    throw new UnreadableSourceError(`${path}: ${specifier} reaches outside the packages`);
  }
  return "external";
};

/** Every import in `file`, at `path` in a package, that reaches a layer its package may not. */
export const upstreamImports = (path: string, file: ts.SourceFile): string[] => {
  const from = layerOf(path);
  if (from === undefined) {
    throw new UnreadableSourceError(`${path}: not in a package, so it has no layer to judge`);
  }
  return importsOf(file).flatMap(({ specifier, line }) => {
    const to = targetOf(path, specifier);
    return to !== "external" && UPSTREAM[from].includes(to)
      ? [`${path} line ${String(line)}: ${from} imports ${to} (${specifier})`]
      : [];
  });
};
