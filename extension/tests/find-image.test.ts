import { expect, test } from "vitest";
import { findImage, type Picture } from "./lib/find-image.ts";

/** A picture from rows of single-letter pixels: each letter one grey level, as RGB. */
const picture = (rows: readonly string[]): Picture => {
  const height = rows.length;
  const width = rows[0]?.length ?? 0;
  const rgb = new Uint8Array(width * height * 3);
  rows.forEach((row, y) => {
    for (let x = 0; x < row.length; x += 1) {
      rgb.fill(row.charCodeAt(x), (y * width + x) * 3, (y * width + x) * 3 + 3);
    }
  });
  return { width, height, rgb };
};

const SCREEN = picture(["aaaaaa", "aabcaa", "aadeaa", "aaaaaa"]);
const TILE = picture(["bc", "de"]);

test("finds where a template sits on the screen, as the centre of the match", () => {
  expect(findImage(SCREEN, TILE)).toEqual([{ x: 3, y: 2 }]);
});

test("finds every place the template sits", () => {
  const twice = picture(["bcabc", "deade"]);
  expect(findImage(twice, TILE)).toEqual([
    { x: 1, y: 1 },
    { x: 4, y: 1 },
  ]);
});

test("finds nothing when one pixel differs", () => {
  expect(findImage(SCREEN, picture(["bc", "df"]))).toEqual([]);
});

test("a match at the screen's last row and column is found", () => {
  const corner = picture(["aaa", "abc", "ade"]);
  expect(findImage(corner, TILE)).toEqual([{ x: 2, y: 2 }]);
});

test("a template larger than the screen is found nowhere", () => {
  expect(findImage(TILE, SCREEN)).toEqual([]);
});

test("a picture whose bytes do not fill its size is refused", () => {
  expect(() => findImage({ width: 2, height: 2, rgb: new Uint8Array(11) }, TILE)).toThrow(
    "a 2x2 picture holds 12 bytes of RGB, got 11",
  );
});
