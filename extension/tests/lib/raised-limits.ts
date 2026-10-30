/**
 * What no test, helper or config may do to a test's limit (#323 AC 2, AC 3). Shyden's rule
 * (2026-10-07, every project): every unit test runs in under 1 s, the runner's timeout, and no
 * limit is ever raised. vitest's limits are set in one place, the unit project in
 * `vitest.config.ts`; every other suite keeps one limit at its CI step and none inside.
 *
 * Every call is judged by its name, whatever it was imported from, and the forms that would hide
 * one from that judgement are refused: a runner renamed, imported whole, held or passed instead of
 * called, or a local name hiding it (yawelo-idle #477: "everything needs to be checked").
 */
import { codeText, lineOf, nodes, ts } from "./source.ts";

/** The one place a limit is set: its keys are pinned by the guard's own test. */
export const LIMITS_HOME = "vitest.config.ts";

const RUNNERS = new Set(["test", "it", "describe", "suite", "bench"]);
const HOOKS = new Set([
  "beforeAll",
  "beforeEach",
  "afterAll",
  "afterEach",
  "onTestFinished",
  "onTestFailed",
]);
/** The names a test file reaches the runner by, which no local name may hide. */
const NAMES = new Set([...RUNNERS, ...HOOKS, "vi"]);
/** Members that return a runner to be called: `test.each(table)("a %i", body)`. */
const MODIFIER_CALLS = new Set(["each", "for", "skipIf", "runIf"]);
/** Members that set a limit, or make a runner under another name. */
const LIMIT_MEMBERS = new Set(["setConfig", "setTimeout", "slow", "extend", "scoped"]);
const RUNNER_MODULES = new Set(["vitest", "@vitest/runner", "@playwright/test", "node:test"]);
const LIMIT_KEY = /^(?:test|hook|teardown)?timeout$/iu;
const CLOCK_MEMBERS = new Set([
  "now",
  "hrtime",
  "cpuUsage",
  "threadCpuUsage",
  "uptime",
  "timeOrigin",
]);
const CLOCK_MODULES = new Set(["perf_hooks", "node:perf_hooks"]);
const LIMIT_FLAG = /--(?:test|hook|teardown)-?[Tt]imeout\b/gu;
const CALL_TEXT = new RegExp(
  `(?<![\\w$.]\\s?)\\b(?:${[...RUNNERS, ...HOOKS].join("|")})\\s(?:\\.\\s[\\w$]+\\s|\\[\\s[^\\]]*\\]\\s)*\\(`,
  "gu",
);

const at = (file: ts.SourceFile, node: ts.Node, what: string): string =>
  `line ${String(lineOf(file, node))}: ${what}`;

/** The name a member read is written with: `a.b` and `a["b"]`; undefined for `a[key]`. */
const memberName = (node: ts.Node): string | undefined => {
  if (ts.isPropertyAccessExpression(node)) {
    return node.name.text;
  }
  if (ts.isElementAccessExpression(node) && ts.isStringLiteralLike(node.argumentExpression)) {
    return node.argumentExpression.text;
  }
  return undefined;
};

type Wrapping =
  | ts.PropertyAccessExpression
  | ts.ElementAccessExpression
  | ts.CallExpression
  | ts.ParenthesizedExpression
  | ts.NonNullExpression;

const wraps = (parent: ts.Node, child: ts.Node): parent is Wrapping =>
  (ts.isPropertyAccessExpression(parent) ||
    ts.isElementAccessExpression(parent) ||
    ts.isCallExpression(parent) ||
    ts.isParenthesizedExpression(parent) ||
    ts.isNonNullExpression(parent)) &&
  parent.expression === child;

/** Where the chain of member reads and calls that starts at `node` ends. */
const chainTop = (node: ts.Node): ts.Node => {
  let current = node;
  while (wraps(current.parent, current)) {
    current = current.parent;
  }
  return current;
};

/** The identifier a chain of member reads and calls starts from, if it starts from one. */
const rootOf = (node: ts.Expression): ts.Identifier | undefined => {
  let current: ts.Expression = node;
  while (
    ts.isPropertyAccessExpression(current) ||
    ts.isElementAccessExpression(current) ||
    ts.isCallExpression(current) ||
    ts.isParenthesizedExpression(current) ||
    ts.isNonNullExpression(current)
  ) {
    current = current.expression;
  }
  return ts.isIdentifier(current) ? current : undefined;
};

/** A call whose callee is a member read named in `names`: `test.extend(x)`, `test.each(t)`. */
const callsMember = (node: ts.Node, names: ReadonlySet<string>): boolean => {
  if (!ts.isCallExpression(node)) {
    return false;
  }
  const name = memberName(node.expression);
  return name !== undefined && names.has(name);
};

/** The declarations whose `name` binds a value under that name in this file. */
const DECLARING = new Set([
  ts.SyntaxKind.VariableDeclaration,
  ts.SyntaxKind.Parameter,
  ts.SyntaxKind.FunctionDeclaration,
  ts.SyntaxKind.FunctionExpression,
  ts.SyntaxKind.ClassDeclaration,
  ts.SyntaxKind.NamespaceImport,
]);

/** The parents whose `name` is a key or a member, not a reference to a value. */
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

const named = (node: ts.Node, identifier: ts.Identifier): boolean =>
  (node as { name?: ts.Node }).name === identifier;

/**
 * What a use of a runner, hook or `vi` name is: a key or a member's name (no use of the runner),
 * an import or export (judged with its specifier, which names both sides of a rename), a local
 * declaration hiding it, a call through a limit member (refused by the member), a test or hook
 * declared by a call, or the runner held or passed instead of called.
 */
type Use = "key" | "import" | "declared" | "limit-member" | "call" | "held";

const useOf = (identifier: ts.Identifier): Use => {
  const { parent } = identifier;
  if ((KEYED.has(parent.kind) && named(parent, identifier)) || ts.isQualifiedName(parent)) {
    return "key";
  }
  if (ts.isImportClause(parent) || ts.isImportSpecifier(parent) || ts.isExportSpecifier(parent)) {
    return "import";
  }
  if (ts.isBindingElement(parent)) {
    return parent.propertyName === undefined && named(parent, identifier) ? "declared" : "import";
  }
  if (DECLARING.has(parent.kind) && named(parent, identifier)) {
    return "declared";
  }
  const top = chainTop(identifier);
  if (callsMember(top, LIMIT_MEMBERS)) {
    return "limit-member";
  }
  return ts.isCallExpression(top) && !callsMember(top, MODIFIER_CALLS) ? "call" : "held";
};

/** Why a use of a runner, hook or `vi` name hides a call from this guard, if it does. `vi` is
 * judged by member alone: `setConfig` is refused wherever it is read. */
const hiddenBy = (identifier: ts.Identifier): string | undefined => {
  const use = useOf(identifier);
  if (use === "declared") {
    return `${identifier.text} declared here, hiding the runner's`;
  }
  return use === "held" && identifier.text !== "vi"
    ? `${identifier.text} held or passed, not called`
    : undefined;
};

/** Each test or hook declaration in `file`: the call a runner or hook name ends in. */
export const declaringCalls = (file: ts.SourceFile): ts.CallExpression[] =>
  nodes(file).flatMap((node) =>
    ts.isIdentifier(node) &&
    (RUNNERS.has(node.text) || HOOKS.has(node.text)) &&
    useOf(node) === "call"
      ? [chainTop(node) as ts.CallExpression]
      : [],
  );

/** The same count from `file`'s code text: each runner or hook name a call opens on. */
export const declaringCallsByText = (file: ts.SourceFile): number =>
  [...codeText(file).matchAll(CALL_TEXT)].length;

/** The module an import, export, `import()` or `require()` names, as written; null if not written. */
const moduleOf = (node: ts.Node): string | null | undefined => {
  if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) {
    // The grammar writes a declaration's module as a string; `export { a }` names none.
    return (node.moduleSpecifier as ts.StringLiteral | undefined)?.text;
  }
  if (
    ts.isCallExpression(node) &&
    (node.expression.kind === ts.SyntaxKind.ImportKeyword ||
      (ts.isIdentifier(node.expression) && node.expression.text === "require"))
  ) {
    const [specifier] = node.arguments;
    return specifier !== undefined && ts.isStringLiteralLike(specifier) ? specifier.text : null;
  }
  return undefined;
};

/** The written name of an object key: `a`, `"a"` and `["a"]`; undefined when not written. */
const keyName = (name: ts.PropertyName): string | undefined => {
  if (ts.isIdentifier(name) || ts.isStringLiteralLike(name)) {
    return name.text;
  }
  if (ts.isComputedPropertyName(name) && ts.isStringLiteralLike(name.expression)) {
    return name.expression.text;
  }
  return undefined;
};

/** The member a destructuring reads: `{ now }` and `{ now: read }` both read `now`. */
const bindingKey = (node: ts.BindingElement): string | undefined => {
  const key = node.propertyName ?? node.name;
  return ts.isIdentifier(key) || ts.isStringLiteralLike(key) ? key.text : undefined;
};

/** Why `node` sets, raises or hides a limit, if it does. */
const limitAt = (
  file: ts.SourceFile,
  node: ts.Node,
  calls: ReadonlySet<ts.CallExpression>,
): string | undefined => {
  if (ts.isIdentifier(node) && NAMES.has(node.text)) {
    return hiddenBy(node);
  }
  if (ts.isCallExpression(node) && calls.has(node)) {
    // A declaring call starts from the runner or hook name it was found by. A test takes its
    // name and body, a hook its body: anything past them is a limit or options (a `timeout` key
    // inside them is refused as a key as well).
    const root = (rootOf(node.expression) as ts.Identifier).text;
    const most = HOOKS.has(root) ? 1 : 2;
    return node.arguments.length > most ? `${root} is given a limit or options` : undefined;
  }
  if (ts.isElementAccessExpression(node) && memberName(node) === undefined) {
    const root = rootOf(node.expression);
    return root !== undefined && (RUNNERS.has(root.text) || HOOKS.has(root.text))
      ? `a member of ${root.text} not written as a name`
      : undefined;
  }
  const member = memberName(node) ?? (ts.isBindingElement(node) ? bindingKey(node) : undefined);
  if (member !== undefined && LIMIT_MEMBERS.has(member)) {
    return `.${member}, which sets a limit or names a runner`;
  }
  // `const { [name]: read } = vi` could read setConfig, or a clock's now, unseen: refused.
  if (ts.isBindingElement(node) && node.propertyName !== undefined && member === undefined) {
    return "a destructured member not written as a name";
  }
  if (ts.isPropertyAssignment(node) || ts.isShorthandPropertyAssignment(node)) {
    const key = keyName(node.name);
    const value = ts.isPropertyAssignment(node) ? node.initializer : node.name;
    return key !== undefined && LIMIT_KEY.test(key)
      ? `a limit key ${node.name.getText(file)}: ${value.getText(file)}`
      : undefined;
  }
  if (ts.isImportDeclaration(node) && node.importClause !== undefined) {
    const module = moduleOf(node);
    const { name, namedBindings } = node.importClause;
    const whole =
      name !== undefined || (namedBindings !== undefined && ts.isNamespaceImport(namedBindings));
    return typeof module === "string" && RUNNER_MODULES.has(module) && whole
      ? `${module} imported whole`
      : undefined;
  }
  if (ts.isImportSpecifier(node) || ts.isExportSpecifier(node) || ts.isBindingElement(node)) {
    const from =
      node.propertyName !== undefined && ts.isIdentifier(node.propertyName)
        ? node.propertyName.text
        : undefined;
    const to = ts.isIdentifier(node.name) ? node.name.text : undefined;
    const runner = [from, to].find((name) => name !== undefined && NAMES.has(name));
    const where = ts.isImportSpecifier(node)
      ? "on import"
      : ts.isExportSpecifier(node)
        ? "on export"
        : "in a binding";
    return from !== undefined && runner !== undefined && from !== to
      ? `${runner} renamed ${where}`
      : undefined;
  }
  if (ts.isCallExpression(node)) {
    const module = moduleOf(node);
    if (module === null) {
      return "an import whose module is not written";
    }
    return module !== undefined && RUNNER_MODULES.has(module)
      ? `${module} imported by a call`
      : undefined;
  }
  return undefined;
};

/** Each place `file` sets, raises or hides a test's limit: `line N: what`, in source order. */
export const raisedLimits = (file: ts.SourceFile): string[] => {
  const calls = new Set(declaringCalls(file));
  return nodes(file).flatMap((node) => {
    const what = limitAt(file, node, calls);
    return what === undefined ? [] : [at(file, node, what)];
  });
};

/** Why `node` reads a clock, if it does. */
const clockAt = (node: ts.Node): string | undefined => {
  const member = memberName(node) ?? (ts.isBindingElement(node) ? bindingKey(node) : undefined);
  if (member !== undefined && CLOCK_MEMBERS.has(member)) {
    return `.${member} reads a clock`;
  }
  if (
    ts.isNewExpression(node) &&
    ts.isIdentifier(node.expression) &&
    node.expression.text === "Date"
  ) {
    return (node.arguments?.length ?? 0) === 0 ? "new Date() reads a clock" : undefined;
  }
  if (
    ts.isCallExpression(node) &&
    ts.isIdentifier(node.expression) &&
    node.expression.text === "Date"
  ) {
    return "Date() reads a clock";
  }
  const module = moduleOf(node);
  return typeof module === "string" && CLOCK_MODULES.has(module) ? `${module} imported` : undefined;
};

/** Each clock `file` reads, by which a test could time itself against a budget of its own. */
export const clockReads = (file: ts.SourceFile): string[] =>
  nodes(file).flatMap((node) => {
    const what = clockAt(node);
    return what === undefined ? [] : [at(file, node, what)];
  });

/** Each vitest limit flag in an npm script. */
export const limitFlags = (script: string): string[] =>
  [...script.matchAll(LIMIT_FLAG)].map((match) => match[0]);
