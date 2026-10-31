import { readdirSync, readFileSync } from "node:fs";
import { expect, test } from "vitest";
import { FIXTURE_PAGES } from "../src/fixture-broker.ts";
import { personalFound, scrub, type Personal } from "../src/scrubber.ts";

// The scrubber (#226 AC6, spec §5.2): a saved page loses its account numbers, names and emails
// before it becomes a fixture, and a test proves none remains in any fixture.

/** The made-up account holder the fixture pages stand in for. */
const HOLDER: Personal = { names: ["Budi Santoso"], accountNumbers: ["0012345678"] };

const FIXTURE_FILES = readdirSync(FIXTURE_PAGES).filter((name) => name.endsWith(".html"));

test("there are fixture pages to judge", () => {
  expect(FIXTURE_FILES).toHaveLength(7);
});

test.each(FIXTURE_FILES.map((name) => [name]))(
  "fixture %s holds no account number, name or email",
  (name) => {
    const text = readFileSync(new URL(name, FIXTURE_PAGES), "utf8");
    expect(personalFound(text, HOLDER)).toEqual([]);
  },
);

const clean = readFileSync(new URL("portfolio.html", FIXTURE_PAGES), "utf8");

// Each planted example turns the check red, naming its kind.
test.each([
  ["Budi Santoso", "name"],
  ["BUDI SANTOSO", "name"],
  ["0012345678", "account number"],
  ["001-234-5678", "account number"],
  ["0012 3456 78", "account number"],
  ["budi.s@example.co.id", "email"],
  ["Budi+saham@mail.example.com", "email"],
] as const)("a planted %j is found as a %s", (planted, kind) => {
  const text = clean.replace("[name]", planted);
  expect(personalFound(text, HOLDER)).toEqual([{ kind, text: planted }]);
});

test("scrubbing replaces each kind with its placeholder", () => {
  const saved =
    "Nasabah: Budi Santoso · Rekening: 001-234-5678 · Email: budi.s@example.co.id · budi santoso";
  const scrubbed = scrub(saved, HOLDER);
  expect(scrubbed).toBe("Nasabah: [name] · Rekening: [account] · Email: [email] · [name]");
  expect(personalFound(scrubbed, HOLDER)).toEqual([]);
});

test("a name inside a longer word is left alone", () => {
  const holder: Personal = { names: ["Ani"], accountNumbers: [] };
  expect(scrub("Ani bought DANIEL and Ani.", holder)).toBe("[name] bought DANIEL and [name].");
});

test("digits next to an account number are not part of it", () => {
  expect(personalFound("90012345678", HOLDER)).toEqual([]);
});

test("a name holding pattern characters is matched as written", () => {
  const holder: Personal = { names: ["A. (Budi)"], accountNumbers: [] };
  expect(scrub("by A. (Budi) and AX (Budi)", holder)).toBe("by [name] and AX (Budi)");
});

test.each([
  [{ names: [""], accountNumbers: [] }, "a name to scrub is empty"],
  [{ names: [], accountNumbers: ["12-3"] }, 'account number "12-3" must be digits only'],
  [{ names: [], accountNumbers: [""] }, 'account number "" must be digits only'],
])("personal details that would match everything are refused: %s", (personal, message) => {
  expect(() => scrub("x", personal)).toThrow(message);
});
