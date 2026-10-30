/** What a guard found, item by item. */

/** Each item's findings beside where the item is (`where`), for only the items with any. An
 * absence search's verdict built so that none of its code runs only when something is found. */
export const foundIn = <T, F>(
  items: readonly T[],
  where: (item: T) => string,
  judge: (item: T) => readonly F[],
): { where: string; found: readonly F[] }[] =>
  items
    .map((item) => ({ where: where(item), found: judge(item) }))
    .filter(({ found }) => found.length > 0);
