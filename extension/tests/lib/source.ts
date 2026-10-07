/**
 * The one way a guard reads source (spec §14.2, Shyden's source-text rule): the TypeScript
 * compiler's own parse tree, so a name inside a comment, a string, a template's text or a regex
 * literal is never read as code. A hand-written stripper gets regex literals and template
 * substitutions wrong in exactly the places a guard looks, so no guard strips text itself. This
 * module is the only one that imports the compiler (a guard checks it); guards take `ts` from here.
 */
import { readFileSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import ts from "typescript";

export { ts };

/** The workspace's root, `extension/`: every path a guard reports is relative to it. */
export const EXTENSION = join(import.meta.dirname, "..", "..");

/** A file the reader cannot classify, refused by name rather than skipped. */
export class UnreadableSourceError extends Error {
  override name = "UnreadableSourceError";
}

const KINDS: Readonly<Record<string, ts.ScriptKind>> = {
  ".ts": ts.ScriptKind.TS,
  ".mts": ts.ScriptKind.TS,
  ".cts": ts.ScriptKind.TS,
  ".js": ts.ScriptKind.JS,
  ".mjs": ts.ScriptKind.JS,
  ".cjs": ts.ScriptKind.JS,
};

const FORMAT: ts.FormatDiagnosticsHost = {
  getCanonicalFileName: (name) => name,
  getCurrentDirectory: () => EXTENSION,
  getNewLine: () => "\n",
};

/** The parse tree of `text`; a file of another kind or with a syntax error is refused by name. */
export const parse = (text: string, fileName: string): ts.SourceFile => {
  const kind = KINDS[extname(fileName)];
  if (kind === undefined) {
    throw new UnreadableSourceError(`${fileName}: not a TypeScript or JavaScript file`);
  }
  const { diagnostics = [] } = ts.transpileModule(text, { fileName, reportDiagnostics: true });
  if (diagnostics.length > 0) {
    throw new UnreadableSourceError(ts.formatDiagnostics(diagnostics, FORMAT).trim());
  }
  return ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true, kind);
};

/** The parse tree of the file at `path`, relative to `extension/`. */
export const readSource = (path: string): ts.SourceFile =>
  parse(readFileSync(join(EXTENSION, path), "utf8"), path);

/** The line `node` starts on, counted from 1. */
export const lineOf = (file: ts.SourceFile, node: ts.Node): number =>
  file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1;

/** Every node of `file`, depth first, by the compiler's child walk: the walk every guard judges. */
export const nodes = (file: ts.SourceFile): ts.Node[] => {
  const found: ts.Node[] = [];
  const visit = (node: ts.Node): void => {
    found.push(node);
    ts.forEachChild(node, visit);
  };
  ts.forEachChild(file, visit);
  return found;
};

const isJSDoc = (node: ts.Node): boolean =>
  node.kind >= ts.SyntaxKind.FirstJSDocNode && node.kind <= ts.SyntaxKind.LastJSDocNode;

/**
 * Every token of `file` in order, read through the tree's token lists (`getChildren`), JSDoc and
 * the end-of-file token left out: a second walk, independent of `nodes`, that cross-checks it.
 */
export const tokens = (file: ts.SourceFile): ts.Node[] => {
  const found: ts.Node[] = [];
  const visit = (node: ts.Node): void => {
    if (isJSDoc(node)) {
      return;
    }
    const children = node.getChildren(file);
    if (children.length > 0) {
      children.forEach(visit);
    } else if (node.kind <= ts.SyntaxKind.LastToken && node.kind !== ts.SyntaxKind.EndOfFileToken) {
      found.push(node);
    }
  };
  visit(file);
  return found;
};

/** What each literal's content becomes in `codeText`, so a name inside one is never code. */
const BLANKED: Partial<Record<ts.SyntaxKind, string>> = {
  [ts.SyntaxKind.StringLiteral]: '""',
  [ts.SyntaxKind.NoSubstitutionTemplateLiteral]: "``",
  [ts.SyntaxKind.TemplateHead]: "`${",
  [ts.SyntaxKind.TemplateMiddle]: "}${",
  [ts.SyntaxKind.TemplateTail]: "}`",
  [ts.SyntaxKind.RegularExpressionLiteral]: "/(?:)/",
};

/**
 * `file`'s code as text, one space between tokens, with every comment removed and every string,
 * template text and regex literal emptied: the text an independent cross-check counts in.
 */
export const codeText = (file: ts.SourceFile): string =>
  tokens(file)
    .map((token) => BLANKED[token.kind] ?? token.getText(file))
    .join(" ");

/**
 * The modules the compiler's own import pre-scanner finds in `text`, without building a tree: an
 * independent count of a file's imports, to cross-check a reader that walks the tree.
 */
export const preScannedImports = (text: string): string[] =>
  ts.preProcessFile(text, true, true).importedFiles.map((imported) => imported.fileName);

/**
 * Each library file a program parsed (anything under `node_modules`, which nothing changes during a
 * run), kept for every later program in this worker, by file and parse options. A program's own
 * files are read afresh every time. Measured on 2026-10-07 (#276): a program parses 182 files,
 * almost all of them the ES2024 and DOM libraries and `@types/node`; built cold it costs about
 * 450 ms here and 3.7 s on a CI runner, reusing them 13-17 ms. No `oldProgram` is passed, so the
 * compiler never asks for a fresh copy of a file it has.
 */
const LIBRARY = new Map<string, ts.SourceFile | undefined>();

/** A compiler host for `options` that reads library files once per worker (see `LIBRARY`). */
const libraryCachingHost = (options: ts.CompilerOptions): ts.CompilerHost => {
  const host = ts.createCompilerHost(options);
  const read = host.getSourceFile.bind(host);
  host.getSourceFile = (fileName, version, onError) => {
    if (!fileName.split("/").includes("node_modules")) {
      return read(fileName, version, onError);
    }
    const key = `${JSON.stringify(version)} ${fileName}`;
    if (!LIBRARY.has(key)) {
      LIBRARY.set(key, read(fileName, version, onError));
    }
    return LIBRARY.get(key);
  };
  return host;
};

/**
 * The type checker over `paths` (relative to `extension/`, or absolute), compiled with the
 * workspace's own `tsconfig.json`. A config that cannot be read, a path the program did not
 * compile and a file with any compiler error are refused by name: types inferred around an error
 * are not the types the code has.
 */
export const typeChecked = (
  paths: readonly string[],
  configPath: string = join(EXTENSION, "tsconfig.json"),
): { checker: ts.TypeChecker; files: ts.SourceFile[]; program: ts.Program } => {
  let unreadable = `${configPath}: not read`;
  const config = ts.getParsedCommandLineOfConfigFile(configPath, undefined, {
    ...ts.sys,
    onUnRecoverableConfigFileDiagnostic: (diagnostic) => {
      unreadable = ts.formatDiagnostics([diagnostic], FORMAT).trim();
    },
  });
  if (config === undefined) {
    throw new UnreadableSourceError(unreadable);
  }
  if (config.errors.length > 0) {
    throw new UnreadableSourceError(ts.formatDiagnostics(config.errors, FORMAT).trim());
  }
  const roots = paths.map((path) => resolve(EXTENSION, path));
  const program = ts.createProgram(roots, config.options, libraryCachingHost(config.options));
  const files = roots.map((root) => {
    const file = program.getSourceFile(root);
    if (file === undefined) {
      throw new UnreadableSourceError(`${root}: not compiled`);
    }
    const errors = [
      ...program.getSyntacticDiagnostics(file),
      ...program.getSemanticDiagnostics(file),
    ];
    if (errors.length > 0) {
      throw new UnreadableSourceError(ts.formatDiagnostics(errors, FORMAT).trim());
    }
    return file;
  });
  return { checker: program.getTypeChecker(), files, program };
};
