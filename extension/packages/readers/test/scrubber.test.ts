import { readdirSync, readFileSync } from "node:fs";
import { expect, test } from "vitest";
import { personalFound, scrub, type Personal } from "../src/scrubber.ts";
import { FIXTURE_PAGES } from "./fixture-pages.ts";

// The scrubber (#226 AC6, #460, spec §5.2): a saved page loses every personal detail an
// Indonesian broker page may show before it becomes a fixture (the holder's names, address and
// account numbers, given; emails, phone numbers, NIK, NPWP, SID and long account numbers, by
// shape), and a test proves none remains in any fixture.

/** The made-up account holder the fixture pages stand in for. */
const HOLDER: Personal = {
  names: ["Budi Santoso"],
  addresses: ["Jl. Melati No. 12, Jakarta Selatan"],
  accountNumbers: ["0012345678"],
};

const FIXTURE_FILES = readdirSync(FIXTURE_PAGES).filter((name) => name.endsWith(".html"));

test("there are fixture pages to judge", () => {
  expect(FIXTURE_FILES).toHaveLength(7);
});

test.each(FIXTURE_FILES.map((name) => [name]))(
  "fixture %s holds no personal detail of any kind",
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
  ["Jl. Melati No. 12, Jakarta Selatan", "address"],
  ["jl. melati  no. 12,\n jakarta selatan", "address"],
  ["+62 812-3456-7890", "phone"],
  ["+6281234567890", "phone"],
  ["+62 21 5550 1234", "phone"],
  ["0812-3456-7890", "phone"],
  ["081234567890", "phone"],
  ["0812 3456 789", "phone"],
  ["3171234567890001", "NIK"],
  ["317123 456789 0001", "NIK"],
  ["01.234.567.8-901.000", "NPWP"],
  ["012345678901000", "NPWP"],
  ["IDD140512345678", "SID"],
  ["IDD1405M5523123", "SID"],
  ["1234567890", "account number"],
  ["5550123456789", "account number"],
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

test("scrubbing replaces each kind found by shape with its placeholder", () => {
  const saved =
    "Alamat: Jl. Melati No. 12, Jakarta Selatan · HP: +62 812-3456-7890 · NIK: " +
    "3171234567890001 · NPWP: 01.234.567.8-901.000 · SID: IDD140512345678 · RDN: 1234567890";
  const scrubbed = scrub(saved, HOLDER);
  expect(scrubbed).toBe(
    "Alamat: [address] · HP: [phone] · NIK: [NIK] · NPWP: [NPWP] · SID: [SID] · RDN: [account]",
  );
  expect(personalFound(scrubbed, HOLDER)).toEqual([]);
});

test("each detail is found once, under the first kind whose shape it has", () => {
  expect(personalFound("NIK 3171234567890001 and HP 081234567890", HOLDER)).toEqual([
    { kind: "phone", text: "081234567890" },
    { kind: "NIK", text: "3171234567890001" },
  ]);
});

// Figures a broker page shows that are not personal: each is left as it is.
test.each([
  ["a price with thousands dots", "Rp 1.234.567.890"],
  ["a plain amount under ten digits", "123456789"],
  ["a day", "2025-06-17"],
  ["a time", "08:30:00"],
  ["an ISIN", "IDA000012008"],
  ["a stock code", "BBCA"],
  ["a lot count", "0812"],
])("%s is not personal: %j", (_case, text) => {
  expect(personalFound(text, HOLDER)).toEqual([]);
});

test("a name inside a longer word is left alone", () => {
  const holder: Personal = { names: ["Ani"], addresses: [], accountNumbers: [] };
  expect(scrub("Ani bought DANIEL and Ani.", holder)).toBe("[name] bought DANIEL and [name].");
});

test("digits next to an account number are not part of it", () => {
  const holder: Personal = { names: [], addresses: [], accountNumbers: ["12345678"] };
  expect(personalFound("912345678", holder)).toEqual([]);
});

test("a name holding pattern characters is matched as written", () => {
  const holder: Personal = { names: ["A. (Budi)"], addresses: [], accountNumbers: [] };
  expect(scrub("by A. (Budi) and AX (Budi)", holder)).toBe("by [name] and AX (Budi)");
});

test.each([
  [{ names: [""], addresses: [], accountNumbers: [] }, "a name to scrub is empty"],
  [{ names: [], addresses: [" "], accountNumbers: [] }, "an address to scrub is empty"],
  [
    { names: [], addresses: [], accountNumbers: ["12-3"] },
    'account number "12-3" must be digits only',
  ],
  [{ names: [], addresses: [], accountNumbers: [""] }, 'account number "" must be digits only'],
])("personal details that would match everything are refused: %s", (personal, message) => {
  expect(() => scrub("x", personal)).toThrow(message);
});
