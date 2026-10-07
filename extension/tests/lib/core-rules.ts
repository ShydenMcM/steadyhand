/**
 * What core may not hold (spec §3, §4.1). Core is pure logic: no browser API, so it runs the same
 * in the side panel, a test and the parity harness. And `number` never holds money: money is a
 * `bigint` of minor units and ratios are `decimal.js`, as Python refuses `float`. Shyden chose
 * (2026-10-06, #221) to judge all of core, by the written word AND by the type checker, because a
 * plain `const fee = 100` is a `number` that never writes the word.
 */
import { lineOf, nodes, ts, UnreadableSourceError } from "./source.ts";

/** The browser's globals spec §3 names, and the objects they hang from. */
export const BROWSER_GLOBALS = new Set(["window", "document", "chrome", "indexedDB"]);
const GLOBAL_OBJECTS = new Set(["globalThis", "self", "window"]);

/** The globals that turn text into a `number`, or name its type. */
export const NUMBER_GLOBALS = new Set(["Number", "parseFloat", "parseInt"]);

/** The declarations whose `name` is a key, not a reference to a value. */
const KEYED = new Set([
  ts.SyntaxKind.PropertyAccessExpression,
  ts.SyntaxKind.PropertyAssignment,
  ts.SyntaxKind.PropertyDeclaration,
  ts.SyntaxKind.PropertySignature,
  ts.SyntaxKind.MethodDeclaration,
  ts.SyntaxKind.MethodSignature,
  ts.SyntaxKind.GetAccessor,
  ts.SyntaxKind.SetAccessor,
  ts.SyntaxKind.EnumMember,
]);

/** Whether `node` refers to a value by its name, rather than naming a key or a member. */
const isReference = (node: ts.Identifier): boolean => {
  const { parent } = node;
  if (KEYED.has(parent.kind)) {
    return (parent as { name?: ts.Node }).name !== node;
  }
  return !(ts.isQualifiedName(parent) && parent.right === node);
};

const at = (file: ts.SourceFile, node: ts.Node, what: string): string =>
  `line ${String(lineOf(file, node))}: ${what}`;

/** Every use of a browser global in `file`: by name, or as a property of a global object. */
export const browserGlobals = (file: ts.SourceFile): string[] =>
  nodes(file).flatMap((node) => {
    if (ts.isIdentifier(node)) {
      return BROWSER_GLOBALS.has(node.text) && isReference(node) ? [at(file, node, node.text)] : [];
    }
    if (ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.expression)) {
      const owner = node.expression.text;
      const name = node.name.text;
      return GLOBAL_OBJECTS.has(owner) && BROWSER_GLOBALS.has(name)
        ? [at(file, node, `${owner}.${name}`)]
        : [];
    }
    if (ts.isElementAccessExpression(node) && ts.isIdentifier(node.expression)) {
      const owner = node.expression.text;
      if (!GLOBAL_OBJECTS.has(owner)) {
        return [];
      }
      const key = node.argumentExpression;
      if (!ts.isStringLiteralLike(key)) {
        throw new UnreadableSourceError(
          `${file.fileName} line ${String(lineOf(file, node))}: ${owner}[…] with a computed key ` +
            "cannot be judged",
        );
      }
      return BROWSER_GLOBALS.has(key.text) ? [at(file, node, `${owner}["${key.text}"]`)] : [];
    }
    return [];
  });

/** A whole number written as one: decimal, hex, octal or binary digits, no point, no exponent. */
const WHOLE = /^(?:0[xX][\da-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+|\d[\d_]*)$/u;

/** Every place `file` writes `number`: the type keyword, a number global, a non-whole literal. */
export const numberWords = (file: ts.SourceFile): string[] =>
  nodes(file).flatMap((node) => {
    if (node.kind === ts.SyntaxKind.NumberKeyword) {
      return [at(file, node, "number")];
    }
    if (ts.isIdentifier(node) && NUMBER_GLOBALS.has(node.text) && isReference(node)) {
      return [at(file, node, node.text)];
    }
    // The literal as written: `text` is the normalised value, which reads `1e3` as `1000`.
    if (ts.isNumericLiteral(node) && !WHOLE.test(node.getText(file))) {
      return [at(file, node, `literal ${node.getText(file)}`)];
    }
    return [];
  });

/** Whether `type` is, or holds, a `number`: a union member, an array or type argument, a field
 * of an anonymous object type. A named interface or class is judged where it is declared. */
const holdsNumber = (checker: ts.TypeChecker, type: ts.Type, seen: Set<ts.Type>): boolean => {
  if (seen.has(type)) {
    return false;
  }
  seen.add(type);
  if ((type.flags & ts.TypeFlags.NumberLike) !== 0) {
    return true;
  }
  if (type.isUnionOrIntersection()) {
    return type.types.some((member) => holdsNumber(checker, member, seen));
  }
  const object = type as ts.ObjectType;
  if ((object.objectFlags & ts.ObjectFlags.Reference) !== 0) {
    return checker
      .getTypeArguments(object as ts.TypeReference)
      .some((argument) => holdsNumber(checker, argument, seen));
  }
  // An object literal's declared type is anonymous, not flagged ObjectLiteral (measured on
  // 2026-10-06). A function type is anonymous too and has no properties: its result is judged
  // where the function is declared.
  if ((object.objectFlags & ts.ObjectFlags.Anonymous) !== 0) {
    return checker
      .getPropertiesOfType(object)
      .some((property) => holdsNumber(checker, checker.getTypeOfSymbol(property), seen));
  }
  return false;
};

/** The declarations whose value the type pass judges by their name. */
const NAMED = new Set([
  ts.SyntaxKind.VariableDeclaration,
  ts.SyntaxKind.Parameter,
  ts.SyntaxKind.BindingElement,
  ts.SyntaxKind.PropertyDeclaration,
  ts.SyntaxKind.PropertySignature,
  ts.SyntaxKind.PropertyAssignment,
  ts.SyntaxKind.ShorthandPropertyAssignment,
  ts.SyntaxKind.GetAccessor,
]);

/** The functions whose result the type pass judges (a getter's is its property's type, above). */
const RETURNING = new Set([
  ts.SyntaxKind.FunctionDeclaration,
  ts.SyntaxKind.FunctionExpression,
  ts.SyntaxKind.ArrowFunction,
  ts.SyntaxKind.MethodDeclaration,
  ts.SyntaxKind.MethodSignature,
]);

/** A named declaration whose name is an identifier: a destructuring pattern's names are judged
 * as their own binding elements. */
const namedDeclaration = (node: ts.Node): ts.Identifier | undefined => {
  if (!NAMED.has(node.kind)) {
    return undefined;
  }
  const { name } = node as ts.Node & { name: ts.Node };
  return ts.isIdentifier(name) ? name : undefined;
};

/**
 * A function passed straight to a call: its result is set by the callee (a comparator for `sort`
 * must return a `number`), so its parameters are judged and its result is not.
 */
const isCallback = (node: ts.Node): boolean =>
  ts.isCallExpression(node.parent) && node.parent.arguments.some((argument) => argument === node);

/** Every value in `file` the type pass judges: named declarations and the results of functions. */
export const typedDeclarations = (file: ts.SourceFile): ts.Node[] =>
  nodes(file).filter(
    (node) =>
      namedDeclaration(node) !== undefined || (RETURNING.has(node.kind) && !isCallback(node)),
  );

/** Every value in `file` whose type, written or inferred, is or holds a `number`. */
export const numberTypes = (checker: ts.TypeChecker, file: ts.SourceFile): string[] =>
  typedDeclarations(file).flatMap((node) => {
    const name = namedDeclaration(node);
    if (name !== undefined) {
      const type = checker.getTypeAtLocation(name);
      return holdsNumber(checker, type, new Set())
        ? [at(file, node, `${name.text}: ${checker.typeToString(type)}`)]
        : [];
    }
    return checker
      .getSignaturesOfType(checker.getTypeAtLocation(node), ts.SignatureKind.Call)
      .map((signature) => checker.getReturnTypeOfSignature(signature))
      .filter((result) => holdsNumber(checker, result, new Set()))
      .map((result) => at(file, node, `returns ${checker.typeToString(result)}`));
  });
