import { expect, test } from "vitest";
import { CHOICE_LINE, DISCLAIMER } from "../src/advice-view.ts";
import * as words from "../src/words.ts";
import { fill, slotsOf, WORDS } from "../src/words.ts";

// The panel's words (#584, English only since Shyden's ruling 2026-11-17): one English text per
// key, and no language list, second table or identical-text allowance.

test("the words module holds the English words and their slot filling, nothing more", () => {
  expect(Object.keys(words).sort()).toEqual(["WORDS", "fill", "slotsOf"]);
});

test.each(Object.keys(WORDS).sort())("%s has an English text", (key) => {
  expect(WORDS[key as keyof typeof WORDS].trim()).not.toBe("");
});

test("the disclaimer and choice line are the panel's constants, word for word", () => {
  expect(WORDS.disclaimer).toBe(DISCLAIMER);
  expect(WORDS.choiceLine).toBe(CHOICE_LINE);
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

test("the slots of a text are listed once each, sorted", () => {
  expect(slotsOf("{b}: {a}, {b}")).toEqual(["a", "b"]);
});
