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

/** The variable `file` declares as `name`, if it declares one. */
const declarationOf = (file: ts.SourceFile, name: string): ts.VariableDeclaration | undefined =>
  nodes(file).find(
    (node): node is ts.VariableDeclaration =>
      ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === name,
  );

/** Whether the identifier `node`, which names no property (`isPropertyName`), is read as a value
 * of its own rather than as the object a property or element is read from (`rows` in
 * `rows.length` or `rows[i]`). */
const isOperand = (node: ts.Identifier): boolean => {
  const { parent } = node;
  return !(
    (ts.isPropertyAccessExpression(parent) || ts.isElementAccessExpression(parent)) &&
    parent.expression === node
  );
};

/** `node` and every node under it, except inside a function: a function's body is code it runs,
 * not the value it is (the `2` in a helper's `JSON.stringify(x, null, 2)` bounds nothing). */
const valueParts = (node: ts.Node): ts.Node[] => {
  if (ts.isFunctionLike(node)) {
    return [];
  }
  const found: ts.Node[] = [node];
  ts.forEachChild(node, (child) => {
    found.push(...valueParts(child));
  });
  return found;
};

/** The refusal of a bound held in `name`, a value this reader cannot classify. */
const unclassifiable = (file: ts.SourceFile, name: ts.Identifier): UnreadableSourceError =>
  new UnreadableSourceError(
    `${file.fileName} line ${String(lineOf(file, name))}: cannot tell whether ${name.text} is ` +
      "a literal floor; bound an assertion by a value computed in the test, or by a recorded floor",
  );

/** Whether the identifier `node` names a property (`rows.length`'s `length`, `{ min: 3 }`'s
 * `min`) rather than a value. */
const isPropertyName = (node: ts.Identifier): boolean =>
  (ts.isPropertyAccessExpression(node.parent) || ts.isPropertyAssignment(node.parent)) &&
  node.parent.name === node;

/** Every name a parameter binds, through object and array destructuring. */
const boundNames = (name: ts.BindingName): ts.Identifier[] =>
  ts.isIdentifier(name)
    ? [name]
    : name.elements.flatMap((element) =>
        ts.isOmittedExpression(element) ? [] : boundNames(element.name),
      );

/** Whether `node` is a parameter of a function enclosing it (#432): any caller may pass a
 * literal, so a bound reaching one cannot be classified. */
const isParameter = (node: ts.Identifier): boolean => {
  for (let scope = node.parent; !ts.isSourceFile(scope); scope = scope.parent) {
    if (
      ts.isFunctionLike(scope) &&
      scope.parameters.some((parameter) =>
        boundNames(parameter.name).some((bound) => bound.text === node.text),
      )
    ) {
      return true;
    }
  }
  return false;
};

/** Whether `node` holds a non-zero literal anywhere in its value (#362): itself, any node under it
 * (arithmetic, a call's argument, a cast, parentheses), or a name it uses as an operand that
 * `file` declares with one, followed to a fixed point. `seen` holds the names already followed,
 * so a cycle ends. A parameter reached anywhere in it, directly, through a property or element, or
 * nested, cannot be classified and is refused by name (#432). */
const holdsLiteral = (
  file: ts.SourceFile,
  node: ts.Node,
  seen: ReadonlySet<string> = new Set(),
): boolean =>
  valueParts(node).some((part) => {
    if (isFloor(part)) {
      return true;
    }
    if (!ts.isIdentifier(part) || isPropertyName(part)) {
      return false;
    }
    if (isParameter(part)) {
      throw unclassifiable(file, part);
    }
    if (!isOperand(part) || seen.has(part.text)) {
      return false;
    }
    const initializer = declarationOf(file, part.text)?.initializer;
    return (
      initializer !== undefined && holdsLiteral(file, initializer, new Set([...seen, part.text]))
    );
  });

/** The initializer `name` is declared with in `file` when it holds a literal, `undefined` if it is
 * computed; a name not declared there as a variable cannot be classified, so it is refused by name. */
const boundOf = (file: ts.SourceFile, name: ts.Identifier): ts.Node | undefined => {
  const initializer = declarationOf(file, name.text)?.initializer;
  if (initializer === undefined) {
    throw unclassifiable(file, name);
  }
  return holdsLiteral(file, initializer, new Set([name.text])) ? initializer : undefined;
};

/** `node` with its parentheses, casts and non-null marks taken off. */
const unwrapped = (node: ts.Expression): ts.Expression =>
  ts.isParenthesizedExpression(node) ||
  ts.isAsExpression(node) ||
  ts.isSatisfiesExpression(node) ||
  ts.isNonNullExpression(node)
    ? unwrapped(node.expression)
    : node;

const SIGNS = new Set([ts.SyntaxKind.MinusToken, ts.SyntaxKind.PlusToken]);

/** Whether `node` is made of literals alone (#362): a literal, a sign or arithmetic on literals, a
 * cast or parentheses around one, or a name `file` declares with one; nothing read from anywhere
 * else (no call, property or parameter). `seen` holds the names already followed. */
const isLiteralsAlone = (
  file: ts.SourceFile,
  node: ts.Expression,
  seen: ReadonlySet<string> = new Set(),
): boolean => {
  const inner = unwrapped(node);
  if (ts.isNumericLiteral(inner) || ts.isBigIntLiteral(inner)) {
    return true;
  }
  if (ts.isPrefixUnaryExpression(inner)) {
    return SIGNS.has(inner.operator) && isLiteralsAlone(file, inner.operand, seen);
  }
  if (ts.isBinaryExpression(inner)) {
    return isLiteralsAlone(file, inner.left, seen) && isLiteralsAlone(file, inner.right, seen);
  }
  if (!ts.isIdentifier(inner) || seen.has(inner.text)) {
    return false;
  }
  const initializer = declarationOf(file, inner.text)?.initializer;
  return (
    initializer !== undefined && isLiteralsAlone(file, initializer, new Set([...seen, inner.text]))
  );
};

/** Whether `node` is a hand-typed floor value: literals alone, and not zero (a non-emptiness
 * check). The subject of a reversed matcher, `expect(5).toBeLessThan(n)`, and a floor constant. */
const isLiteralValue = (file: ts.SourceFile, node: ts.Expression): boolean =>
  isLiteralsAlone(file, node) && holdsLiteral(file, node);

/** A bound matcher `node` calls on an assertion: its name as written, its argument, the
 * assertion's subject, and whether it bounds the subject from below (`lower`) or, reversed, the
 * argument from below by the subject (`expect(5).toBeLessThan(n)`). */
const boundMatcher = (
  node: ts.Node,
):
  | { matcher: string; bound: ts.Expression; subject: ts.Expression | undefined; lower: boolean }
  | undefined => {
  if (!ts.isCallExpression(node) || !ts.isPropertyAccessExpression(node.expression)) {
    return undefined;
  }
  const name = node.expression.name.text;
  let receiver = node.expression.expression;
  let negated = false;
  while (ts.isPropertyAccessExpression(receiver) && MODIFIERS.has(receiver.name.text)) {
    negated = negated !== (receiver.name.text === "not");
    receiver = receiver.expression;
  }
  const [bound] = node.arguments;
  const lower = negated ? UPPER.has(name) : LOWER.has(name);
  const upper = negated ? LOWER.has(name) : UPPER.has(name);
  return (lower || upper) && isAssertion(receiver) && bound !== undefined
    ? { matcher: `${negated ? "not." : ""}${name}`, bound, subject: receiver.arguments[0], lower }
    : undefined;
};

const COMPARISONS = new Map<ts.SyntaxKind, "left" | "right">([
  [ts.SyntaxKind.GreaterThanToken, "right"],
  [ts.SyntaxKind.GreaterThanEqualsToken, "right"],
  [ts.SyntaxKind.LessThanToken, "left"],
  [ts.SyntaxKind.LessThanEqualsToken, "left"],
]);

/** A comparison inside an assertion's subject whose lower side holds a literal anywhere. It is
 * judged by syntax alone, so `elapsed / 1000 < 30` is refused too: write a ceiling with
 * `toBeLessThan`, where the bound is unambiguous (#362). */
const isLiteralComparison = (file: ts.SourceFile, node: ts.Node): node is ts.BinaryExpression => {
  if (!ts.isBinaryExpression(node)) {
    return false;
  }
  const side = COMPARISONS.get(node.operatorToken.kind);
  return side !== undefined && holdsLiteral(file, node[side]);
};

/** Every literal floor `file`'s assertions write, by line. */
export const literalFloors = (file: ts.SourceFile): string[] =>
  nodes(file).flatMap((node) => {
    const at = `line ${String(lineOf(file, node))}`;
    if (isAssertion(node)) {
      return node.arguments
        .flatMap((argument) => [argument, ...descendants(argument)])
        .filter((part) => isLiteralComparison(file, part))
        .map((comparison) => `${at}: ${comparison.getText(file)}`);
    }
    const found = boundMatcher(node);
    if (found === undefined) {
      return [];
    }
    const { matcher, bound, subject, lower } = found;
    if (!lower) {
      return subject !== undefined && isLiteralValue(file, subject)
        ? [`${at}: expect(${subject.getText(file)}).${matcher}(${bound.getText(file)})`]
        : [];
    }
    if (ts.isIdentifier(bound)) {
      const literal = boundOf(file, bound);
      return literal === undefined
        ? []
        : [`${at}: ${matcher}(${bound.text} = ${literal.getText(file)})`];
    }
    return holdsLiteral(file, bound) ? [`${at}: ${matcher}(${bound.getText(file)})`] : [];
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
    return FLOOR_NAME.test(name.getText(file)) &&
      initializer !== undefined &&
      isLiteralValue(file, initializer)
      ? [
          `line ${String(lineOf(file, variable))}: ${name.getText(file)} = ${initializer.getText(file)}`,
        ]
      : [];
  });
