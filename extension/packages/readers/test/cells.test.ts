import { expect, test } from "vitest";
import { numberAt, refusing, Refusal } from "../src/cells.ts";

test("a refusal thrown inside a reader is returned as its refusal", () => {
  expect(
    refusing(() => {
      throw new Refusal("no table");
    }),
  ).toEqual({ refused: "no table" });
});

test("any other error inside a reader is not a refusal and goes on up", () => {
  expect(() =>
    refusing(() => {
      throw new TypeError("a bug");
    }),
  ).toThrow(new TypeError("a bug"));
});

test("an error that is not an unreadable number goes on up from where it was read", () => {
  expect(() => numberAt("cell", () => BigInt("x"))).toThrow(SyntaxError);
});
