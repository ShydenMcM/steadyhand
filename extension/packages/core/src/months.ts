/** Calendar months: their last days, and a day so many months before another. */

const isLeap = (year: bigint): boolean =>
  year % 4n === 0n && (year % 100n !== 0n || year % 400n === 0n);

const two = (value: bigint): string => value.toString().padStart(2, "0");

/** `year-month-last day`, as an ISO day. */
export const endOfMonth = (year: bigint, month: bigint): string => {
  const thirty = month === 4n || month === 6n || month === 9n || month === 11n;
  const february = isLeap(year) ? 29n : 28n;
  const last = month === 2n ? february : thirty ? 30n : 31n;
  return `${year.toString().padStart(4, "0")}-${two(month)}-${two(last)}`;
};

/** The day `months` calendar months before `day`: the same date that many months back, or that
 * month's last day when it is shorter (31 May less a month is 30 April). */
export const monthsBefore = (day: string, months: bigint): string => {
  const counted = BigInt(day.slice(0, 4)) * 12n + BigInt(day.slice(5, 7)) - 1n - months;
  const last = endOfMonth(counted / 12n, (counted % 12n) + 1n);
  const same = `${last.slice(0, 8)}${day.slice(8, 10)}`;
  return same < last ? same : last;
};
