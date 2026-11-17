import { expect, test } from "vitest";
import { EXCEPTIONS, main, problems, readReport } from "../audit.ts";

// CI's dependency audit (#240 AC5, #586): every advisory against any installed package fails the
// job, dev tools too, except one Shyden excepted by name until its expiry. The report's shape is
// npm audit --json's own, recorded 2026-11-18 (picomatch via fdir, as npm printed it).

const PICOMATCH = "https://github.com/advisories/GHSA-fc5q-39xc-vjpf";
const TITLE = "picomatch vulnerable to ReDoS through single-branch repeated extglobs";
const OTHER = "https://github.com/advisories/GHSA-aaaa-bbbb-cccc";

const advisory = (url: string, title: string, severity: string) => ({
  source: 1,
  name: "x",
  dependency: "x",
  title,
  url,
  severity,
  range: "*",
});

const report = (...advisories: readonly ReturnType<typeof advisory>[]) => ({
  auditReportVersion: 2,
  vulnerabilities: {
    picomatch: { name: "picomatch", severity: "high", via: advisories },
    fdir: { name: "fdir", severity: "high", via: ["picomatch"] },
  },
  metadata: {},
});

const ONLY_PICOMATCH = report(advisory(PICOMATCH, TITLE, "high"));

test("the one exception is picomatch's advisory, until 2026-12-01, recorded on #586", () => {
  expect(EXCEPTIONS).toEqual([
    { advisory: "GHSA-fc5q-39xc-vjpf", expires: "2026-12-01", ticket: "ShydenMcM/steadyhand#586" },
  ]);
});

test("the excepted advisory alone, before its expiry, passes", () => {
  expect(problems(ONLY_PICOMATCH, EXCEPTIONS, "2026-11-18")).toEqual([]);
});

test("the exception still holds on its last day", () => {
  expect(problems(ONLY_PICOMATCH, EXCEPTIONS, "2026-12-01")).toEqual([]);
});

test("the exception fails the day after its expiry, naming its ticket", () => {
  expect(problems(ONLY_PICOMATCH, EXCEPTIONS, "2026-12-02")).toEqual([
    "exception for GHSA-fc5q-39xc-vjpf expired on 2026-12-01 (ShydenMcM/steadyhand#586)",
  ]);
});

test.each(["low", "moderate", "high", "critical"])(
  "another advisory of %s severity fails by its url and title",
  (severity) => {
    const found = report(advisory(PICOMATCH, TITLE, "high"), advisory(OTHER, "a flaw", severity));
    expect(problems(found, EXCEPTIONS, "2026-11-18")).toEqual([`not excepted: ${OTHER} (a flaw)`]);
  },
);

test("an exception that matches nothing fails, so it is removed once the fix lands", () => {
  expect(problems(report(), EXCEPTIONS, "2026-11-18")).toEqual([
    "exception for GHSA-fc5q-39xc-vjpf matches nothing: remove it (ShydenMcM/steadyhand#586)",
  ]);
});

test("an advisory reached through several packages is reported once", () => {
  const twice = {
    ...report(advisory(OTHER, "a flaw", "low")),
    vulnerabilities: {
      a: { via: [advisory(OTHER, "a flaw", "low")] },
      b: { via: [advisory(OTHER, "a flaw", "low")] },
    },
  };
  expect(problems(twice, [], "2026-11-18")).toEqual([`not excepted: ${OTHER} (a flaw)`]);
});

test("npm audit's report is read from its JSON", () => {
  expect(readReport(JSON.stringify(ONLY_PICOMATCH))).toEqual(ONLY_PICOMATCH);
});

test.each([
  ["text that is not JSON", "npm ERR! network"],
  ["JSON with no report", JSON.stringify({ error: { code: "ENOTFOUND" } })],
  ["JSON that is not an object", "null"],
])("%s is refused by name", (_, printed) => {
  expect(() => readReport(printed)).toThrow("npm audit printed no report");
});

/** The program's arms, run in-process with npm stood in. */
const run = (isProgram: boolean, printed: string, today: string | undefined) => {
  const lines: string[] = [];
  let audited = 0;
  const code = main(
    isProgram,
    () => {
      audited += 1;
      return { stdout: printed };
    },
    today,
    (line) => lines.push(line),
  );
  return { code, lines, audited };
};

test("imported, the program audits nothing", () => {
  expect(run(false, JSON.stringify(ONLY_PICOMATCH), "2026-11-18")).toEqual({
    code: 0,
    lines: [],
    audited: 0,
  });
});

test("run, a report with only the excepted advisory exits 0 and says so", () => {
  expect(run(true, JSON.stringify(ONLY_PICOMATCH), "2026-11-18")).toEqual({
    code: 0,
    lines: ["npm audit: nothing but GHSA-fc5q-39xc-vjpf, excepted until 2026-12-01 (#586)"],
    audited: 1,
  });
});

test("run, a report with an advisory not excepted exits 1, naming it", () => {
  const found = report(advisory(PICOMATCH, TITLE, "high"), advisory(OTHER, "a flaw", "low"));
  expect(run(true, JSON.stringify(found), "2026-11-18")).toEqual({
    code: 1,
    lines: [`not excepted: ${OTHER} (a flaw)`],
    audited: 1,
  });
});

// The date comes from the caller (CI passes `date -u +%F`): no unit file reads a clock (#586).
test.each([
  ["no date", undefined],
  ["a date not as YYYY-MM-DD", "18/11/2026"],
  ["a date with more after it", "2026-11-18T00:00"],
])("run with %s, the audit is refused by name before npm runs", (_, today) => {
  expect(() => run(true, JSON.stringify(ONLY_PICOMATCH), today)).toThrow(
    'npm run audit needs today\'s UTC date as YYYY-MM-DD: npm run audit -- "$(date -u +%F)"',
  );
});

test("run with no date, nothing is audited", () => {
  let audited = 0;
  expect(() =>
    main(
      true,
      () => {
        audited += 1;
        return { stdout: JSON.stringify(ONLY_PICOMATCH) };
      },
      undefined,
      () => undefined,
    ),
  ).toThrow();
  expect(audited).toBe(0);
});
