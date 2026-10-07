/**
 * The files a guard judges, found two ways: walked on disk, and listed by git. A guard asserts the
 * two are equal, so a walk that narrows (a folder left out, one suffix missed) fails by name.
 */
import { execFileSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { join, sep } from "node:path";
import { EXTENSION } from "./source.ts";

/** Folders the build and the tools write, never source. */
const SKIPPED = new Set(["node_modules", "dist", "coverage"]);

const named = (path: string, suffixes: readonly string[]): boolean =>
  suffixes.some((suffix) => path.endsWith(suffix));

/** Every file under `directory` (relative to `extension/`) whose name ends in one of `suffixes`. */
export const filesUnder = (directory: string, suffixes: readonly string[]): string[] =>
  readdirSync(join(EXTENSION, directory), { recursive: true, encoding: "utf8" })
    .map((found) => join(directory, found).split(sep).join("/"))
    .filter((path) => named(path, suffixes) && !path.split("/").some((part) => SKIPPED.has(part)))
    .sort();

/** The same files as git lists them, independent of the walk. */
export const gitListed = (directory: string, suffixes: readonly string[]): string[] =>
  execFileSync("git", ["ls-files", "-z", "--", directory], { cwd: EXTENSION, encoding: "utf8" })
    .split("\0")
    .filter((path) => path !== "" && named(path, suffixes))
    .sort();
