/** Where a small picture sits on a screenshot (#503): how the browser suite finds the extension's
 * toolbar button and the extensions menu button before it clicks them as a person does. */

/** An image as 8-bit RGB, row by row from the top left. */
export interface Picture {
  readonly width: number;
  readonly height: number;
  readonly rgb: Uint8Array;
}

/** A point on the screen, in pixels from its top left. */
export interface Point {
  readonly x: number;
  readonly y: number;
}

const checked = (picture: Picture): Picture => {
  const expected = picture.width * picture.height * 3;
  if (picture.rgb.length !== expected) {
    throw new Error(
      `a ${String(picture.width)}x${String(picture.height)} picture holds ${String(expected)} bytes of RGB, got ${String(picture.rgb.length)}`,
    );
  }
  return picture;
};

const matchesAt = (screen: Picture, template: Picture, left: number, top: number): boolean => {
  const row = template.width * 3;
  for (let y = 0; y < template.height; y += 1) {
    const from = ((top + y) * screen.width + left) * 3;
    const wanted = template.rgb.subarray(y * row, (y + 1) * row);
    const seen = screen.rgb.subarray(from, from + row);
    for (let i = 0; i < row; i += 1) {
      if (seen[i] !== wanted[i]) {
        return false;
      }
    }
  }
  return true;
};

/** The centre of every place *template* appears pixel for pixel on *screen*, top row first. */
export const findImage = (screen: Picture, template: Picture): Point[] => {
  checked(screen);
  checked(template);
  const found: Point[] = [];
  for (let top = 0; top + template.height <= screen.height; top += 1) {
    for (let left = 0; left + template.width <= screen.width; left += 1) {
      if (matchesAt(screen, template, left, top)) {
        found.push({
          x: left + Math.floor(template.width / 2),
          y: top + Math.floor(template.height / 2),
        });
      }
    }
  }
  return found;
};
