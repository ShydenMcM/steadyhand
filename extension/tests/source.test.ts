import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { beforeAll, expect, test } from "vitest";
import { floorBreach } from "./lib/floors.ts";
import { searched } from "./lib/population.ts";
import {
  codeText,
  lineOf,
  nodes,
  parse,
  readSource,
  tokens,
  ts,
  typeChecked,
  UnreadableSourceError,
} from "./lib/source.ts";
import { filesUnder, gitListed } from "./lib/walk.ts";

/** Every source file of the workspace a guard may read: TypeScript and JavaScript, tests too. */
const SUFFIXES = [".ts", ".js"] as const;
const FILES = filesUnder(".", SUFFIXES);

/** Where a name is NOT code (AC2): each way the workspace writes a comment, string or regex. */
const CARRIERS: readonly (readonly [string, string])[] = [
  ["a line comment", "// window\n"],
  ["a block comment", "/* window */"],
  ["a JSDoc comment", "/** @param window the page */"],
  ["a double-quoted string", '"window";'],
  ["a single-quoted string", "'window';"],
  ["a template", "`window`;"],
  ["a template's text around a substitution", "`window ${0} window`;"],
  ["a regex literal", "/window/u;"],
  ["a regex holding a slash in a character class", "/[/]window/u;"],
  ["a regex literal after a return", "() => { return /window/u; };"],
];

/** The identifiers named `window` the parse tree reads in `text`. */
const windowsRead = (text: string): number =>
  nodes(parse(text, "sample.ts")).filter((node) => ts.isIdentifier(node) && node.text === "window")
    .length;

/** The times `window` stands as a word in `text`'s code text. */
const windowsInCodeText = (text: string): number =>
  codeText(parse(text, "sample.ts"))
    .split(" ")
    .filter((word) => word === "window").length;

test.each(CARRIERS)("a name inside %s is not read as code", (_, carrier) => {
  expect(windowsRead(carrier)).toBe(0);
  expect(windowsInCodeText(carrier)).toBe(0);
});

test.each(CARRIERS)("a name in code after %s is read as code", (_, carrier) => {
  expect(windowsRead(`${carrier}\nwindow;`)).toBe(1);
  expect(windowsInCodeText(`${carrier}\nwindow;`)).toBe(1);
});

test("a name inside a template's substitution is code", () => {
  expect(windowsRead("`text ${window} text`;")).toBe(1);
  expect(windowsInCodeText("`text ${window} text`;")).toBe(1);
});

test("code text empties every literal and keeps the code around it", () => {
  const file = parse('const a = "x" + `y ${b} z` + /w/u; // c\n', "sample.ts");
  expect(codeText(file)).toBe('const a = "" + `${ b }` + /(?:)/ ;');
});

test("a file with a syntax error is refused by name, line and column", () => {
  expect(() => parse("const = 1;\n", "broken.ts")).toThrow(
    new UnreadableSourceError(
      "broken.ts(1,7): error TS1134: Variable declaration expected.\n" +
        "broken.ts(1,9): error TS1134: Variable declaration expected.",
    ),
  );
});

test("a file that is neither TypeScript nor JavaScript is refused by name", () => {
  expect(() => parse("# notes\n", "notes.md")).toThrow(
    new UnreadableSourceError("notes.md: not a TypeScript or JavaScript file"),
  );
});

test("the refusal is an UnreadableSourceError by name", () => {
  expect(new UnreadableSourceError("x").name).toBe("UnreadableSourceError");
});

test("JavaScript is read as JavaScript", () => {
  expect(codeText(parse("export const a = 1;\n", "sample.mjs"))).toBe("export const a = 1 ;");
});

test("a node's line is counted from 1", () => {
  const file = parse("\n\nwindow;\n", "sample.ts");
  const [found] = nodes(file).filter(ts.isIdentifier);
  expect(found === undefined ? 0 : lineOf(file, found)).toBe(3);
});

/** Write `files` into a fresh directory, run `check` on their paths and the directory, then remove it. */
const inScratch = <T>(
  files: Readonly<Record<string, string>>,
  check: (paths: string[], scratch: string) => T,
): T => {
  const scratch = mkdtempSync(join(tmpdir(), "steadyhand-source-"));
  try {
    const paths = Object.entries(files).map(([name, text]) => {
      const path = join(scratch, name);
      writeFileSync(path, text);
      return path;
    });
    return check(paths, scratch);
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
};

/** The ES5 library file `program` compiled against, the first of the libraries every program loads. */
const libraryOf = (program: ts.Program): ts.SourceFile | undefined =>
  program.getSourceFiles().find(({ fileName }) => fileName.endsWith("/lib.es5.d.ts"));

// The compiler's libraries (ES2024, DOM, @types/node: 182 files) are parsed once per worker, here,
// within the hook's 10 s budget, so each test's own budget holds only its own program (#276:
// built cold every time, this file's first type-checking test took 5.2 s in CI). A program needs a
// root file to load them: `typeChecked([])` loads none (measured), so the hook compiles one.
let warmed: ts.SourceFile | undefined;
beforeAll(() => {
  warmed = inScratch({ "warm.ts": "export {};\n" }, (paths) =>
    libraryOf(typeChecked(paths).program),
  );
});

test("every later program reuses the library files the hook parsed", () => {
  expect(warmed).toBeDefined();
  inScratch({ "a.ts": "export const a = 1n;\n" }, (paths) => {
    expect(libraryOf(typeChecked(paths).program)).toBe(warmed);
  });
});

test("a program under another target parses its own library files", () => {
  const config = '{ "compilerOptions": { "target": "ES2015", "lib": ["ES2024"], "types": [] } }\n';
  inScratch({ "tsconfig.json": config, "c.ts": 'export const c = "c";\n' }, (paths, scratch) => {
    const other = libraryOf(typeChecked(paths.slice(1), join(scratch, "tsconfig.json")).program);
    expect(other).toBeDefined();
    expect(other).not.toBe(warmed);
  });
});

test("a program's own files are read afresh every time", () => {
  inScratch({ "v.ts": "export const v = 1n;\n" }, (paths, scratch) => {
    const typeOfV = (): string[] => {
      const { checker, files } = typeChecked(paths);
      return files.flatMap((file) =>
        nodes(file)
          .filter(ts.isVariableDeclaration)
          .map(({ name }) => checker.typeToString(checker.getTypeAtLocation(name))),
      );
    };
    expect(typeOfV()).toEqual(["1n"]);
    writeFileSync(join(scratch, "v.ts"), 'export const v = "x";\n');
    expect(typeOfV()).toEqual(['"x"']);
  });
});

test("a file with no error is compiled, and its checker reads its types", () => {
  inScratch({ "fine.ts": 'export const name = "x";\n' }, (paths) => {
    const { checker, files } = typeChecked(paths);
    expect(files.map(({ fileName }) => fileName)).toEqual(paths);
    const declared = files.flatMap((file) => nodes(file).filter(ts.isVariableDeclaration));
    expect(
      declared.map(({ name }) => checker.typeToString(checker.getTypeAtLocation(name))),
    ).toEqual(['"x"']);
  });
});

test("a file with a compiler error is refused by name, not judged", () => {
  inScratch({ "broken.ts": "export const a: string = 1;\n" }, (paths) => {
    expect(() => typeChecked(paths)).toThrow(
      /broken\.ts\(1,14\): error TS2322: Type 'number' is not assignable to type 'string'\./u,
    );
  });
});

test("a path the program did not compile is refused by name", () => {
  const missing = join(tmpdir(), "steadyhand-no-such-dir", "missing.ts");
  expect(() => typeChecked([missing])).toThrow(
    new UnreadableSourceError(`${missing}: not compiled`),
  );
});

test("a config that cannot be read is refused by name", () => {
  expect(() => typeChecked([], join(tmpdir(), "steadyhand-no-such-dir", "tsconfig.json"))).toThrow(
    /error TS5083: Cannot read file '.*steadyhand-no-such-dir\/tsconfig\.json'\./u,
  );
});

test("a config with an error is refused by name", () => {
  inScratch({ "tsconfig.json": '{ "compilerOptions": { "strictest": true } }\n' }, (_, scratch) => {
    expect(() => typeChecked([], join(scratch, "tsconfig.json"))).toThrow(
      /error TS5025: Unknown compiler option 'strictest'\. Did you mean 'strict'\?/u,
    );
  });
});

test("the files read are the ones git lists, and as many as recorded", () => {
  expect(FILES).toEqual(gitListed(".", SUFFIXES));
  expect(floorBreach("source.files", FILES.length)).toBeUndefined();
});

/** The kinds both walks reach: names, literals and type keywords, not punctuation. */
const CROSS_CHECKED = [
  ts.SyntaxKind.Identifier,
  ts.SyntaxKind.PrivateIdentifier,
  ts.SyntaxKind.StringLiteral,
  ts.SyntaxKind.NumericLiteral,
  ts.SyntaxKind.BigIntLiteral,
  ts.SyntaxKind.NoSubstitutionTemplateLiteral,
  ts.SyntaxKind.TemplateHead,
  ts.SyntaxKind.TemplateMiddle,
  ts.SyntaxKind.TemplateTail,
  ts.SyntaxKind.RegularExpressionLiteral,
  ts.SyntaxKind.NumberKeyword,
];

/** How many of each cross-checked kind `found` holds, by kind name. */
const tally = (found: readonly ts.Node[]): Record<string, number> =>
  Object.fromEntries(
    CROSS_CHECKED.map((kind) => [
      ts.SyntaxKind[kind],
      found.filter((node) => node.kind === kind).length,
    ]),
  );

test.each(FILES)("%s: the node walk and the token walk read the same names", (path) => {
  const file = readSource(path);
  expect(tally(nodes(file))).toEqual(tally(tokens(file)));
});

/** The compiler's own readers: called anywhere but `source.ts`, a guard would read source its own way. */
const READERS = new Set([
  "createSourceFile",
  "createScanner",
  "createProgram",
  "createLanguageService",
  "transpileModule",
  "preProcessFile",
]);

/** How `node`, an identifier named `ts`, is used: `ts.<name>`, a plain import, or another way. */
const useOf = (node: ts.Identifier): string => {
  const { parent } = node;
  if (ts.isPropertyAccessExpression(parent) && parent.expression === node) {
    return `ts.${parent.name.text}`;
  }
  if (ts.isQualifiedName(parent) && parent.left === node) {
    return `ts.${parent.right.text}`;
  }
  if (ts.isImportSpecifier(parent) && parent.propertyName === undefined) {
    return "import";
  }
  return "another way";
};

test("only tests/lib/source.ts calls the compiler's readers, and ts is reached only as ts.X", () => {
  const uses = FILES.filter((path) => path !== "tests/lib/source.ts").flatMap((path) => {
    const file = readSource(path);
    return nodes(file)
      .filter((node): node is ts.Identifier => ts.isIdentifier(node) && node.text === "ts")
      .map((node) => ({ path, line: lineOf(file, node), use: useOf(node) }));
  });
  const found = uses
    .filter(({ use }) => use === "another way" || READERS.has(use.slice("ts.".length)))
    .map(({ path, line, use }) => `${path} line ${String(line)}: ${use}`);
  expect(searched(found, { of: uses.length, what: "uses of ts" })).toEqual([]);
  expect(floorBreach("compiler-home.uses", uses.length)).toBeUndefined();
});
