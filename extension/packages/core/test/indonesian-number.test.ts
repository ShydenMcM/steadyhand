import Decimal from "decimal.js";
import fc from "fast-check";
import { expect, test } from "vitest";
import {
  formatIndonesianNumber,
  parseIndonesianNumber,
  parseIndonesianWhole,
  UnreadableNumberError,
} from "../src/indonesian-number.ts";

// Each case as the broker writes it, and its exact value.
test.each([
  ["0", "0"],
  ["7", "7"],
  ["1.234", "1234"],
  ["1.234.567", "1234567"],
  ["999.999.999.999.999", "999999999999999"],
  ["1234567", "1234567"],
  ["1.234,50", "1234.5"],
  ["1.234,567", "1234.567"],
  ["0,5", "0.5"],
  ["12,25", "12.25"],
  ["1,2340", "1.234"],
  ["-1.234.567", "-1234567"],
  ["-0,75", "-0.75"],
  ["-12", "-12"],
])("%s reads as %s exactly", (text, value) => {
  expect(parseIndonesianNumber(text).equals(new Decimal(value))).toBe(true);
});

// Each refusal names the text and why.
test.each([
  ["", "is empty"],
  [" 1", "is not a number in Indonesian format"],
  ["1 ", "is not a number in Indonesian format"],
  ["+1", "is not a number in Indonesian format"],
  ["−1", "is not a number in Indonesian format"],
  ["(1.000)", "is not a number in Indonesian format"],
  ["1.23", "is not a number in Indonesian format"],
  ["1.2345", "is not a number in Indonesian format"],
  ["12.345.6", "is not a number in Indonesian format"],
  ["1234.567", "is not a number in Indonesian format"],
  ["01", "is not a number in Indonesian format"],
  ["00,5", "is not a number in Indonesian format"],
  [",5", "is not a number in Indonesian format"],
  ["1,", "is not a number in Indonesian format"],
  ["1,2,3", "is not a number in Indonesian format"],
  ["1.234.56,7", "is not a number in Indonesian format"],
  ["Rp 1.000", "is not a number in Indonesian format"],
  ["1e3", "is not a number in Indonesian format"],
  ["-", "is not a number in Indonesian format"],
  ["1,234", "is ambiguous: a comma before exactly three digits could be a thousands separator"],
  ["-12,500", "is ambiguous: a comma before exactly three digits could be a thousands separator"],
])("%j is refused: %s", (text, reason) => {
  expect(() => parseIndonesianNumber(text)).toThrow(
    new UnreadableNumberError(text, reason).message,
  );
});

test("a refusal carries the text and the reason, and names its class", () => {
  const error = new UnreadableNumberError("1,234", "why");
  expect(error.text).toBe("1,234");
  expect(error.reason).toBe("why");
  expect(error.name).toBe("UnreadableNumberError");
  expect(error.message).toBe('"1,234" why');
});

test.each([
  ["1.234.567", 1234567n],
  ["-1.000", -1000n],
  ["0", 0n],
  ["12,00", 12n],
])("%s reads as the whole number %s", (text, value) => {
  expect(parseIndonesianWhole(text)).toBe(value);
});

test("a whole number with a fraction is refused, naming it", () => {
  expect(() => parseIndonesianWhole("1.234,5")).toThrow(
    new UnreadableNumberError("1.234,5", "has a fraction where a whole number is needed").message,
  );
});

test.each([
  ["0", "0"],
  ["-0", "0"],
  ["1234567", "1.234.567"],
  ["-1234.5", "-1.234,5"],
  ["999", "999"],
  ["1000", "1.000"],
  ["0.05", "0,05"],
  ["1.234", "1,2340"],
  ["-12.5", "-12,5"],
  ["1234.567", "1.234,567"],
])("%s is written %s", (value, text) => {
  expect(formatIndonesianNumber(new Decimal(value))).toBe(text);
});

test("writing then reading returns the value, for any amount the broker may show", () => {
  const amounts = fc
    .tuple(
      fc.bigInt({ min: -(10n ** 18n), max: 10n ** 18n }),
      fc.integer({ min: 0, max: 8 }).map((places) => BigInt(places)),
    )
    .map(([units, places]) =>
      new Decimal(units.toString()).div(new Decimal(10).pow(places.toString())),
    );
  fc.assert(
    fc.property(amounts, (value) => {
      expect(parseIndonesianNumber(formatIndonesianNumber(value)).equals(value)).toBe(true);
    }),
  );
});
