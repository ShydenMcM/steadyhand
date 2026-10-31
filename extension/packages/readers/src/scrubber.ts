/**
 * The scrubber (spec §5.2): a page saved from a real account loses its holder's names, account
 * numbers and every email address before it is kept as a fixture. Names and account numbers are
 * the holder's own, given to it (they cannot be told from other text); emails are found by shape.
 */

/** The holder's details to remove. An account number is its digits; written with spaces, dots or
 * dashes between them it is still found. */
export interface Personal {
  readonly names: readonly string[];
  readonly accountNumbers: readonly string[];
}

export type FindingKind = "name" | "account number" | "email";

export interface Finding {
  readonly kind: FindingKind;
  readonly text: string;
}

const PLACEHOLDER: Readonly<Record<FindingKind, string>> = {
  name: "[name]",
  "account number": "[account]",
  email: "[email]",
};

const EMAIL = "[\\p{L}\\p{N}._%+-]+@[\\p{L}\\p{N}.-]+\\.\\p{L}{2,}";

const escape = (text: string): string => text.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");

/** Every pattern to remove, by kind, each matching only whole words or whole digit runs. */
const patterns = (personal: Personal): readonly [FindingKind, RegExp][] => {
  const names = personal.names.map((name): [FindingKind, RegExp] => {
    if (name.trim() === "") {
      throw new RangeError("a name to scrub is empty");
    }
    const body = name.trim().split(/\s+/u).map(escape).join("\\s+");
    return ["name", new RegExp(`(?<![\\p{L}\\p{N}])${body}(?![\\p{L}\\p{N}])`, "giu")];
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
  return [...names, ...accounts, ["email", new RegExp(EMAIL, "gu")]];
};

/** Each holder detail and email still in `text`, in the order: names, account numbers, emails. */
export const personalFound = (text: string, personal: Personal): readonly Finding[] =>
  patterns(personal).flatMap(([kind, pattern]) =>
    [...text.matchAll(pattern)].map((match) => ({ kind, text: match[0] })),
  );

/** `text` with each holder detail and email replaced by its placeholder. */
export const scrub = (text: string, personal: Personal): string =>
  patterns(personal).reduce(
    (scrubbed, [kind, pattern]) => scrubbed.replace(pattern, PLACEHOLDER[kind]),
    text,
  );
