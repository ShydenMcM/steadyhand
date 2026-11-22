/**
 * CI's dependency audit (#240 AC5, #586): `npm run audit` runs `npm audit --json` and fails on
 * every advisory against any installed package, of any severity and dev tools included, except
 * one Shyden excepted by name until its expiry. An exception past its expiry fails, and so does
 * one that matches nothing (its fix landed), so it is removed rather than left behind.
 */
import { spawnSync } from "node:child_process";

export interface AuditException {
  /** The GitHub advisory's id. */
  readonly advisory: string;
  /** The last day (UTC, YYYY-MM-DD) the exception holds. */
  readonly expires: string;
  /** Where the ruling is recorded. */
  readonly ticket: string;
}

/**
 * None. The one there was, picomatch's GHSA-fc5q-39xc-vjpf (Shyden, 2026-11-18: "temporary
 * exception"), went when GitHub withdrew the advisory on 2026-11-18 (#586). A new one names its
 * advisory, its expiry and the ticket recording Shyden's ruling.
 */
export const EXCEPTIONS: readonly AuditException[] = [];

/** An advisory as npm lists it in a package's `via`; a plain string there names a package. */
interface Advisory {
  readonly url: string;
  readonly title: string;
}

export interface AuditReport {
  readonly vulnerabilities: Readonly<Record<string, { readonly via: readonly unknown[] }>>;
}

const isAdvisory = (entry: unknown): entry is Advisory =>
  typeof entry === "object" && entry !== null && "url" in entry && "title" in entry;

/** Each reason the audit fails on `today` (YYYY-MM-DD): an advisory not excepted, an expired
 * exception, or an exception that matches nothing. */
export const problems = (
  report: AuditReport,
  exceptions: readonly AuditException[],
  today: string,
): string[] => {
  const found = new Map(
    Object.values(report.vulnerabilities)
      .flatMap(({ via }) => via.filter(isAdvisory))
      .map(({ url, title }) => [url, title] as const),
  );
  const names = (url: string, exception: AuditException): boolean =>
    url.endsWith(`/${exception.advisory}`);
  const notExcepted = [...found]
    .filter(([url]) => !exceptions.some((exception) => names(url, exception)))
    .map(([url, title]) => `not excepted: ${url} (${title})`);
  const stale = exceptions.flatMap(({ advisory, expires, ticket }) => {
    if (today > expires) {
      return [`exception for ${advisory} expired on ${expires} (${ticket})`];
    }
    if (![...found.keys()].some((url) => url.endsWith(`/${advisory}`))) {
      return [`exception for ${advisory} matches nothing: remove it (${ticket})`];
    }
    return [];
  });
  return [...notExcepted, ...stale];
};

/** The report npm audit printed as JSON; anything else is refused by name. */
export const readReport = (printed: string): AuditReport => {
  let parsed: unknown;
  try {
    parsed = JSON.parse(printed);
  } catch {
    parsed = undefined;
  }
  if (typeof parsed !== "object" || parsed === null || !("vulnerabilities" in parsed)) {
    throw new Error("npm audit printed no report");
  }
  return parsed as AuditReport;
};

/** Audit when Node runs this file as its program (`npm run audit -- "$(date -u +%F)"`), and do
 * nothing when it is imported: a unit test runs both arms in-process with npm stood in. The date
 * comes from the caller, since no unit file reads a clock. Returns the exit code. */
export const main = (
  isProgram: boolean | undefined,
  audit: () => { readonly stdout: string | Uint8Array },
  today: string | undefined,
  say: (line: string) => void,
  exceptions: readonly AuditException[],
): number => {
  if (!isProgram) {
    return 0;
  }
  if (today === undefined || !/^\d{4}-\d{2}-\d{2}$/u.test(today)) {
    throw new Error(
      'npm run audit needs today\'s UTC date as YYYY-MM-DD: npm run audit -- "$(date -u +%F)"',
    );
  }
  const found = problems(readReport(audit().stdout.toString()), exceptions, today);
  if (found.length === 0) {
    say(
      exceptions.length === 0
        ? "npm audit: no advisories"
        : exceptions
            .map(
              ({ advisory, expires, ticket }) =>
                `npm audit: nothing but ${advisory}, excepted until ${expires} (${ticket.slice(ticket.indexOf("#"))})`,
            )
            .join("\n"),
    );
    return 0;
  }
  for (const line of found) {
    say(line);
  }
  return 1;
};

// The program's arm passes spawnSync bound to `npm audit --json`, the date it was given,
// `console.log` and the exceptions, so no line here runs only as the program (the unit test imports this file).
process.exitCode = main(
  import.meta.main,
  spawnSync.bind(undefined, "npm", ["audit", "--json"], { encoding: "utf8" }),
  process.argv[2],
  console.log,
  EXCEPTIONS,
);
