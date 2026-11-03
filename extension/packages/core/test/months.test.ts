import { expect, test } from "vitest";
import { endOfMonth, monthsBefore } from "../src/months.ts";

// Hand-computed calendar months for momentum-rotation's windows (spec §7.2, #235 AC2 and AC7).

test.each([
  ["a 31-day month", 2024n, 1n, "2024-01-31"],
  ["a 30-day month", 2024n, 4n, "2024-04-30"],
  ["February of a leap year", 2024n, 2n, "2024-02-29"],
  ["February of a common year", 2023n, 2n, "2023-02-28"],
  ["February of a century that is not a leap year", 2100n, 2n, "2100-02-28"],
  ["February of a century that is a leap year", 2000n, 2n, "2000-02-29"],
] as const)("the last day of %s", (_case, year, month, last) => {
  expect(endOfMonth(year, month)).toBe(last);
});

test.each([
  ["a day that exists in the earlier month is kept", "2024-05-15", 1n, "2024-04-15"],
  [
    "the 31st one month before a 30-day month's end is that month's 30th",
    "2024-05-31",
    1n,
    "2024-04-30",
  ],
  ["the 31st two months back lands on a 31st", "2024-05-31", 2n, "2024-03-31"],
  ["the 30th one month before March is February's last day", "2024-03-30", 1n, "2024-02-29"],
  ["the 31st one month before March in a common year is the 28th", "2023-03-31", 1n, "2023-02-28"],
  ["a month back from January is December of the year before", "2024-01-31", 1n, "2023-12-31"],
  ["twelve months back is the same day a year before", "2024-05-31", 12n, "2023-05-31"],
  ["twelve months back from a leap day is February's last day", "2024-02-29", 12n, "2023-02-28"],
  ["no months back is the day itself", "2024-05-31", 0n, "2024-05-31"],
] as const)("%s", (_case, day, months, before) => {
  expect(monthsBefore(day, months)).toBe(before);
});
