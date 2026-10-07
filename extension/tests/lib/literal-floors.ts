/**
 * A floor typed into a test (spec §14.2, AC1): a literal lower bound on a population, which is
 * tight only on the day it is measured. Floors live in `tests/floors.json`; this reader refuses
 * every way a test can write one by hand. A bound of 0 is a non-emptiness check, not a floor, and
 * a ceiling (`toBeLessThan`) is a budget, not a floor; both are allowed.
 */
import { lineOf, nodes, ts, UnreadableSourceError } from "./source.ts";

const LOWER = new Set(["toBeGreaterThan", "toBeGreaterThanOrEqual"]);
const UPPER = new Set(["toBeLessThan", "toBeLessThanOrEqual"]);
const MODIFIERS = new Set(["not", "resolves", "rejects"]);
const KINDS = new Set(["soft", "poll"]);

/** Whether `node` is an assertion: `expect(…)`, `expect.soft(…)` or `expect.poll(…)`. */
export const isAssertion = (node: ts.Node): node is ts.CallExpression => {
  if (!ts.isCallExpression(node)) {
    return false;
  }
  const callee = node.expression;
  if (ts.isIdentifier(callee)) {
    return callee.text === "expect";
  }
  return (
    ts.isPropertyAccessExpression(callee) &&
    ts.isIdentifier(callee.expression) &&
    callee.expression.text === "expect" &&
    KINDS.has(callee.name.text)
  );
};

/** Every assertion in `file`. */
export const assertionsOf = (file: ts.SourceFile): ts.CallExpression[] =>
  nodes(file).filter(isAssertion);

/** The number a literal writes, with its sign; `undefined` for anything else. */
const literalValue = (node: ts.Node): number | undefined => {
  if (ts.isNumericLiteral(node) || ts.isBigIntLiteral(node)) {
    return Number(node.text.replaceAll("_", "").replace(/n$/u, ""));
  }
  if (ts.isPrefixUnaryExpression(node) && node.operator === ts.SyntaxKind.MinusToken) {
    const value = literalValue(node.operand);
    return value === undefined ? undefined : -value;
  }
  return undefined;
};

const isFloor = (node: ts.Node): boolean => {
  const value = literalValue(node);
  return value !== undefined && value !== 0;
};

/** The literal `name` is declared with in `file`, `undefined` if it is computed; a name not
 * declared there as a variable cannot be classified, so it is refused by name. */
const boundOf = (file: ts.SourceFile, name: ts.Identifier): ts.Node | undefined => {
  const declared = nodes(file).find(
    (node): node is ts.VariableDeclaration =>
      ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === name.text,
  );
  if (declared?.initializer === undefined) {
    throw new UnreadableSourceError(
      `${file.fileName} line ${String(lineOf(file, name))}: cannot tell whether ${name.text} is ` +
        "a literal floor; bound an assertion by a value computed in the test, or by a recorded floor",
    );
  }
  return isFloor(declared.initializer) ? declared.initializer : undefined;
};

/** The lower-bound matcher `node` calls on an assertion, with its argument, if it is one. */
const lowerBound = (node: ts.Node): { matcher: string; bound: ts.Expression } | undefined => {
  if (!ts.isCallExpression(node) || !ts.isPropertyAccessExpression(node.expression)) {
    return undefined;
  }
  const matcher = node.expression.name.text;
  let receiver = node.expression.expression;
  let negated = false;
  while (ts.isPropertyAccessExpression(receiver) && MODIFIERS.has(receiver.name.text)) {
    negated = negated !== (receiver.name.text === "not");
    receiver = receiver.expression;
  }
  const [bound] = node.arguments;
  const lower = negated ? UPPER.has(matcher) : LOWER.has(matcher);
  return lower && isAssertion(receiver) && bound !== undefined
    ? { matcher: `${negated ? "not." : ""}${matcher}`, bound }
    : undefined;
};

const COMPARISONS = new Map<ts.SyntaxKind, "left" | "right">([
  [ts.SyntaxKind.GreaterThanToken, "right"],
  [ts.SyntaxKind.GreaterThanEqualsToken, "right"],
  [ts.SyntaxKind.LessThanToken, "left"],
  [ts.SyntaxKind.LessThanEqualsToken, "left"],
]);

/** A comparison inside an assertion's subject that bounds a value from below by a literal. */
const isLiteralComparison = (node: ts.Node): node is ts.BinaryExpression => {
  if (!ts.isBinaryExpression(node)) {
    return false;
  }
  const side = COMPARISONS.get(node.operatorToken.kind);
  return side !== undefined && isFloor(node[side]);
};

/** Every literal floor `file`'s assertions write, by line. */
export const literalFloors = (file: ts.SourceFile): string[] =>
  nodes(file).flatMap((node) => {
    const at = `line ${String(lineOf(file, node))}`;
    if (isAssertion(node)) {
      return node.arguments
        .flatMap((argument) => [argument, ...descendants(argument)])
        .filter(isLiteralComparison)
        .map((comparison) => `${at}: ${comparison.getText(file)}`);
    }
    const found = lowerBound(node);
    if (found === undefined) {
      return [];
    }
    const { matcher, bound } = found;
    if (ts.isIdentifier(bound)) {
      const literal = boundOf(file, bound);
      return literal === undefined
        ? []
        : [`${at}: ${matcher}(${bound.text} = ${literal.getText(file)})`];
    }
    return isFloor(bound) ? [`${at}: ${matcher}(${bound.getText(file)})`] : [];
  });

/** Every node under `node`, by the compiler's child walk. */
const descendants = (node: ts.Node): ts.Node[] => {
  const found: ts.Node[] = [];
  const visit = (child: ts.Node): void => {
    found.push(child);
    ts.forEachChild(child, visit);
  };
  ts.forEachChild(node, visit);
  return found;
};

const FLOOR_NAME = /floor/iu;

/** The variables `file` declares by name: the population the floor-constant check judges. */
export const variablesOf = (file: ts.SourceFile): ts.VariableDeclaration[] =>
  nodes(file).filter(
    (node): node is ts.VariableDeclaration =>
      ts.isVariableDeclaration(node) && ts.isIdentifier(node.name),
  );

/** Every constant named like a floor that `file` sets to a literal, by line. */
export const floorConstants = (file: ts.SourceFile): string[] =>
  variablesOf(file).flatMap((variable) => {
    const { name, initializer } = variable;
    return FLOOR_NAME.test(name.getText(file)) && initializer !== undefined && isFloor(initializer)
      ? [
          `line ${String(lineOf(file, variable))}: ${name.getText(file)} = ${initializer.getText(file)}`,
        ]
      : [];
  });
