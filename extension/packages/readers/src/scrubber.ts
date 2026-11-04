/**
 * The scrubber (spec §5.2, #460): a page saved from a real account loses every personal detail an
 * Indonesian broker page may show before it is kept as a fixture. The holder's names, address and
 * account numbers are given to it, since they cannot be told from other text. Emails, phone
 * numbers (+62 and 08 forms), NIK (16 digits), NPWP (grouped, or 15 digits plain), SID (`ID`, a
 * letter, then 12 letters or digits) and any other run of ten or more digits, which an RDN or a
 * securities account number is, are found by shape. A broker writes its figures with thousands
 * separators, so a plain run that long is never one of them.
 */

/** The holder's details to remove. An account number is its digits; written with spaces, dots or
 * dashes between them it is still found. */
export interface Personal {
  readonly names: readonly string[];
  /** The holder's street address, as the page writes it; matched like a name. */
  readonly addresses: readonly string[];
  readonly accountNumbers: readonly string[];
}

export type FindingKind =
  "name" | "address" | "account number" | "email" | "NPWP" | "SID" | "phone" | "NIK";

export interface Finding {
  readonly kind: FindingKind;
  readonly text: string;
}

const PLACEHOLDER: Readonly<Record<FindingKind, string>> = {
  name: "[name]",
  address: "[address]",
  "account number": "[account]",
  email: "[email]",
  NPWP: "[NPWP]",
  SID: "[SID]",
  phone: "[phone]",
  NIK: "[NIK]",
};

const EMAIL = "[\\p{L}\\p{N}._%+-]+@[\\p{L}\\p{N}.-]+\\.\\p{L}{2,}";

const escape = (text: string): string => text.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");

/** A separator a number may be written with between its groups. */
const SEP = "[\\s.-]?";

/** Not inside a longer number: no digit (or a plus sign) before it, no digit after it. */
const START = "(?<![\\p{N}+])";
const END = "(?!\\p{N})";

/** Each kind found by shape, most particular first: a detail is found once, under the first. */
const SHAPES: readonly (readonly [FindingKind, string])[] = [
  ["NPWP", `${START}\\d{2}\\.\\d{3}\\.\\d{3}\\.\\d-\\d{3}\\.\\d{3}${END}`],
  ["SID", "(?<![\\p{L}\\p{N}])ID[A-Z][0-9A-Z]{12}(?![\\p{L}\\p{N}])"],
  ["phone", `\\+62${SEP}\\d{2,3}${SEP}\\d{3,4}${SEP}\\d{3,5}${END}`],
  ["phone", `${START}08\\d{1,2}${SEP}\\d{3,4}${SEP}\\d{3,5}${END}`],
  ["NIK", `${START}\\d{6}${SEP}\\d{6}${SEP}\\d{4}${END}`],
  ["NPWP", `${START}\\d{15}${END}`],
  ["account number", `${START}\\d{10,}${END}`],
];

/** `text` as a pattern of words, any run of space between them, matched whole. */
const words = (text: string): RegExp =>
  new RegExp(
    `(?<![\\p{L}\\p{N}])${text.trim().split(/\s+/u).map(escape).join("\\s+")}(?![\\p{L}\\p{N}])`,
    "giu",
  );

/** Every pattern to remove, by kind, each matching only whole words or whole digit runs: the
 * holder's names, addresses and account numbers, then emails, then each shape. */
const patterns = (personal: Personal): readonly [FindingKind, RegExp][] => {
  const names = personal.names.map((name): [FindingKind, RegExp] => {
    if (name.trim() === "") {
      throw new RangeError("a name to scrub is empty");
    }
    return ["name", words(name)];
  });
  const addresses = personal.addresses.map((address): [FindingKind, RegExp] => {
    if (address.trim() === "") {
      throw new RangeError("an address to scrub is empty");
    }
    return ["address", words(address)];
  });
  const accounts = personal.accountNumbers.map((account): [FindingKind, RegExp] => {
    if (!/^\d+$/u.test(account)) {
      throw new RangeError(`account number ${JSON.stringify(account)} must be digits only`);
    }
    return [
      "account number",
      new RegExp(`(?<!\\d)${account.replace(/\d(?=\d)/gu, "$&[\\s.-]?")}(?!\\d)`, "gu"),
    ];
  });
  const shapes = SHAPES.map(([kind, shape]): [FindingKind, RegExp] => [
    kind,
    new RegExp(shape, "gu"),
  ]);
  return [...names, ...addresses, ...accounts, ["email", new RegExp(EMAIL, "gu")], ...shapes];
};

/** Each personal detail still in `text`, each found once: every pattern in turn is judged on the
 * text the patterns before it have scrubbed. */
export const personalFound = (text: string, personal: Personal): readonly Finding[] => {
  const found: Finding[] = [];
  let left = text;
  for (const [kind, pattern] of patterns(personal)) {
    for (const match of left.matchAll(pattern)) {
      found.push({ kind, text: match[0] });
    }
    left = left.replace(pattern, PLACEHOLDER[kind]);
  }
  return found;
};

/** `text` with each personal detail replaced by its kind's placeholder. */
export const scrub = (text: string, personal: Personal): string =>
  patterns(personal).reduce(
    (scrubbed, [kind, pattern]) => scrubbed.replace(pattern, PLACEHOLDER[kind]),
    text,
  );
