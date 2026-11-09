import { expect, test } from "vitest";
import { CHOICE_LINE, DISCLAIMER } from "../src/advice-view.ts";
import { fill, identicalAllowed, LANGUAGES, slotsOf, WORDS, type Language } from "../src/words.ts";

// The panel's words in each language (#251 AC1-AC2): every string the panel writes has an
// English and an Indonesian text, with the same slots, and an Indonesian text is never the
// English left untranslated unless it is only names and codes.

const KEYS = Object.keys(WORDS.en).sort();

test("both languages are offered, each named in its own language", () => {
  expect(LANGUAGES).toEqual([
    ["en", "English"],
    ["id", "Bahasa Indonesia"],
  ]);
});

test("Indonesian has exactly the English keys", () => {
  expect(Object.keys(WORDS.id).sort()).toEqual(KEYS);
});

test.each(KEYS)("%s has a text in both languages, with the same slots", (key) => {
  const english = WORDS.en[key as keyof typeof WORDS.en];
  const indonesian = WORDS.id[key as keyof typeof WORDS.id];
  expect(english.trim()).not.toBe("");
  expect(indonesian.trim()).not.toBe("");
  expect(slotsOf(indonesian)).toEqual(slotsOf(english));
});

test.each(KEYS)("%s in Indonesian is not its English left untranslated", (key) => {
  const english = WORDS.en[key as keyof typeof WORDS.en];
  const indonesian = WORDS.id[key as keyof typeof WORDS.id];
  expect(indonesian === english && !identicalAllowed(english)).toBe(false);
});

test("the English disclaimer and choice line are the panel's constants, word for word", () => {
  expect(WORDS.en.disclaimer).toBe(DISCLAIMER);
  expect(WORDS.en.choiceLine).toBe(CHOICE_LINE);
});

// The derived list: a text may read the same in both languages only when every word in it is
// the product's name, a code in capitals, a number or a slot.
test.each([
  ["steadyhand", true],
  ["IDX", true],
  ["BBCA: {count}", true],
  ["2025-06-16", true],
  ["{day}", true],
  ["Settings", false],
  ["steadyhand reads", false],
  ["lot", false],
  ["", false],
])("%j may read the same in both languages: %s", (text, allowed) => {
  expect(identicalAllowed(text)).toBe(allowed);
});

test("a slot is filled with its value, each time it appears", () => {
  expect(fill("{a} and {b}, then {a}", { a: "1", b: "BBCA" })).toBe("1 and BBCA, then 1");
});

test("a slot with no value is refused by name", () => {
  expect(() => fill("{a} and {b}", { a: "1" })).toThrow("the text has a slot {b} with no value");
});

test("a value for no slot is refused by name", () => {
  expect(() => fill("{a}", { a: "1", c: "2" })).toThrow("the text has no slot {c}");
});

// Sorted, so a sentence whose words come in another order in Indonesian has the same slots.
test("the slots of a text are listed once each, sorted", () => {
  expect(slotsOf("{b}: {a}, {b}")).toEqual(["a", "b"]);
});

test("a language is one of the two", () => {
  const each: readonly Language[] = LANGUAGES.map(([language]) => language);
  expect(each).toEqual(["en", "id"]);
});
