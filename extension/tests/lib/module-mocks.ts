/**
 * No extension test mocks a module (#394, Shyden's ruling 2026-10-23: "No vi.mock"). Vitest
 * rewrites any file that calls one of the members below (`@vitest/mocker`'s hoisting reads
 * `vi` or `vitest` followed by `.mock`, `.unmock`, `.hoisted`, `.doMock`, `.doUnmock` or
 * `.importActual`), so the file no longer runs as written and Node's own coverage of it is
 * refused; `importMock` mocks a module by another name. A stand-in is passed in instead (build.ts
 * takes its bundler). `vi` and `vitest` may be used only by reading a member written as a name,
 * so a mock cannot hide behind a rename, a whole import or `vi` passed around.
 */
import { lineOf, nodes, ts, UnreadableSourceError } from "./source.ts";

/** The members of `vi` that mock a module, or that make Vitest rewrite the file. */
export const MODULE_MOCKS = new Set([
  "mock",
  "unmock",
  "hoisted",
  "doMock",
  "doUnmock",
  "importActual",
  "importMock",
]);

/** The names Vitest exports its mocking object under. */
export const HOLDERS = new Set(["vi", "vitest"]);

/** The declarations whose `name` is a key, not a use of a value. */
const KEYED = new Set([
  ts.SyntaxKind.PropertyAssignment,
  ts.SyntaxKind.PropertyDeclaration,
  ts.SyntaxKind.PropertySignature,
  ts.SyntaxKind.MethodDeclaration,
  ts.SyntaxKind.MethodSignature,
  ts.SyntaxKind.GetAccessor,
  ts.SyntaxKind.SetAccessor,
  ts.SyntaxKind.EnumMember,
]);

/** The holder `node` is, if it is one: `vi` by name, or read as a member (`helpers.vi`,
 * `helpers["vi"]`). */
const holderOf = (node: ts.Node): string | undefined => {
  const name = ts.isIdentifier(node)
    ? node.text
    : ts.isPropertyAccessExpression(node)
      ? node.name.text
      : ts.isElementAccessExpression(node) && ts.isStringLiteralLike(node.argumentExpression)
        ? node.argumentExpression.text
        : undefined;
  return name !== undefined && HOLDERS.has(name) ? name : undefined;
};

/** Whether `node` is the object a member is read from, the member written as a name or a key. */
const isMemberRoot = (node: ts.Node): boolean => {
  const { parent } = node;
  return (
    (ts.isPropertyAccessExpression(parent) || ts.isElementAccessExpression(parent)) &&
    parent.expression === node
  );
};

/** Whether the holder name `node` is a key, a type's name or an import's name, not a value. */
const isNotAValue = (node: ts.Identifier): boolean => {
  const { parent } = node;
  return (
    (KEYED.has(parent.kind) && (parent as { name?: ts.Node }).name === node) ||
    ts.isQualifiedName(parent) ||
    ts.isImportSpecifier(parent) ||
    ts.isExportSpecifier(parent) ||
    (ts.isPropertyAccessExpression(parent) && parent.name === node)
  );
};

/** The module a static import or export names, if it is written. */
const moduleOf = (node: ts.ImportDeclaration | ts.ExportDeclaration): string | undefined =>
  node.moduleSpecifier !== undefined && ts.isStringLiteral(node.moduleSpecifier)
    ? node.moduleSpecifier.text
    : undefined;

/** What `node` does that this guard refuses, if anything. */
const refusal = (file: ts.SourceFile, node: ts.Node): string | undefined => {
  if (ts.isPropertyAccessExpression(node)) {
    const holder = holderOf(node.expression);
    if (holder !== undefined && MODULE_MOCKS.has(node.name.text)) {
      return `${holder}.${node.name.text}`;
    }
  }
  if (ts.isElementAccessExpression(node)) {
    const holder = holderOf(node.expression);
    if (holder !== undefined) {
      const key = node.argumentExpression;
      if (!ts.isStringLiteralLike(key)) {
        throw new UnreadableSourceError(
          `${file.fileName} line ${String(lineOf(file, node))}: ${holder}[…] with a computed ` +
            "key cannot be judged",
        );
      }
      return MODULE_MOCKS.has(key.text) ? `${holder}["${key.text}"]` : undefined;
    }
  }
  const holder = holderOf(node);
  if (
    holder !== undefined &&
    !isMemberRoot(node) &&
    !(ts.isIdentifier(node) && isNotAValue(node))
  ) {
    return `${holder} held, passed or declared, so its members cannot be judged`;
  }
  if ((ts.isImportSpecifier(node) || ts.isExportSpecifier(node)) && node.propertyName) {
    const from = node.propertyName.text;
    const to = node.name.text;
    const renamed = [from, to].find((name) => HOLDERS.has(name));
    if (renamed !== undefined && from !== to) {
      return `${renamed} renamed on ${ts.isImportSpecifier(node) ? "import" : "export"}`;
    }
  }
  if (ts.isImportDeclaration(node) && moduleOf(node) === "vitest") {
    const { name, namedBindings } = node.importClause ?? {};
    if (
      name !== undefined ||
      (namedBindings !== undefined && ts.isNamespaceImport(namedBindings))
    ) {
      return "vitest imported whole";
    }
  }
  if (ts.isExportDeclaration(node) && moduleOf(node) === "vitest") {
    if (node.exportClause === undefined || ts.isNamespaceExport(node.exportClause)) {
      return "vitest exported whole";
    }
  }
  if (ts.isCallExpression(node)) {
    const isImport =
      node.expression.kind === ts.SyntaxKind.ImportKeyword ||
      (ts.isIdentifier(node.expression) && node.expression.text === "require");
    const [module] = node.arguments;
    if (isImport && module !== undefined && ts.isStringLiteralLike(module)) {
      return module.text === "vitest" ? "vitest imported by a call" : undefined;
    }
  }
  return undefined;
};

/** Each place `file` mocks a module or hides `vi` from this guard: `line N: what`, in order. */
export const moduleMocks = (file: ts.SourceFile): string[] =>
  nodes(file).flatMap((node) => {
    const why = refusal(file, node);
    return why === undefined ? [] : [`line ${String(lineOf(file, node))}: ${why}`];
  });

/** Every `vi` or `vitest` name in `file`, as the parse tree holds it: the guard's population. */
export const holderNames = (file: ts.SourceFile): ts.Identifier[] =>
  nodes(file).filter(
    (node): node is ts.Identifier => ts.isIdentifier(node) && HOLDERS.has(node.text),
  );
